import json
import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from sqlalchemy import select

from app.db import async_session
from app.models.task import Task, TaskStatus, PublishType
from app.models.system_config import SystemConfig
from app.services.rewriter.prompt_builder import extract_title_and_body
from app.services.rewriter.validation import validate_rewritten_html
from app.services.tagging.service import build_tag_records

logger = logging.getLogger(__name__)


class StageExecutionError(Exception):
    def __init__(self, stage: str, original: Exception):
        super().__init__(str(original))
        self.stage = stage
        self.original = original


def _build_generated_tags(rewritten_title: str, rewritten_body: str) -> list[dict]:
    text = BeautifulSoup(rewritten_body or "", "html.parser").get_text(" ", strip=True)
    candidates: list[str] = []

    for value in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}|[\u4e00-\u9fff]{2,8}", f"{rewritten_title or ''} {text}"):
        if value not in candidates:
            candidates.append(value)
        if len(candidates) >= 6:
            break

    return build_tag_records(candidates)


def ensure_task_is_retryable(task: Task) -> None:
    if task.status != TaskStatus.failed or not task.failed_stage:
        raise ValueError("Task is not retryable")


def ensure_task_can_republish(task: Task) -> None:
    if task.status == TaskStatus.completed:
        pass
    elif task.status == TaskStatus.failed and task.failed_stage == "publishing":
        pass
    else:
        raise ValueError("Task status does not support republish")

    if not (task.rewritten_title or task.title) or not task.rewritten_content:
        raise ValueError("Task has no rewritten content to republish")


async def _update_task(task_id: str, **kwargs):
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        for key, value in kwargs.items():
            setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return task


async def _broadcast_update(task_id: str, status: str, progress: int, stage_detail: str):
    from app.routers.ws import ws_manager
    await ws_manager.broadcast_task_update(task_id, status, progress, stage_detail)


async def _get_config(db_session, key: str) -> dict | None:
    result = await db_session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        return json.loads(row.value)
    return None


async def _load_pipeline_config(provider_key: str) -> tuple[str, dict]:
    async with async_session() as db:
        fetch_mode = await _get_config(db, "fetch.mode") or {"value": "http"}
        provider_cfg = await _get_config(db, f"providers.{provider_key}")
        if not provider_cfg:
            raise ValueError(f"Provider {provider_key} not configured")

    mode = fetch_mode if isinstance(fetch_mode, str) else fetch_mode.get("value", "http")
    return mode, provider_cfg


def _cleanup_local_files(parsed):
    import os

    for item in parsed.media_items + parsed.attachment_items:
        if item.local_path and os.path.exists(item.local_path):
            os.remove(item.local_path)


async def _publish_or_schedule(
    task_id: str,
    publish_type: str,
    scheduled_at: str | None,
    provider_key: str,
    model_name: str,
    rewritten_title: str,
    rewritten_body: str,
):
    from app.services.publisher.halo_client import halo_client

    if publish_type == "immediate":
        await _update_task(task_id, status=TaskStatus.publishing, progress=85, failed_stage=None)
        await _broadcast_update(task_id, "publishing", 85, "正在发布到Halo...")

        async with async_session() as db:
            post_id = await halo_client.publish(db, rewritten_title, rewritten_body)

        await _update_task(
            task_id,
            status=TaskStatus.completed,
            progress=100,
            halo_post_id=post_id,
            error_msg=None,
            failed_stage=None,
            stage_detail="已完成",
        )
        await _broadcast_update(task_id, "completed", 100, "已完成")
        return

    scheduled_dt = datetime.fromisoformat(scheduled_at) if scheduled_at else None
    await _update_task(
        task_id,
        status=TaskStatus.scheduled,
        progress=90,
        scheduled_at=scheduled_dt,
        error_msg=None,
        failed_stage=None,
        stage_detail=f"等待定时发布: {scheduled_at}",
    )
    await _broadcast_update(task_id, "scheduled", 90, f"等待定时发布: {scheduled_at}")

    from app.services.scheduler import scheduler_service
    scheduler_service.schedule_publish(task_id, scheduled_at, provider_key, model_name)


