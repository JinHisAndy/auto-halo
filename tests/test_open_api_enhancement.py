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
        await db.execute(delete(Task))
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


async def _get_task_count() -> int:
    async with async_session() as db:
        result = await db.execute(select(Task))
        return len(result.scalars().all())


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
            "open_api_keys": [{"id": "k1", "key": "********", "label": "", "created_at": ""}],
            "default_model_provider": "openai",
            "default_model_name": "gpt-4.1",
        }
    )
    assert len(payload.open_api_keys) == 1
    assert payload.open_api_keys[0].key == "********"
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
    keys_raw = asyncio.run(_get_config_value("open_api.keys"))
    keys_data = json.loads(keys_raw)
    assert len(keys_data["keys"]) == 1
    assert keys_data["keys"][0]["key"] == "secret-key"


def test_post_config_persists_open_api_default_model():
    asyncio.run(_reset_system_config_table())

    client = _test_client()
    try:
        response = client.post(
            "/api/config",
            json={
                "providers": [
                    {
                        "name": "OpenAI",
                        "api_key": "secret",
                        "base_url": "https://api.openai.com/v1",
                        "models": [{"id": "gpt-4.1", "name": "GPT-4.1"}],
                    }
                ],
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
    asyncio.run(_seed_config_row("open_api.keys", {"keys": [{"id": "k1", "key": "secret-key", "label": "", "created_at": ""}]}))
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
    data = response.json()
    assert len(data["open_api_keys"]) >= 1
    assert data["default_model_provider"] == "openai"
    assert data["default_model_name"] == "gpt-4.1"


def test_post_config_preserves_existing_open_api_key_when_mask_is_submitted():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.keys", {"keys": [{"id": "k1", "key": "secret-key", "label": "", "created_at": ""}]}))

    client = _test_client()
    try:
        response = client.post(
            "/api/config",
            json={
                "providers": [],
                "fetch_mode": "http",
                "open_api_key": "********",
                "default_model_provider": None,
                "default_model_name": None,
            },
        )
    finally:
        client.close()

    assert response.status_code == 200
    keys_raw = asyncio.run(_get_config_value("open_api.keys"))
    keys_data = json.loads(keys_raw)
    assert any(k["key"] == "secret-key" for k in keys_data["keys"])


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


def test_post_open_api_tasks_rejects_invalid_publish_type_before_task_creation():
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
                "publish_type": "later",
            },
        )
    finally:
        client.close()

    assert response.status_code == 400
    assert "publish_type" in response.json()["detail"]
    assert asyncio.run(_get_task_count()) == 0


def test_post_open_api_tasks_request_model_pair_overrides_default_model():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", {"key": "secret-key"}))
    asyncio.run(
        _seed_config_row(
            "providers.anthropic",
            {
                "name": "Anthropic",
                "api_key": "anthropic-key",
                "base_url": "https://api.anthropic.com",
                "models": ["claude-3-5-sonnet"],
            },
        )
    )
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


def test_post_open_api_tasks_rejects_explicit_model_provider_when_provider_not_configured():
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

    assert response.status_code == 400
    assert "provider" in response.json()["detail"].lower()
    assert asyncio.run(_get_task_count()) == 0


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


def test_settings_template_repairs_invalid_default_selection_after_provider_changes():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "repairDefaultModelSelection()" in source
    assert '@input="repairDefaultModelSelection()"' in source
    assert "removeProvider" in source
    assert "repairDefaultModelSelection" in source


def test_settings_template_clears_stale_default_provider_and_model_when_provider_missing():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "this.defaultModelProvider = '';" in source
    assert "this.defaultModelName = '';" in source
    assert "const provider = this.getDefaultProvider();" in source


def test_open_api_docs_page_and_route_exist():
    template = Path("app/templates/open_api_docs.html")
    assert template.exists()
    source = Path("app/routers/pages.py").read_text(encoding="utf-8")
    assert '/open-api/docs' in source


def test_post_config_mask_preserve_handles_none_existing_value_gracefully():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.key", None))

    client = _test_client()
    try:
        response = client.post(
            "/api/config",
            json={
                "providers": [],
                "fetch_mode": "http",
                "open_api_key": "********",
                "default_model_provider": None,
                "default_model_name": None,
            },
        )
    finally:
        client.close()

    assert response.status_code == 200


def test_settings_template_contains_generate_key_button():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "生成 Key" in source
    assert "generateOpenApiKey" in source


