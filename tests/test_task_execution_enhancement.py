from datetime import datetime, timezone
from pathlib import Path
import asyncio
import sqlite3
import sys
import types

import httpx
import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault(
    "app.config",
    types.SimpleNamespace(
        settings=types.SimpleNamespace(database_url="sqlite+aiosqlite:///:memory:")
    ),
)

from app.db import async_session, engine, ensure_task1_task_columns
from app.schemas.task import TaskResponse
from app.services.rewriter.deepseek import DeepSeekRewriter
from app.services.rewriter.mofi import MofiRewriter
from app.services.rewriter.minimax import MiniMaxRewriter
from app.services.rewriter.openai_rewriter import OpenAIRewriter
from app.services.rewriter.prompt_builder import build_rewrite_prompt, extract_title_and_body
from app.services.publisher.halo_client import HaloClient
from app.services.publisher.conflict_resolution import build_retry_title
from app.services.publisher.payloads import build_halo_payload


def test_task_response_supports_retry_metadata_and_rewritten_title():
    task = TaskResponse.model_validate(
        {
            "id": "task-1",
            "title": "Original",
            "urls": ["https://example.com"],
            "status": "failed",
            "progress": 80,
            "stage_detail": "failed in publish",
            "error_msg": "boom",
            "keep_citations": False,
            "publish_type": "immediate",
            "scheduled_at": None,
            "minio_original_path": None,
            "minio_rewritten_path": None,
            "original_content": "<p>orig</p>",
            "rewritten_content": "<p>rewritten</p>",
            "rewritten_title": "Rewritten title",
            "failed_stage": "publishing",
            "trigger_source": "ui",
            "halo_post_id": "post-slug",
            "model_provider": "openai",
            "model_name": "gpt-test",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    assert task.failed_stage == "publishing"
    assert task.trigger_source == "ui"
    assert task.rewritten_title == "Rewritten title"


def test_async_session_is_initialized_at_import_time():
    assert engine is not None
    assert async_session is not None
    assert callable(async_session)


def test_ensure_task1_task_columns_adds_missing_columns_for_existing_sqlite_db(tmp_path):
    db_path = tmp_path / "legacy-tasks.db"
    sqlite_conn = sqlite3.connect(db_path)
    try:
        sqlite_conn.execute(
            """
            CREATE TABLE tasks (
                id VARCHAR(36) PRIMARY KEY,
                title VARCHAR(500),
                urls JSON NOT NULL,
                status VARCHAR(20) NOT NULL,
                progress INTEGER NOT NULL,
                stage_detail VARCHAR(500) NOT NULL,
                error_msg TEXT,
                keep_citations BOOLEAN NOT NULL,
                publish_type VARCHAR(20) NOT NULL,
                scheduled_at DATETIME,
                minio_original_path VARCHAR(500),
                minio_rewritten_path VARCHAR(500),
                original_content TEXT,
                rewritten_content TEXT,
                halo_post_id VARCHAR(200),
                model_provider VARCHAR(50) NOT NULL,
                model_name VARCHAR(100) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        sqlite_conn.commit()
    finally:
        sqlite_conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            ensure_task1_task_columns(conn)

        with engine.connect() as conn:
            columns = {
                row[1]: row for row in conn.execute(text("PRAGMA table_info(tasks)"))
            }
    finally:
        engine.dispose()

    assert "rewritten_title" in columns
    assert columns["rewritten_title"][2] == "VARCHAR(500)"
    assert "failed_stage" in columns
    assert columns["failed_stage"][2] == "VARCHAR(50)"
    assert "trigger_source" in columns
    assert columns["trigger_source"][2] == "VARCHAR(20)"
    assert columns["trigger_source"][3] == 1
    assert columns["trigger_source"][4] == "'ui'"


def test_extract_title_and_body_from_structured_llm_output():
    title, body = extract_title_and_body("TITLE: New title\nBODY:\n<p>Hello</p>", "Fallback")

    assert title == "New title"
    assert body == "<p>Hello</p>"


def test_build_retry_title_for_duplicate_publish():
    assert build_retry_title("技术文章", 1) == "技术文章（重发版）"
    assert build_retry_title("技术文章", 2) == "技术文章（重发2）"


def test_duplicate_name_retry_titles_are_available_for_publish_loop():
    titles = [build_retry_title("标题", i) for i in range(1, 4)]
    assert titles == ["标题（重发版）", "标题（重发2）", "标题（重发3）"]


def test_build_rewrite_prompt_requests_structured_title_and_body_output():
    prompt = build_rewrite_prompt("<p>Hello</p>", keep_citations=False, content_format="html")

    assert "TITLE:" in prompt
    assert "BODY:" in prompt


def test_rewriter_providers_preserve_structured_model_output(monkeypatch):
    structured_output = "TITLE: New title\nBODY:\n<p>Hello</p>"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": structured_output}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    providers = [
        OpenAIRewriter("key", "https://example.com", "model"),
        DeepSeekRewriter("key", "https://example.com", "model"),
        MofiRewriter("key", "https://example.com", "model"),
        MiniMaxRewriter("key", "https://example.com", "model"),
    ]

    for provider in providers:
        result = asyncio.run(provider.rewrite("<p>Hello</p>"))
        assert result == structured_output


def test_pipeline_source_persists_rewritten_title_and_failed_stage():
    source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    assert "extract_title_and_body(" in source
    assert "rewritten_title=" in source
    assert "rewritten_content=" in source
    assert "halo_client.publish(db, rewritten_title, rewritten_body)" in source
    assert 'current_stage = "scheduled"' in source
    assert "failed_stage=current_stage" in source


def test_task_router_contains_retry_and_republish_endpoints():
    source = Path("app/routers/tasks.py").read_text(encoding="utf-8")
    assert '@router.post("/{task_id}/retry")' in source
    assert '@router.post("/{task_id}/republish")' in source


def test_pipeline_contains_retry_and_republish_helpers():
    source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    assert "async def retry_from_stage(task_id: str):" in source
    assert "async def republish_task_content(task_id: str):" in source


def test_scheduler_source_uses_rewritten_title_fallback_and_sets_publishing_failed_stage():
    source = Path("app/services/scheduler.py").read_text(encoding="utf-8")
    assert "halo_client.publish(db, task.rewritten_title or task.title, task.rewritten_content)" in source
    assert 'task.failed_stage = "publishing"' in source


def test_build_halo_payload_keeps_retry_slug_suffix_when_title_truncates():
    long_title = "Long Title " * 20

    initial_payload = build_halo_payload(long_title, "<p>body</p>")
    retry_payload = build_halo_payload(
        build_retry_title(long_title, 1),
        "<p>body</p>",
        slug_suffix="retry-1",
    )

    assert initial_payload["post"]["metadata"]["name"] != retry_payload["post"]["metadata"]["name"]
    assert retry_payload["post"]["metadata"]["name"].endswith("-retry-1")
    assert retry_payload["post"]["spec"]["slug"].endswith("-retry-1")


def test_halo_client_retries_duplicate_names_five_times_with_distinct_retry_names(monkeypatch):
    posted_payloads = []
    long_title = "Long Title " * 20

    class FakeResponse:
        def __init__(self, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

        @property
        def is_success(self):
            return False

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            posted_payloads.append(kwargs["json"])
            return FakeResponse(409, "名称重复")

    async def fake_load_config(self, db_session):
        return {"site_url": "https://halo.example", "api_token": "token"}

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(HaloClient, "_load_config", fake_load_config)

    with pytest.raises(Exception, match="自动重试 5 次后仍失败"):
        asyncio.run(HaloClient().publish(None, long_title, "<p>body</p>"))

    retry_names = [payload["post"]["metadata"]["name"] for payload in posted_payloads]
    retry_titles = [payload["post"]["spec"]["title"] for payload in posted_payloads]

    assert len(retry_names) == 6
    assert len(set(retry_names)) == 6
    assert retry_titles[0] == long_title
    assert retry_titles[1] == build_retry_title(long_title, 1)
    assert retry_titles[-1] == build_retry_title(long_title, 5)
