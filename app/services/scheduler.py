import asyncio
import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db import async_session
from app.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()

    def schedule_publish(self, task_id: str, scheduled_at: str, provider_key: str, model_name: str):
        if isinstance(scheduled_at, str):
            run_date = datetime.fromisoformat(scheduled_at)
        else:
            run_date = scheduled_at

        self._scheduler.add_job(
            self._execute_publish,
            "date",
            run_date=run_date,
            args=[task_id],
            id=f"publish_{task_id}",
        )
        logger.info(f"Scheduled publish for task {task_id} at {run_date}")

    async def _execute_publish(self, task_id: str):
        logger.info(f"Executing scheduled publish for task {task_id}")

        from app.services.publisher.halo_client import halo_client

        async with async_session() as db:
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if not task or task.status != TaskStatus.scheduled:
                return

            task.status = TaskStatus.publishing
            task.progress = 95
            task.stage_detail = "正在发布到Halo..."
            task.updated_at = datetime.now(timezone.utc)
            await db.commit()

            from app.routers.ws import ws_manager
            await ws_manager.broadcast_task_update(task_id, "publishing", 95, "正在发布到Halo...")

            try:
                post_id = await halo_client.publish(db, task.title, task.rewritten_content)

                result = await db.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one()
                task.status = TaskStatus.completed
                task.progress = 100
                task.halo_post_id = post_id
                task.stage_detail = "已完成"
                task.updated_at = datetime.now(timezone.utc)
                await db.commit()

                await ws_manager.broadcast_task_update(task_id, "completed", 100, "已完成")
            except Exception as e:
                result = await db.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one()
                task.status = TaskStatus.failed
                task.error_msg = str(e)
                task.stage_detail = f"发布失败: {str(e)}"
                task.updated_at = datetime.now(timezone.utc)
                await db.commit()

                await ws_manager.broadcast_task_update(task_id, "failed", 0, f"发布失败: {str(e)}")

    def shutdown(self):
        self._scheduler.shutdown()


scheduler_service = SchedulerService()