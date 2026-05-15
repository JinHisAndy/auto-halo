import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.config import ConfigSaveRequest
from app.schemas.open_api import OpenApiTaskCreateRequest


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
