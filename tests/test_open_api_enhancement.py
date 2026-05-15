import sys
from pathlib import Path
import asyncio
import json
import types
import pytest

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
from app.models.task import Task


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


async def _get_task_model_selection(task_id: str):
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        return task.model_provider, task.model_name


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


def test_open_api_request_requires_scheduled_at_for_scheduled_publish():
    with pytest.raises(Exception):
        OpenApiTaskCreateRequest.model_validate(
            {
                "urls": ["https://example.com"],
                "publish_type": "scheduled",
            }
        )


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
    asyncio.run(
        _seed_config_row(
            "open_api.default_model",
            {"provider": "openai", "model": "gpt-4.1"},
        )
    )

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
    assert response.json()["status"] == "fetching"


def test_post_open_api_tasks_uses_default_model_when_request_omits_model_fields():
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
    assert response.json()["status"] == "fetching"


def test_post_open_api_tasks_rejects_partial_model_selection():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", {"key": "secret-key"}))

    client = _test_client()
    try:
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "secret-key"},
            json={
                "urls": ["https://example.com/post"],
                "model_provider": "openai",
            },
        )
    finally:
        client.close()

    assert response.status_code == 400
    assert "model_provider" in response.json()["detail"]


def test_post_open_api_tasks_treats_blank_model_fields_as_missing_and_uses_default():
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
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "secret-key"},
            json={
                "urls": ["https://example.com/post"],
                "model_provider": "   ",
                "model_name": "",
            },
        )
    finally:
        client.close()

    assert response.status_code in {200, 201}
    assert asyncio.run(_get_task_model_selection(response.json()["task_id"])) == (
        "openai",
        "gpt-4.1",
    )


def test_post_open_api_tasks_treats_blank_model_fields_as_missing_and_requires_default():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", {"key": "secret-key"}))

    client = _test_client()
    try:
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "secret-key"},
            json={
                "urls": ["https://example.com/post"],
                "model_provider": "",
                "model_name": " \t ",
            },
        )
    finally:
        client.close()

    assert response.status_code == 400
    assert "default model" in response.json()["detail"].lower()


def test_post_open_api_tasks_rejects_partial_nonblank_model_selection_when_other_is_blank():
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
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "secret-key"},
            json={
                "urls": ["https://example.com/post"],
                "model_provider": "openai",
                "model_name": "   ",
            },
        )
    finally:
        client.close()

    assert response.status_code == 400
    assert "model_provider" in response.json()["detail"]


def test_post_open_api_tasks_request_model_pair_overrides_default_model():
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
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "secret-key"},
            json={
                "urls": ["https://example.com/post"],
                "model_provider": "anthropic",
                "model_name": "claude-3-5-sonnet",
            },
        )
    finally:
        client.close()

    assert response.status_code in {200, 201}
    assert asyncio.run(_get_task_model_selection(response.json()["task_id"])) == (
        "anthropic",
        "claude-3-5-sonnet",
    )


def test_post_open_api_tasks_requires_default_model_when_request_omits_model_fields():
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

    assert response.status_code == 400
    assert "default model" in response.json()["detail"].lower()


def test_post_open_api_tasks_requires_scheduled_at_for_scheduled_publish():
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
        response = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "secret-key"},
            json={
                "urls": ["https://example.com/post"],
                "publish_type": "scheduled",
            },
        )
    finally:
        client.close()

    assert response.status_code == 400
    assert "scheduled_at" in response.json()["detail"]


def test_post_open_api_tasks_rejects_whitespace_only_stored_default_model():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", {"key": "secret-key"}))
    asyncio.run(
        _seed_config_row(
            "open_api.default_model",
            {"provider": "   ", "model": " \t "},
        )
    )

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

    assert response.status_code == 400
    assert "default model" in response.json()["detail"].lower()


def test_open_api_router_contains_api_key_header_validation_and_task_endpoint():
    source = Path("app/routers/open_api.py").read_text(encoding="utf-8")
    assert 'X-API-Key' in source
    assert '@router.post("/tasks", response_model=OpenApiTaskCreateResponse)' in source


def test_open_api_router_uses_default_model_when_request_model_missing_and_sets_trigger_source_api():
    source = Path("app/routers/open_api.py").read_text(encoding="utf-8")
    assert 'open_api.default_model' in source
    assert 'trigger_source="api"' in source or "trigger_source='api'" in source


def test_settings_template_contains_open_api_key_and_default_model_section():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "Open API" in source
    assert "API Key" in source
    assert "默认模型" in source or "default model" in source.lower()


def test_open_api_docs_page_and_route_exist():
    template = Path("app/templates/open_api_docs.html")
    assert template.exists()
    source = Path("app/routers/pages.py").read_text(encoding="utf-8")
    assert '/open-api/docs' in source