async def _rewrite_from_source(
    task_id: str,
    provider_key: str,
    provider_cfg: dict,
    model_name: str,
    keep_citations: bool,
    publish_type: str,
    scheduled_at: str | None,
    source_title: str,
    rewrite_source: str,
    source_validation_html: str | None = None,
):
    from app.services.rewriter.factory import RewriterFactory
    from app.services.storage.minio_client import minio_storage
    current_stage = "rewriting"

    try:
        await _update_task(
            task_id,
            status=TaskStatus.rewriting,
            stage_detail="AI正在重写文章...",
            progress=55,
            error_msg=None,
            failed_stage=None,
        )
        await _broadcast_update(task_id, "rewriting", 55, "AI正在重写文章...")

        rewriter = RewriterFactory.create(
            provider_key,
            provider_cfg.get("api_key", ""),
            provider_cfg.get("base_url", ""),
            model_name,
        )
        rewriter_output = await rewriter.rewrite(rewrite_source, keep_citations)
        rewritten_title, rewritten_body = extract_title_and_body(rewriter_output, source_title)
        ok, message = validate_rewritten_html(source_validation_html or rewrite_source, rewritten_body)
        if not ok:
            raise ValueError(message)

        generated_tags = _build_generated_tags(rewritten_title, rewritten_body)

        await _update_task(
            task_id,
            rewritten_title=rewritten_title,
            rewritten_content=rewritten_body,
            generated_tags=generated_tags,
            stage_detail="正在备份重写稿到MinIO...",
            progress=75,
        )
        await _broadcast_update(task_id, "rewriting", 75, "正在备份重写稿到MinIO...")

        async with async_session() as db:
            rewritten_path = await minio_storage.save_rewritten(db, rewritten_title, rewritten_body)

        await _update_task(task_id, minio_rewritten_path=rewritten_path)
        if publish_type == "immediate":
            current_stage = "publishing"
        else:
            current_stage = "scheduled"
        await _publish_or_schedule(
            task_id=task_id,
            publish_type=publish_type,
            scheduled_at=scheduled_at,
            provider_key=provider_key,
            model_name=model_name,
            rewritten_title=rewritten_title,
            rewritten_body=rewritten_body,
        )
    except Exception as e:
        if isinstance(e, StageExecutionError):
            raise
        raise StageExecutionError(current_stage, e) from e


async def _retry_from_parsing(
    task_id: str,
    url: str,
    mode: str,
    provider_key: str,
    provider_cfg: dict,
    model_name: str,
    keep_citations: bool,
    publish_type: str,
    scheduled_at: str | None,
):
    from app.services.fetcher.service import fetcher_service
    from app.services.parser.service import parser_service
    from app.services.storage.minio_client import minio_storage
    current_stage = "fetching"

    try:
        await _update_task(
            task_id,
            status=TaskStatus.fetching,
            progress=10,
            error_msg=None,
            failed_stage=None,
            stage_detail="正在抓取网页内容...",
        )
        await _broadcast_update(task_id, "fetching", 10, "正在抓取网页内容...")
        content = await fetcher_service.fetch(url, mode=mode)

        current_stage = "parsing"
        await _update_task(
            task_id,
            status=TaskStatus.parsing,
            title=content.title,
            stage_detail="正在解析文章内容和媒体文件...",
            progress=25,
        )
        await _broadcast_update(task_id, "parsing", 25, "正在解析文章内容和媒体文件...")
        parsed = await parser_service.parse(content)

        await _update_task(
            task_id,
            original_content=parsed.rich_html or content.rich_html or parsed.clean_text,
            stage_detail="正在上传原始文件到MinIO...",
            progress=40,
        )
        await _broadcast_update(task_id, "parsing", 40, "正在上传原始文件到MinIO...")

        async with async_session() as db:
            minio_path = await minio_storage.save_original(db, parsed.title, content.html_raw, parsed)

        _cleanup_local_files(parsed)

        await _update_task(task_id, title=parsed.title, minio_original_path=minio_path)
        await _rewrite_from_source(
            task_id=task_id,
            provider_key=provider_key,
            provider_cfg=provider_cfg,
            model_name=model_name,
            keep_citations=keep_citations,
            publish_type=publish_type,
            scheduled_at=scheduled_at,
            source_title=parsed.title,
            rewrite_source=parsed.rich_html or parsed.clean_text,
            source_validation_html=parsed.rich_html,
        )
    except Exception as e:
        if isinstance(e, StageExecutionError):
            raise
        raise StageExecutionError(current_stage, e) from e


async def _retry_from_rewriting(
    task_id: str,
    task: Task,
    provider_key: str,
    provider_cfg: dict,
    model_name: str,
    keep_citations: bool,
    publish_type: str,
    scheduled_at: str | None,
):
    if not task.original_content or not task.title:
        await run_pipeline(
            task_id=task_id,
            urls=list(task.urls or []),
            provider_key=provider_key,
            model_name=model_name,
            keep_citations=keep_citations,
            publish_type=publish_type,
            scheduled_at=scheduled_at,
        )
        return

    await _rewrite_from_source(
        task_id=task_id,
        provider_key=provider_key,
        provider_cfg=provider_cfg,
        model_name=model_name,
        keep_citations=keep_citations,
        publish_type=publish_type,
        scheduled_at=scheduled_at,
        source_title=task.title,
        rewrite_source=task.original_content,
        source_validation_html=task.original_content,
    )


