import asyncio
import re
import sys
import types
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault(
    "app.config",
    types.SimpleNamespace(
        settings=types.SimpleNamespace(database_url="sqlite+aiosqlite:///:memory:")
    ),
)

from app.main import app
from app.services.publisher.halo_client import HaloClient
from app.services.publisher.payloads import build_halo_payload


def _test_client():
    return TestClient(app, raise_server_exceptions=True)


def _nav_link_class(html: str, href: str) -> str:
    matches = re.findall(rf'<a href="{re.escape(href)}" class="([^"]+)"', html)
    assert matches, f"expected nav link for {href}"
    return matches[-1]


@pytest.mark.parametrize(
    ("path", "active_href"),
    [
        ("/", "/"),
        ("/tasks", "/tasks"),
        ("/settings", "/settings"),
        ("/open-api/docs", "/open-api/docs"),
    ],
)
def test_nav_marks_current_page_active(path, active_href):
    client = _test_client()
    try:
        response = client.get(path)
    finally:
        client.close()

    assert response.status_code == 200
    active_classes = _nav_link_class(response.text, active_href)
    assert "text-indigo-600" in active_classes
    assert "border-indigo-600" in active_classes


def test_build_halo_payload_keeps_tag_slugs_in_post_spec():
    payload = build_halo_payload(
        "Tagged Title",
        "<p>body</p>",
        tags=["linux", "docker"],
    )

    assert payload["post"]["spec"]["tags"] == ["linux", "docker"]


def test_halo_client_immediate_publish_sets_publish_flag_on_create_without_publish_endpoint(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code: int, payload=None, text: str = ""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        @property
        def is_success(self):
            return 200 <= self.status_code < 300

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            calls.append(("GET", url, params, None))
            return FakeResponse(200, {"items": []})

        async def post(self, url, headers=None, json=None):
            calls.append(("POST", url, None, json))
            if url.endswith("/tags"):
                return FakeResponse(201, {"metadata": {"name": json["tag"]["metadata"]["name"]}})
            if url.endswith("/posts"):
                return FakeResponse(201, {"metadata": {"name": json["post"]["metadata"]["name"]}})
            if url.endswith("/publish"):
                return FakeResponse(404, text="not found")
            raise AssertionError(f"unexpected POST {url}")

    async def fake_load_config(self, db_session):
        return {"site_url": "https://halo.example", "api_token": "token"}

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(HaloClient, "_load_config", fake_load_config)

    post_id = asyncio.run(
        HaloClient().publish(
            None,
            "Tagged Title",
            "<p>body</p>",
            tags=[{"name": "Linux", "color": "blue"}],
        )
    )

    assert post_id == "tagged-title"
    assert [call[1] for call in calls if call[0] == "POST" and call[1].endswith("/posts")] == [
        "https://halo.example/apis/api.console.halo.run/v1alpha1/posts"
    ]
    assert [call[1] for call in calls if call[0] == "POST" and call[1].endswith("/publish")] == []

    create_payload = next(call[3] for call in calls if call[0] == "POST" and call[1].endswith("/posts"))
    assert create_payload["post"]["spec"]["publish"] is True
    assert create_payload["post"]["spec"]["tags"] == ["linux"]


def test_halo_client_uses_content_api_group_for_tag_list_and_create(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code: int, payload=None, text: str = ""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        @property
        def is_success(self):
            return 200 <= self.status_code < 300

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            calls.append(("GET", url, params, None))
            if url.endswith("/tags"):
                return FakeResponse(200, {"items": []})
            raise AssertionError(f"unexpected GET {url}")

        async def post(self, url, headers=None, json=None):
            calls.append(("POST", url, None, json))
            if url.endswith("/tags"):
                return FakeResponse(201, {"metadata": {"name": json["tag"]["metadata"]["name"]}})
            if url.endswith("/posts"):
                return FakeResponse(201, {"metadata": {"name": json["post"]["metadata"]["name"]}})
            raise AssertionError(f"unexpected POST {url}")

    async def fake_load_config(self, db_session):
        return {"site_url": "https://halo.example", "api_token": "token"}

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(HaloClient, "_load_config", fake_load_config)

    asyncio.run(
        HaloClient().publish(
            None,
            "Tagged Title",
            "<p>body</p>",
            tags=[{"name": "Linux", "color": "blue"}],
        )
    )

    tag_get = next(call for call in calls if call[0] == "GET" and call[1].endswith("/tags"))
    tag_post = next(call for call in calls if call[0] == "POST" and call[1].endswith("/tags"))

    assert tag_get[1] == "https://halo.example/apis/content.halo.run/v1alpha1/tags"
    assert tag_post[1] == "https://halo.example/apis/content.halo.run/v1alpha1/tags"
    assert tag_post[3]["tag"]["apiVersion"] == "content.halo.run/v1alpha1"


def test_halo_client_scheduled_publish_keeps_create_payload_unpublished(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code: int, payload=None, text: str = ""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        @property
        def is_success(self):
            return 200 <= self.status_code < 300

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append(("POST", url, None, json))
            if url.endswith("/posts"):
                return FakeResponse(201, {"metadata": {"name": json["post"]["metadata"]["name"]}})
            if url.endswith("/publish"):
                return FakeResponse(404, text="not found")
            raise AssertionError(f"unexpected POST {url}")

    async def fake_load_config(self, db_session):
        return {"site_url": "https://halo.example", "api_token": "token"}

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(HaloClient, "_load_config", fake_load_config)

    post_id = asyncio.run(
        HaloClient().publish(
            None,
            "Scheduled Title",
            "<p>body</p>",
            publish_time="2025-01-01T10:00:00Z",
        )
    )

    assert post_id == "scheduled-title"
    assert [call[1] for call in calls if call[0] == "POST" and call[1].endswith("/posts")] == [
        "https://halo.example/apis/api.console.halo.run/v1alpha1/posts"
    ]
    assert [call[1] for call in calls if call[0] == "POST" and call[1].endswith("/publish")] == []

    create_payload = next(call[3] for call in calls if call[0] == "POST" and call[1].endswith("/posts"))
    assert create_payload["post"]["spec"]["publish"] is False
