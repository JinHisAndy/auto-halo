import asyncio
import ipaddress
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select

from app.db import async_session
from app.models.task import Task, TaskStatus, PublishType
from app.schemas.task import (
    TaskBatchCreateRequest,
    TaskBatchCreateResponse,
    TaskCreate,
    TaskListItem,
    TaskListResponse,
    TaskResponse,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _validate_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail=f"不支持的URL协议: {parsed.scheme}")
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="无效的URL")
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback:
            raise HTTPException(status_code=400, detail="不允许访问内网地址")
    except ValueError:
        pass


@router.post("", response_model=TaskResponse)
async def create_task(payload: TaskCreate, background_tasks: BackgroundTasks):
    for url in payload.urls:
        _validate_url(url)

    task = Task(
        urls=payload.urls,
        keep_citations=payload.keep_citations,
        publish_type=PublishType(payload.publish_type),
        scheduled_at=payload.scheduled_at,
        trigger_source=payload.trigger_source,
        model_provider=payload.model_provider,
        model_name=payload.model_name,
        status=TaskStatus.fetching,
        progress=0,
        stage_detail="等待开始...",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async with async_session() as db:
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = task.id

    from app.services.pipeline import run_pipeline
    background_tasks.add_task(
        run_pipeline,
        task_id=task_id,
        urls=payload.urls,
        provider_key=payload.model_provider,
        model_name=payload.model_name,
        keep_citations=payload.keep_citations,
        publish_type=payload.publish_type,
        scheduled_at=payload.scheduled_at.isoformat() if payload.scheduled_at else None,
    )

    return task


@router.post("/batch", response_model=TaskBatchCreateResponse)
async def create_tasks_batch(payload: TaskBatchCreateRequest, background_tasks: BackgroundTasks):
    for task_payload in payload.tasks:
        for url in task_payload.urls:
            _validate_url(url)

    created_tasks = []

    async with async_session() as db:
        for task_payload in payload.tasks:
            task = Task(
                urls=task_payload.urls,
                keep_citations=task_payload.keep_citations,
                publish_type=PublishType(task_payload.publish_type),
                scheduled_at=task_payload.scheduled_at,
                trigger_source=task_payload.trigger_source,
                model_provider=task_payload.model_provider,
                model_name=task_payload.model_name,
                status=TaskStatus.fetching,
                progress=0,
                stage_detail="等待开始...",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(task)
            created_tasks.append(task)

        await db.commit()

        for task in created_tasks:
            await db.refresh(task)

    from app.services.pipeline import run_pipeline

    async def _run_pipelines_concurrently():
        coros = []
        for task, task_payload in zip(created_tasks, payload.tasks):
            coros.append(run_pipeline(
                task_id=task.id,
                urls=task_payload.urls,
                provider_key=task_payload.model_provider,
                model_name=task_payload.model_name,
                keep_citations=task_payload.keep_citations,
                publish_type=task_payload.publish_type,
                scheduled_at=task_payload.scheduled_at.isoformat() if task_payload.scheduled_at else None,
            ))
        await asyncio.gather(*coros, return_exceptions=True)

    background_tasks.add_task(_run_pipelines_concurrently)

    task_ids = [task.id for task in created_tasks]
    return {"task_ids": task_ids, "count": len(task_ids)}

@router.get("", response_model=TaskListResponse)
async def list_tasks(page: int = 1, page_size: int = 10):
    if page < 1:
        page = 1
    if page_size not in (10, 20, 50):
        page_size = 10

    async with async_session() as db:
        from sqlalchemy import func
        count_result = await db.execute(select(func.count(Task.id)))
        total = count_result.scalar() or 0
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size
        result = await db.execute(
            select(Task).order_by(Task.created_at.desc()).offset(offset).limit(page_size)
        )
        paged_tasks = list(result.scalars().all())

    items = []
    for t in paged_tasks:
        items.append(TaskListItem(
            id=t.id, title=t.title, urls=list(t.urls or []), status=t.status,
            progress=t.progress, stage_detail=t.stage_detail, error_msg=t.error_msg,
            keep_citations=t.keep_citations, publish_type=t.publish_type.value if isinstance(t.publish_type, PublishType) else str(t.publish_type),
            scheduled_at=t.scheduled_at, rewritten_title=t.rewritten_title,
            generated_tags=t.generated_tags, failed_stage=t.failed_stage,
            trigger_source=t.trigger_source, halo_post_id=t.halo_post_id,
            model_provider=t.model_provider, model_name=t.model_name,
            original_content=bool(t.original_content), rewritten_content=bool(t.rewritten_content),
            has_original=bool(t.original_content), has_rewritten=bool(t.rewritten_content),
            created_at=t.created_at, updated_at=t.updated_at,
        ))

    return TaskListResponse(
        tasks=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/retry")
async def retry_task(task_id: str, background_tasks: BackgroundTasks):
    from app.services.pipeline import ensure_task_is_retryable

    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        try:
            ensure_task_is_retryable(task)
        except ValueError:
            raise HTTPException(status_code=400, detail="Task is not retryable")

    from app.services.pipeline import retry_from_stage

    background_tasks.add_task(retry_from_stage, task_id)
    return {"message": "已加入重试队列"}


@router.post("/{task_id}/republish")
async def republish_task(task_id: str, background_tasks: BackgroundTasks):
    from app.services.pipeline import ensure_task_can_republish

    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        try:
            ensure_task_can_republish(task)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    from app.services.pipeline import republish_task_content

    background_tasks.add_task(republish_task_content, task_id)
    return {"message": "已加入重发队列"}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await db.delete(task)
        await db.commit()
    return {"message": "已删除"}
