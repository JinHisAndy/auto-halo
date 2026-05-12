import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select

from app.db import async_session, get_db
from app.models.task import Task, TaskStatus, PublishType
from app.schemas.task import TaskCreate, TaskResponse, TaskListResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.post("", response_model=TaskResponse)
async def create_task(payload: TaskCreate, background_tasks: BackgroundTasks):
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