async def _retry_from_scheduled(
    task_id: str,
    task: Task,
    provider_key: str,
    provider_cfg: dict,
    model_name: str,
    keep_citations: bool,
    publish_type: str,
    scheduled_at: str | None,
):
    rewritten_title = task.rewritten_title or task.title
    if not rewritten_title or not task.rewritten_content:
        await _retry_from_rewriting(
            task_id=task_id,
            task=task,
            provider_key=provider_key,
            provider_cfg=provider_cfg,
            model_name=model_name,
            keep_citations=keep_citations,
            publish_type=publish_type,
            scheduled_at=scheduled_at,
        )
        return

    await _publish_or_schedule(
        task_id=task_id,
        publish_type=publish_type,
        scheduled_at=scheduled_at,
        provider_key=provider_key,
        model_name=model_name,
        rewritten_title=rewritten_title,
        rewritten_body=task.rewritten_content,
    )


async def republish_task_content(task_id: str):
    from app.services.publisher.halo_client import halo_client

    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError("Task not found")
        ensure_task_can_republish(task)

    try:
        await _update_task(
            task_id,
            status=TaskStatus.publishing,
            progress=85,
            error_msg=None,
            failed_stage=None,
            stage_detail="正在发布到Halo...",
        )
        await _broadcast_update(task_id, "publishing", 85, "正在发布到Halo...")

        async with async_session() as db:
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one()
            post_id = await halo_client.publish(db, task.rewritten_title or task.title, task.rewritten_content)

        await _update_task(
            task_id,
            status=TaskStatus.completed,
            progress=100,
            halo_post_id=post_id,
            error_msg=None,
            failed_stage=None,
            stage_detail="已完成",
        )
        await _broadcast_update(task_id, "completed", 100, "已完成")
    except Exception as e:
        logger.exception(f"Republish failed for task {task_id}")
        await _update_task(
            task_id,
            status=TaskStatus.failed,
            failed_stage="publishing",
            error_msg=str(e),
            stage_detail=f"失败: {str(e)}",
        )
        await _broadcast_update(task_id, "failed", 0, f"失败: {str(e)}")


async def retry_from_stage(task_id: str):
    current_stage = "fetching"
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError("Task not found")
        ensure_task_is_retryable(task)

        current_stage = task.failed_stage

        if task.failed_stage == "fetching":
            urls = list(task.urls or [])
            provider_key = task.model_provider
            model_name = task.model_name
            keep_citations = task.keep_citations
            publish_type = task.publish_type.value if isinstance(task.publish_type, PublishType) else str(task.publish_type)
            scheduled_at = task.scheduled_at.isoformat() if task.scheduled_at else None
        elif task.failed_stage == "parsing":
            urls = list(task.urls or [])
            provider_key = task.model_provider
            model_name = task.model_name
            keep_citations = task.keep_citations
            publish_type = task.publish_type.value if isinstance(task.publish_type, PublishType) else str(task.publish_type)
            scheduled_at = task.scheduled_at.isoformat() if task.scheduled_at else None
        elif task.failed_stage == "rewriting":
            provider_key = task.model_provider
            model_name = task.model_name
            keep_citations = task.keep_citations
            publish_type = task.publish_type.value if isinstance(task.publish_type, PublishType) else str(task.publish_type)
            scheduled_at = task.scheduled_at.isoformat() if task.scheduled_at else None
        elif task.failed_stage == "scheduled":
            provider_key = task.model_provider
            model_name = task.model_name
            keep_citations = task.keep_citations
            publish_type = task.publish_type.value if isinstance(task.publish_type, PublishType) else str(task.publish_type)
            scheduled_at = task.scheduled_at.isoformat() if task.scheduled_at else None

        if task.failed_stage == "publishing":
            await republish_task_content(task_id)
            return

    if task.failed_stage == "fetching":
        await run_pipeline(
            task_id=task_id,
            urls=urls,
            provider_key=provider_key,
            model_name=model_name,
            keep_citations=keep_citations,
            publish_type=publish_type,
            scheduled_at=scheduled_at,
        )
        return

    mode, provider_cfg = await _load_pipeline_config(provider_key)

    try:
        if task.failed_stage == "parsing":
            await _retry_from_parsing(
                task_id=task_id,
                url=urls[0],
                mode=mode,
                provider_key=provider_key,
                provider_cfg=provider_cfg,
                model_name=model_name,
                keep_citations=keep_citations,
                publish_type=publish_type,
                scheduled_at=scheduled_at,
            )
            return

        if task.failed_stage == "rewriting":
            await _retry_from_rewriting(
                task_id=task_id,
                task=task,
                provider_key=provider_key,
                provider_cfg=provider_cfg,
                model_name=model_name,
                keep_citations=keep_citations,
                publish_type=publish_type,
                scheduled_at=scheduled_at,
            )
            return

        if task.failed_stage == "scheduled":
            await _retry_from_scheduled(
                task_id=task_id,
                task=task,
                provider_key=provider_key,
                provider_cfg=provider_cfg,
                model_name=model_name,
                keep_citations=keep_citations,
                publish_type=publish_type,
                scheduled_at=scheduled_at,
            )
            return

        await run_pipeline(
            task_id=task_id,
            urls=urls,
            provider_key=provider_key,
            model_name=model_name,
            keep_citations=keep_citations,
            publish_type=publish_type,
            scheduled_at=scheduled_at,
        )
    except Exception as e:
        failed_stage = e.stage if isinstance(e, StageExecutionError) else current_stage
        error = e.original if isinstance(e, StageExecutionError) else e
        logger.exception(f"Retry from stage failed for task {task_id}")
        await _update_task(
            task_id,
            status=TaskStatus.failed,
            failed_stage=failed_stage,
            error_msg=str(error),
            stage_detail=f"失败: {str(error)}",
        )
        await _broadcast_update(task_id, "failed", 0, f"失败: {str(error)}")


