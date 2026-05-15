import json
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import async_session
from app.models.system_config import SystemConfig
from app.schemas.config import (
    ConfigSaveRequest,
    ConfigResponse,
    ProviderConfig,
    MinioConfig,
    HaloConfig,
    TestConnectionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])
MASKED_OPEN_API_KEY = "********"


def _mask_open_api_key(value: str | None) -> str | None:
    return MASKED_OPEN_API_KEY if value else None


async def _get_config_row(db, key: str) -> SystemConfig | None:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    return result.scalar_one_or_none()


@router.get("", response_model=ConfigResponse)
async def get_config():
    async with async_session() as db:
        result = await db.execute(select(SystemConfig))
        rows = result.scalars().all()

    providers = []
    minio_cfg = None
    halo_cfg = None
    fetch_mode = "http"
    open_api_key = None
    default_model_provider = None
    default_model_name = None

    for row in rows:
        value = json.loads(row.value)
        if row.key.startswith("providers."):
            providers.append(ProviderConfig(**value))
        elif row.key == "minio":
            minio_cfg = MinioConfig(**value)
        elif row.key == "halo":
            halo_cfg = HaloConfig(**value)
        elif row.key == "fetch.mode":
            fetch_mode = value if isinstance(value, str) else value.get("value", "http")
        elif row.key == "open_api.key":
            configured_key = value if isinstance(value, str) else value.get("key")
            open_api_key = _mask_open_api_key(configured_key)
        elif row.key == "open_api.default_model":
            default_model_provider = value.get("provider")
            default_model_name = value.get("model") or value.get("name")

    return ConfigResponse(
        providers=providers,
        minio=minio_cfg,
        halo=halo_cfg,
        fetch_mode=fetch_mode,
        open_api_key=open_api_key,
        default_model_provider=default_model_provider,
        default_model_name=default_model_name,
    )

@router.post("")
async def save_config(payload: ConfigSaveRequest):
    async with async_session() as db:
        existing = await db.execute(select(SystemConfig))
        existing_keys = {r.key for r in existing.scalars().all()}

        provider_keys = set()
        for provider in payload.providers:
            key = f"providers.{provider.name.lower()}"
            provider_keys.add(key)
            value = json.dumps(provider.model_dump())
            result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                db.add(SystemConfig(key=key, value=value))

        for old_key in existing_keys:
            if old_key.startswith("providers.") and old_key not in provider_keys:
                row = await db.execute(select(SystemConfig).where(SystemConfig.key == old_key))
                row = row.scalar_one_or_none()
                if row:
                    await db.delete(row)

        if payload.minio:
            key = "minio"
            value = json.dumps(payload.minio.model_dump())
            result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                db.add(SystemConfig(key=key, value=value))

        if payload.halo:
            key = "halo"
            value = json.dumps(payload.halo.model_dump())
            result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                db.add(SystemConfig(key=key, value=value))

        key = "fetch.mode"
        value = json.dumps({"value": payload.fetch_mode})
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=key, value=value))

        key = "open_api.key"
        persisted_open_api_key = payload.open_api_key
        if payload.open_api_key == MASKED_OPEN_API_KEY:
            existing_open_api_key_row = await _get_config_row(db, key)
            if existing_open_api_key_row is not None:
                existing_open_api_key_value = json.loads(existing_open_api_key_row.value)
                persisted_open_api_key = (
                    existing_open_api_key_value
                    if isinstance(existing_open_api_key_value, str)
                    else existing_open_api_key_value.get("key")
                )

        value = json.dumps({"key": persisted_open_api_key})
        row = await _get_config_row(db, key)
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=key, value=value))

        key = "open_api.default_model"
        value = json.dumps(
            {
                "provider": payload.default_model_provider,
                "model": payload.default_model_name,
            }
        )
        row = await _get_config_row(db, key)
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=key, value=value))

        await db.commit()

    return {"message": "配置已保存"}

@router.post("/test/{service}", response_model=TestConnectionResponse)
async def test_connection(service: str):
    if service == "minio":
        async with async_session() as db:
            from app.services.storage.minio_client import minio_storage
            success, message = await minio_storage.test_connection(db)
    elif service == "halo":
        async with async_session() as db:
            from app.services.publisher.halo_client import halo_client
            success, message = await halo_client.test_connection(db)
    elif service.startswith("provider."):
        provider_key = service.split(".", 1)[1]
        async with async_session() as db:
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.key == f"providers.{provider_key}")
            )
            row = result.scalar_one_or_none()
            if not row:
                raise HTTPException(status_code=404, detail="Provider not configured")
            cfg = json.loads(row.value)
            from app.services.rewriter.factory import RewriterFactory
            rewriter = RewriterFactory.create(
                provider_key, cfg.get("api_key", ""), cfg.get("base_url", ""),
                cfg.get("models", [""])[0] if cfg.get("models") else "default",
            )
            ok = await rewriter.test_connection()
            success, message = (True, "模型供应商连接成功") if ok else (False, "模型供应商连接失败")
    else:
        raise HTTPException(status_code=400, detail="Unknown service")
    return TestConnectionResponse(success=success, message=message)

@router.post("/models/{provider_key}")
async def list_models(provider_key: str):
    async with async_session() as db:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == f"providers.{provider_key}")
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Provider not configured")
        cfg = json.loads(row.value)
        from app.services.rewriter.factory import RewriterFactory
        rewriter = RewriterFactory.create(
            provider_key, cfg.get("api_key", ""), cfg.get("base_url", ""),
            cfg.get("models", [""])[0] if cfg.get("models") else "default",
        )
        try:
            models = await rewriter.list_models()
            return {"models": models}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")
