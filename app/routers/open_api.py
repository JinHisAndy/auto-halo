import json

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from sqlalchemy import select

from app.db import async_session
from app.models.system_config import SystemConfig
from app.schemas.open_api import OpenApiTaskCreateRequest, OpenApiTaskCreateResponse
from app.schemas.task import TaskCreate
from app.routers.tasks import create_task

router = APIRouter(prefix="/open-api", tags=["open-api"])


async def _require_api_key(x_api_key: str | None):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    async with async_session() as db:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "open_api.key")
        )
        row = result.scalar_one_or_none()

    configured_key = None
    if row is not None:
        value = json.loads(row.value)
        configured_key = value if isinstance(value, str) else value.get("key")

    if not configured_key:
        raise HTTPException(status_code=503, detail="Open API key is not configured")

    if x_api_key != configured_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


async def _resolve_model_selection(payload: OpenApiTaskCreateRequest) -> tuple[str, str]:
    has_provider = payload.model_provider is not None
    has_model_name = payload.model_name is not None

    if has_provider and has_model_name:
        return payload.model_provider, payload.model_name

    if has_provider or has_model_name:
        raise HTTPException(
            status_code=400,
            detail="model_provider and model_name must be provided together",
        )

    async with async_session() as db:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "open_api.default_model")
        )
        row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=400, detail="Open API default model is not configured")

    value = json.loads(row.value)
    provider = value.get("provider") if isinstance(value, dict) else None
    model_name = None
    if isinstance(value, dict):
        model_name = value.get("model") or value.get("name")

    if not provider or not model_name:
        raise HTTPException(status_code=400, detail="Open API default model is not configured")

    return provider, model_name


@router.post("/tasks", response_model=OpenApiTaskCreateResponse)
async def create_open_api_task(
    payload: OpenApiTaskCreateRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> OpenApiTaskCreateResponse:
    await _require_api_key(x_api_key)
    model_provider, model_name = await _resolve_model_selection(payload)

    task = await create_task(
        TaskCreate(
            urls=payload.urls,
            keep_citations=payload.keep_citations,
            publish_type=payload.publish_type,
            scheduled_at=payload.scheduled_at,
            trigger_source="api",
            model_provider=model_provider,
            model_name=model_name,
        ),
        background_tasks,
    )

    return OpenApiTaskCreateResponse(
        task_id=task.id,
        status=task.status.value if hasattr(task.status, "value") else str(task.status),
        trigger_source="api",
        message=f"Task created for {len(payload.urls)} url(s)",
    )
