import json
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from app.db import async_session
from app.models.system_config import SystemConfig
from app.schemas.open_api import OpenApiTaskCreateRequest, OpenApiTaskCreateResponse

router = APIRouter(prefix="/open-api", tags=["open-api"])


async def _require_api_key(x_api_key: str | None):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

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


@router.post("/tasks")
async def create_open_api_task(
    payload: OpenApiTaskCreateRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> OpenApiTaskCreateResponse:
    await _require_api_key(x_api_key)

    return OpenApiTaskCreateResponse(
        task_id=str(uuid4()),
        status="accepted",
        trigger_source="open_api",
        message=f"Task request accepted for {len(payload.urls)} url(s)",
    )
