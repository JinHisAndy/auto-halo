import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.config import ConfigResponse, ConfigSaveRequest
from app.schemas.open_api import OpenApiTaskCreateRequest, OpenApiTaskCreateResponse


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


def test_config_router_persists_open_api_key_and_default_model_fields():
    source = Path("app/routers/config.py").read_text(encoding="utf-8")
    assert 'open_api.key' in source
    assert 'open_api.default_model' in source


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
