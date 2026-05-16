import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select

from app.db import async_session
from app.models.task import Task, TaskStatus, PublishType
from app.models.system_config import SystemConfig
from app.services.rewriter.prompt_builder import extract_title_and_body
from app.services.rewriter.validation import validate_rewritten_html
from app.services.tagging.service import generate_tags_from_rewritten_content

logger = logging.getLogger(__name__)

MULTI_URL_MERGE_INSTRUCTION = (
    "以下是从多个来源收集的文章内容。"
    "请先综合理解全部信息，去重并处理冲突，"
    "再按清晰的逻辑结构整合成一篇统一文章，"
    "不要按来源分别输出多篇文章。\n\n"
)


class StageExecutionError(Exception):
    def __init__(self, stage: str, original: Exception):
        inner = str(original)
        if "ReadTimeout" in type(original).__name__:
            inner = f"{stage}阶段请求超时，请检查模型服务是否可用"
        elif "ConnectError" in type(original).__name__ or "ConnectTimeout" in type(original).__name__:
            inner = f"{stage}阶段连接失败，请检查网络或服务地址"
        super().__init__(inner)
        self.stage = stage
        self.original = original


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
    generated_tags: list[dict] | None = None,
):
    from app.services.publisher.halo_client import halo_client

    if publish_type == "immediate":
        await _update_task(task_id, status=TaskStatus.publishing, progress=85, failed_stage=None)
        await _broadcast_update(task_id, "publishing", 85, "正在发布到Halo...")

        async with async_session() as db:
            post_id = await halo_client.publish(db, rewritten_title, rewritten_body, tags=generated_tags)

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
    url_mapping: dict[str, str] | None = None,
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

        if url_mapping:
            for original_url, minio_url in url_mapping.items():
                rewritten_body = rewritten_body.replace(original_url, minio_url)

        ok, message = validate_rewritten_html(source_validation_html or rewrite_source, rewritten_body)
        if not ok:
            raise ValueError(message)

        generated_tags = generate_tags_from_rewritten_content(rewritten_title, rewritten_body)

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
            generated_tags=generated_tags,
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
            minio_path, url_mapping = await minio_storage.save_original(db, parsed.title, content.html_raw, parsed)

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
            url_mapping=url_mapping if url_mapping else None,
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
            post_id = await halo_client.publish(
                db,
                task.rewritten_title or task.title,
                task.rewritten_content,
                tags=task.generated_tags,
            )

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

        all_parsed_rich_html = []
        all_parsed_clean_text = []
        first_parsed = None
        minio_path = None
        all_url_mappings: dict[str, str] = {}

        for idx, url in enumerate(urls):
            content = await fetcher_service.fetch(url, mode=mode)

            await _update_task(
                task_id,
                status=TaskStatus.parsing,
                title=content.title,
                stage_detail=f"正在解析文章内容({idx+1}/{len(urls)})...",
                progress=10 + 15 * (idx + 1) // len(urls),
            )
            await _broadcast_update(task_id, "parsing", 10 + 15 * (idx + 1) // len(urls),
                                    f"正在解析文章内容({idx+1}/{len(urls)})...")
            current_stage = "parsing"
            parsed = await parser_service.parse(content)

            all_parsed_rich_html.append(parsed.rich_html or content.rich_html)
            all_parsed_clean_text.append(parsed.clean_text or content.text_content)

            async with async_session() as db:
                saved_path, url_mapping = await minio_storage.save_original(
                    db, parsed.title, content.html_raw, parsed
                )

            _cleanup_local_files(parsed)

            if url_mapping:
                all_url_mappings.update(url_mapping)

            if idx == 0:
                first_parsed = parsed
                minio_path = saved_path
                title = parsed.title

        if not first_parsed:
            raise ValueError("No content could be fetched from any URL")

        merged_rich_html = "\n<hr/>\n".join(all_parsed_rich_html)
        merged_clean_text = "\n\n---\n\n".join(all_parsed_clean_text)

        multi_url = len(urls) > 1
        if multi_url:
            rewrite_source = MULTI_URL_MERGE_INSTRUCTION + (merged_rich_html or merged_clean_text)
            source_validation_html = merged_rich_html
            original_content = merged_rich_html or merged_clean_text
        else:
            rewrite_source = first_parsed.rich_html or first_parsed.clean_text
            source_validation_html = first_parsed.rich_html
            original_content = first_parsed.rich_html or first_parsed.clean_text

        final_url_mapping = all_url_mappings if all_url_mappings else None

        await _update_task(
            task_id,
            status=TaskStatus.rewriting,
            minio_original_path=minio_path,
            original_content=original_content,
            stage_detail="AI正在重写文章...",
            progress=55,
        )
        await _broadcast_update(task_id, "rewriting", 55, "AI正在重写文章...")
        current_stage = "rewriting"
        await _rewrite_from_source(
            task_id=task_id,
            provider_key=provider_key,
            provider_cfg=provider_cfg,
            model_name=model_name,
            keep_citations=keep_citations,
            publish_type=publish_type,
            scheduled_at=scheduled_at,
            source_title=title,
            rewrite_source=rewrite_source,
            source_validation_html=source_validation_html,
            url_mapping=final_url_mapping,
        )

    except Exception as e:
        current_stage = e.stage if isinstance(e, StageExecutionError) else current_stage
        error = e if isinstance(e, StageExecutionError) else e
        logger.exception(f"Pipeline failed for task {task_id}")
        await _update_task(
            task_id,
            status=TaskStatus.failed,
            failed_stage=current_stage,
            error_msg=str(error),
            stage_detail=f"失败: {str(error)}",
        )
        await _broadcast_update(task_id, "failed", 0, f"失败: {str(error)}")
