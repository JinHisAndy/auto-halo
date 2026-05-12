import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import async_session
from app.models.task import Task, TaskStatus, PublishType
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


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


async def run_pipeline(
    task_id: str,
    urls: list[str],
    provider_key: str,
    model_name: str,
    keep_citations: bool,
    publish_type: str,
    scheduled_at: str | None,
):
    try:
        task = await _update_task(task_id, status=TaskStatus.fetching, progress=0)
        await _broadcast_update(task_id, "fetching", 0, "等待开始...")

        async with async_session() as db:
            fetch_mode = await _get_config(db, "fetch.mode") or {"value": "http"}
            provider_cfg = await _get_config(db, f"providers.{provider_key}")
            if not provider_cfg:
                raise ValueError(f"Provider {provider_key} not configured")

        mode = fetch_mode if isinstance(fetch_mode, str) else fetch_mode.get("value", "http")

        from app.services.fetcher.service import fetcher_service
        from app.services.parser.service import parser_service
        from app.services.storage.minio_client import minio_storage
        from app.services.publisher.halo_client import halo_client

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
        parsed = await parser_service.parse(content)

        await _update_task(
            task_id,
            original_content=parsed.clean_text,
            stage_detail="正在上传原始文件到MinIO...",
            progress=40,
        )
        await _broadcast_update(task_id, "parsing", 40, "正在上传原始文件到MinIO...")

        async with async_session() as db:
            minio_path = await minio_storage.save_original(db, parsed.title, content.html_raw, parsed)

        import os
        for item in parsed.media_items + parsed.attachment_items:
            if item.local_path and os.path.exists(item.local_path):
                os.remove(item.local_path)

        await _update_task(
            task_id,
            status=TaskStatus.rewriting,
            minio_original_path=minio_path,
            stage_detail="AI正在重写文章...",
            progress=55,
        )
        await _broadcast_update(task_id, "rewriting", 55, "AI正在重写文章...")

        from app.services.rewriter.factory import RewriterFactory
        rewriter = RewriterFactory.create(
            provider_key,
            provider_cfg.get("api_key", ""),
            provider_cfg.get("base_url", ""),
            model_name,
        )
        rewritten = await rewriter.rewrite(parsed.clean_text, keep_citations)

        await _update_task(
            task_id,
            rewritten_content=rewritten,
            stage_detail="正在备份重写稿到MinIO...",
            progress=75,
        )
        await _broadcast_update(task_id, "rewriting", 75, "正在备份重写稿到MinIO...")

        async with async_session() as db:
            rewritten_path = await minio_storage.save_rewritten(db, parsed.title, rewritten)

        await _update_task(task_id, minio_rewritten_path=rewritten_path)

        if publish_type == "immediate":
            await _update_task(task_id, status=TaskStatus.publishing, progress=85)
            await _broadcast_update(task_id, "publishing", 85, "正在发布到Halo...")

            async with async_session() as db:
                post_id = await halo_client.publish(db, parsed.title, rewritten)

            await _update_task(
                task_id,
                status=TaskStatus.completed,
                progress=100,
                halo_post_id=post_id,
                stage_detail="已完成",
            )
            await _broadcast_update(task_id, "completed", 100, "已完成")
        else:
            scheduled_dt = datetime.fromisoformat(scheduled_at) if scheduled_at else None
            await _update_task(
                task_id,
                status=TaskStatus.scheduled,
                progress=90,
                scheduled_at=scheduled_dt,
                stage_detail=f"等待定时发布: {scheduled_at}",
            )
            await _broadcast_update(task_id, "scheduled", 90, f"等待定时发布: {scheduled_at}")

            from app.services.scheduler import scheduler_service
            scheduler_service.schedule_publish(task_id, scheduled_at, provider_key, model_name)

    except Exception as e:
        logger.exception(f"Pipeline failed for task {task_id}")
        await _update_task(
            task_id,
            status=TaskStatus.failed,
            error_msg=str(e),
            stage_detail=f"失败: {str(e)}",
        )
        await _broadcast_update(task_id, "failed", 0, f"失败: {str(e)}")