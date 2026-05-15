import sys
from pathlib import Path
import asyncio
import json
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault(
    "app.config",
    types.SimpleNamespace(
        settings=types.SimpleNamespace(database_url="sqlite+aiosqlite:///:memory:")
    ),
)

from app.schemas.config import ConfigResponse, ConfigSaveRequest
from app.schemas.open_api import OpenApiTaskCreateRequest, OpenApiTaskCreateResponse
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import async_session, init_db
from app.main import app
from app.models.system_config import SystemConfig


async def _reset_system_config_table():
    await init_db()
    async with async_session() as db:
        await db.execute(delete(SystemConfig))
        await db.commit()


async def _get_config_value(key: str):
    async with async_session() as db:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        row = result.scalar_one_or_none()
        return None if row is None else row.value


async def _seed_config_row(key: str, value):
    async with async_session() as db:
        db.add(SystemConfig(key=key, value=json.dumps(value)))
        await db.commit()


def _test_client():
    return TestClient(app, raise_server_exceptions=True)


def test_open_api_task_request_accepts_optional_model_fields():
    payload = OpenApiTaskCreateRequest.model_validate(
        {
            "urls": ["https://example.com/post"],
            "publish_type": "immediate",
            "keep_citations": False,
        }
    )
    assert payload.model_provider is None
    assert payload.model_name is None


def test_config_save_request_supports_open_api_settings():
    payload = ConfigSaveRequest.model_validate(
        {
            "providers": [],
            "fetch_mode": "http",
            "open_api_key": "secret-key",
            "default_model_provider": "openai",
            "default_model_name": "gpt-4.1",
        }
    )
    assert payload.open_api_key == "secret-key"
    assert payload.default_model_provider == "openai"
    assert payload.default_model_name == "gpt-4.1"


def test_config_response_supports_open_api_settings():
    payload = ConfigResponse.model_validate(
        {
            "providers": [],
            "minio": None,
            "halo": None,
            "fetch_mode": "http",
            "open_api_key": "secret-key",
            "default_model_provider": "openai",
            "default_model_name": "gpt-4.1",
        }
    )
    assert payload.open_api_key == "secret-key"
    assert payload.default_model_provider == "openai"
    assert payload.default_model_name == "gpt-4.1"


def test_post_config_persists_open_api_key():
    asyncio.run(_reset_system_config_table())

    client = _test_client()
    try:
        response = client.post(
            "/api/config",
            json={
                "providers": [],
                "fetch_mode": "http",
                "open_api_key": "secret-key",
                "default_model_provider": None,
                "default_model_name": None,
            },
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert asyncio.run(_get_config_value("open_api.key")) == json.dumps({"key": "secret-key"})


def test_post_config_persists_open_api_default_model():
    asyncio.run(_reset_system_config_table())

    client = _test_client()
    try:
        response = client.post(
            "/api/config",
            json={
                "providers": [],
                "fetch_mode": "http",
                "open_api_key": None,
                "default_model_provider": "openai",
                "default_model_name": "gpt-4.1",
            },
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert asyncio.run(_get_config_value("open_api.default_model")) == json.dumps(
        {"provider": "openai", "model": "gpt-4.1"}
    )


def test_get_config_returns_mapped_open_api_fields():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", {"key": "secret-key"}))
    asyncio.run(
        _seed_config_row(
            "open_api.default_model",
            {"provider": "openai", "model": "gpt-4.1"},
        )
    )

    client = _test_client()
    try:
        response = client.get("/api/config")
    finally:
        client.close()

    assert response.status_code == 200
    assert response.json()["open_api_key"] == "secret-key"
    assert response.json()["default_model_provider"] == "openai"
    assert response.json()["default_model_name"] == "gpt-4.1"


def test_get_config_accepts_legacy_default_model_name_field():
    asyncio.run(_reset_system_config_table())
    asyncio.run(
        _seed_config_row(
            "open_api.default_model",
            {"provider": "openai", "name": "gpt-4.1"},
        )
    )

    client = _test_client()
    try:
        response = client.get("/api/config")
    finally:
        client.close()

    assert response.status_code == 200
    assert response.json()["default_model_provider"] == "openai"
    assert response.json()["default_model_name"] == "gpt-4.1"


def test_open_api_task_create_response_schema_fields():
    payload = OpenApiTaskCreateResponse.model_validate(
        {
            "task_id": "task-123",
            "status": "fetching",
            "trigger_source": "api",
            "message": "任务已创建",
        }
    )
    assert payload.task_id == "task-123"
    assert payload.status == "fetching"
    assert payload.trigger_source == "api"
    assert payload.message == "任务已创建"


def test_post_open_api_tasks_missing_api_key_returns_401():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", {"key": "secret-key"}))

    client = _test_client()
    try:
        response = client.post(
            "/open-api/tasks",
            json={
                "urls": ["https://example.com/post"],
            },
        )
    finally:
        client.close()

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-API-Key header"


def test_post_open_api_tasks_without_configured_key_returns_503():
    asyncio.run(_reset_system_config_table())

    client = _test_client()
    try:
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "secret-key"},
            json={
                "urls": ["https://example.com/post"],
            },
        )
    finally:
        client.close()

    assert response.status_code == 503


def test_post_open_api_tasks_with_wrong_api_key_returns_403():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", {"key": "secret-key"}))

    client = _test_client()
    try:
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "wrong-key"},
            json={
                "urls": ["https://example.com/post"],
            },
        )
    finally:
        client.close()

    assert response.status_code == 403


def test_post_open_api_tasks_with_valid_api_key_succeeds():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", {"key": "secret-key"}))

    client = _test_client()
    try:
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "secret-key"},
            json={
                "urls": ["https://example.com/post"],
            },
        )
    finally:
        client.close()

    assert response.status_code in {200, 201}
    assert response.json()["trigger_source"] == "api"
    assert response.json()["status"] == "accepted"


def test_open_api_router_contains_api_key_header_validation_and_task_endpoint():
    source = Path("app/routers/open_api.py").read_text(encoding="utf-8")
    assert 'X-API-Key' in source
    assert '@router.post("/tasks", response_model=OpenApiTaskCreateResponse)' in source
