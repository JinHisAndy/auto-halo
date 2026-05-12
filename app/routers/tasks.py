import asyncio
import ipaddress
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select

from app.db import async_session
from app.models.task import Task, TaskStatus, PublishType
from app.schemas.task import TaskCreate, TaskResponse, TaskListResponse

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

@router.get("", response_model=TaskListResponse)
async def list_tasks():
    async with async_session() as db:
        result = await db.execute(
            select(Task).order_by(Task.created_at.desc())
        )
        tasks = result.scalars().all()
    return TaskListResponse(tasks=[TaskResponse.model_validate(t) for t in tasks])

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


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