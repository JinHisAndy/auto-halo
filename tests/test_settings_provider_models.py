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

from fastapi.testclient import TestClient
from sqlalchemy import delete

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


def _test_client():
    return TestClient(app, raise_server_exceptions=True)


def test_post_config_persists_provider_model_lists_for_refresh():
    asyncio.run(_reset_system_config_table())

    payload = {
        "providers": [
            {
                "name": "OpenAI",
                "api_key": "secret",
                "base_url": "https://api.openai.com/v1",
                "models": [
                    {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
                    {"id": "gpt-4.1", "name": "GPT-4.1"},
                ],
            }
        ],
        "fetch_mode": "http",
        "open_api_key": None,
        "default_model_provider": "openai",
        "default_model_name": "gpt-4.1",
    }

    client = _test_client()
    try:
        save_response = client.post("/api/config", json=payload)
        load_response = client.get("/api/config")
    finally:
        client.close()

    assert save_response.status_code == 200
    assert load_response.status_code == 200
    data = load_response.json()
    assert data["providers"][0]["models"] == payload["providers"][0]["models"]
    assert data["default_model_provider"] == "openai"
    assert data["default_model_name"] == "gpt-4.1"


def test_post_config_rejects_default_model_outside_loaded_provider_models():
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
                        "models": [{"id": "gpt-4o-mini", "name": "GPT-4o Mini"}],
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

    assert response.status_code == 400
    assert "default model" in response.json()["detail"].lower()


def test_settings_template_auto_fetches_models_after_provider_connection_test():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")

    provider_function = source.split("async testProviderConnection(provider) {", 1)[1].split(
        "async saveSilent() {", 1
    )[0]
    generic_connection_function = source.split("async testConnection(service) {", 1)[1].split(
        "async testProviderConnection(provider) {", 1
    )[0]

    assert '@click="fetchProviderModels(provider)"' not in source
    assert "await this.fetchProviderModels(provider);" in provider_function
    assert "await this.fetchProviderModels(provider);" not in generic_connection_function
    assert "模型列表获取成功" in source


def test_settings_template_keeps_global_default_model_section_at_provider_bottom():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")

    assert "全局默认模型" in source
    assert "mt-4 pt-4 border-t border-gray-200" in source
    assert source.index("mt-4 pt-4 border-t border-gray-200") > source.index("从预设模板添加")
    assert "defaultModelsForSelection" in source
