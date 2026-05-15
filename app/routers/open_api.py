import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Header, HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.db import async_session
from app.models.system_config import SystemConfig
from app.schemas.open_api import OpenApiTaskCreateRequest, OpenApiTaskCreateResponse
from app.schemas.task import TaskCreate
from app.routers.tasks import create_task

router = APIRouter(prefix="/open-api", tags=["open-api"])
VALID_PUBLISH_TYPES = {"immediate", "scheduled"}


def _normalize_optional_model_value(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


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


async def _is_provider_configured(provider_key: str) -> bool:
    async with async_session() as db:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == f"providers.{provider_key.lower()}")
        )
        return result.scalar_one_or_none() is not None


def _validate_publish_type(publish_type: str) -> None:
    if publish_type not in VALID_PUBLISH_TYPES:
        raise HTTPException(
            status_code=400,
            detail="publish_type must be one of: immediate, scheduled",
        )


async def _resolve_model_selection(payload: OpenApiTaskCreateRequest) -> tuple[str, str]:
    provider = _normalize_optional_model_value(payload.model_provider)
    model_name = _normalize_optional_model_value(payload.model_name)

    has_provider = provider is not None
    has_model_name = model_name is not None

    if has_provider and has_model_name:
        if not await _is_provider_configured(provider):
            raise HTTPException(
                status_code=400,
                detail=f"Provider {provider} is not configured",
            )
        return provider, model_name

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

    provider = _normalize_optional_model_value(provider)
    model_name = _normalize_optional_model_value(model_name)

    if not provider or not model_name:
        raise HTTPException(status_code=400, detail="Open API default model is not configured")

    return provider, model_name


@router.post("/tasks", response_model=OpenApiTaskCreateResponse)
async def create_open_api_task(
    background_tasks: BackgroundTasks,
    payload_data: dict[str, Any] = Body(...),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> OpenApiTaskCreateResponse:
    await _require_api_key(x_api_key)

    raw_publish_type = payload_data.get("publish_type", "immediate")
    if isinstance(raw_publish_type, str):
        raw_publish_type = raw_publish_type.strip()
    _validate_publish_type(raw_publish_type)

    try:
        payload = OpenApiTaskCreateRequest.model_validate(payload_data)
    except ValidationError as exc:
        if (
            payload_data.get("publish_type") == "scheduled"
            and payload_data.get("scheduled_at") is None
        ):
            raise HTTPException(
                status_code=400,
                detail="scheduled_at is required when publish_type is scheduled",
            ) from exc
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    if payload.publish_type == "scheduled" and payload.scheduled_at is None:
        raise HTTPException(
            status_code=400,
            detail="scheduled_at is required when publish_type is scheduled",
        )

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