def test_key_generation_endpoint_creates_new_key():
    asyncio.run(_reset_system_config_table())

    client = _test_client()
    try:
        response = client.post("/api/config/keys?label=prod")
    finally:
        client.close()

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "key" in data
    assert len(data["key"]) == 32
    assert data["label"] == "prod"

    keys_raw = asyncio.run(_get_config_value("open_api.keys"))
    keys_data = json.loads(keys_raw)
    assert len(keys_data["keys"]) == 1
    assert keys_data["keys"][0]["id"] == data["id"]


def test_delete_key_endpoint_removes_key():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.keys", {"keys": [{"id": "k1", "key": "key1", "label": "", "created_at": ""}, {"id": "k2", "key": "key2", "label": "", "created_at": ""}]}))

    client = _test_client()
    try:
        response = client.delete("/api/config/keys/k1")
    finally:
        client.close()

    assert response.status_code == 200

    keys_raw = asyncio.run(_get_config_value("open_api.keys"))
    keys_data = json.loads(keys_raw)
    assert len(keys_data["keys"]) == 1
    assert keys_data["keys"][0]["id"] == "k2"


def test_delete_nonexistent_key_returns_404():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.keys", {"keys": [{"id": "k1", "key": "key1", "label": "", "created_at": ""}]}))

    client = _test_client()
    try:
        response = client.delete("/api/config/keys/nonexistent")
    finally:
        client.close()

    assert response.status_code == 404


def test_open_api_any_key_in_list_is_accepted():
    asyncio.run(_reset_system_config_table())
    asyncio.run(_seed_config_row("open_api.keys", {"keys": [{"id": "k1", "key": "key-one", "label": "", "created_at": ""}, {"id": "k2", "key": "key-two", "label": "", "created_at": ""}]}))
    asyncio.run(_seed_config_row("open_api.default_model", {"provider": "openai", "model": "gpt-4.1"}))

    client = _test_client()
    try:
        response1 = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "key-one"},
            json={"urls": ["https://example.com/post"]},
        )
        response2 = client.post(
            "/open-api/tasks",
            headers={"X-API-Key": "key-two"},
            json={"urls": ["https://example.com/post"]},
        )
    finally:
        client.close()

    assert response1.status_code in {200, 201}
    assert response2.status_code in {200, 201}


def test_config_response_includes_keys_list_not_single_key():
    asyncio.run(_reset_system_config_table())

    client = _test_client()
    try:
        response = client.get("/api/config")
    finally:
        client.close()

    assert response.status_code == 200
    data = response.json()
    assert "open_api_keys" in data
    assert isinstance(data["open_api_keys"], list)


def test_settings_template_has_key_copy_and_delete():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "copyKey" in source
    assert "deleteKey" in source
    assert "showKey" in source


def test_settings_template_default_model_in_provider_section():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "setDefaultModel" in source
    assert "isDefaultModel" in source


def test_parser_fetched_content_type_detection_available():
    source = Path("app/services/parser/service.py").read_text(encoding="utf-8")
    assert "_classify_content_type" in source
    assert "CONTENT_TYPE_MAP" in source


def test_open_api_docs_template_includes_required_usage_examples_and_json_samples():
    source = Path("app/templates/open_api_docs.html").read_text(encoding="utf-8")

    required_markers = [
        "API Key 用法",
        "X-API-Key",
        "POST /open-api/tasks",
        "curl 示例",
        "curl -X POST",
        "Python requests 示例",
        "requests.post(",
        "JavaScript fetch 示例",
        'fetch("/open-api/tasks", {',
        '"task_id": "task-123"',
        '"status": "fetching"',
        '"trigger_source": "api"',
        '"detail": "Missing X-API-Key header"',
    ]

    for marker in required_markers:
        assert marker in source, f"Missing docs marker: {marker}"


def test_settings_template_has_global_default_model_section():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "全局默认模型" in source
    assert "onDefaultProviderChanged" in source
    assert "defaultModelsForSelection" in source
    assert "Open API 将使用此全局默认模型" in source


def test_settings_template_shows_model_chips():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "flex flex-wrap gap-1 mb-2" in source
    assert "bg-gray-100 text-gray-700 rounded-full" in source


def test_settings_repair_default_model_on_provider_change():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert '@input="repairDefaultModelSelection()"' in source
    assert '@change="repairDefaultModelSelection()"' in source
    assert "this.defaultModelProvider = ''" in source
    assert "this.defaultModelName = ''" in source


def test_settings_default_model_persists_to_open_api_config():
    source = Path("app/routers/config.py").read_text(encoding="utf-8")
    assert '"open_api.default_model"' in source
    assert '"provider": payload.default_model_provider' in source
    assert '"model": payload.default_model_name' in source