async def run_pipeline(
    task_id: str,
    urls: list[str],
    provider_key: str,
    model_name: str,
    keep_citations: bool,
    publish_type: str,
    scheduled_at: str | None,
):
    current_stage = "fetching"
    try:
        await _update_task(task_id, status=TaskStatus.fetching, progress=0, error_msg=None, failed_stage=None)
        await _broadcast_update(task_id, "fetching", 0, "等待开始...")

        mode, provider_cfg = await _load_pipeline_config(provider_key)

        from app.services.fetcher.service import fetcher_service
        from app.services.parser.service import parser_service
        from app.services.storage.minio_client import minio_storage

        await _update_task(task_id, stage_detail="正在抓取网页内容...", progress=10)
        await _broadcast_update(task_id, "fetching", 10, "正在抓取网页内容...")
        content = await fetcher_service.fetch(urls[0], mode=mode)

        await _update_task(
            task_id,
            status=TaskStatus.parsing,
            title=content.title,
            stage_detail="正在解析文章内容和媒体文件...",
            progress=25,
        )
        await _broadcast_update(task_id, "parsing", 25, "正在解析文章内容和媒体文件...")
        current_stage = "parsing"
        parsed = await parser_service.parse(content)

        await _update_task(
            task_id,
            original_content=parsed.rich_html or content.rich_html or parsed.clean_text,
            stage_detail="正在上传原始文件到MinIO...",
            progress=40,
        )
        await _broadcast_update(task_id, "parsing", 40, "正在上传原始文件到MinIO...")

        async with async_session() as db:
            minio_path = await minio_storage.save_original(db, parsed.title, content.html_raw, parsed)

        _cleanup_local_files(parsed)

        await _update_task(
            task_id,
            status=TaskStatus.rewriting,
            minio_original_path=minio_path,
            stage_detail="AI正在重写文章...",
            progress=55,
        )
        await _broadcast_update(task_id, "rewriting", 55, "AI正在重写文章...")
        current_stage = "rewriting"
        rewrite_source = parsed.rich_html or parsed.clean_text
        await _rewrite_from_source(
            task_id=task_id,
            provider_key=provider_key,
            provider_cfg=provider_cfg,
            model_name=model_name,
            keep_citations=keep_citations,
            publish_type=publish_type,
            scheduled_at=scheduled_at,
            source_title=parsed.title,
            rewrite_source=rewrite_source,
            source_validation_html=parsed.rich_html,
        )

    except Exception as e:
        current_stage = e.stage if isinstance(e, StageExecutionError) else current_stage
        error = e.original if isinstance(e, StageExecutionError) else e
        logger.exception(f"Pipeline failed for task {task_id}")
        await _update_task(
            task_id,
            status=TaskStatus.failed,
            failed_stage=current_stage,
            error_msg=str(error),
            stage_detail=f"失败: {str(error)}",
        )
        await _broadcast_update(task_id, "failed", 0, f"失败: {str(error)}")
