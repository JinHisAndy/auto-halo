from pathlib import Path
import asyncio
import sys
import types

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault(
    "app.config",
    types.SimpleNamespace(
        settings=types.SimpleNamespace(database_url="sqlite+aiosqlite:///:memory:")
    ),
)

from app.db import async_session, init_db
from app.main import app
from app.models.task import Task
from app.schemas.task import TaskBatchCreateRequest
from app.services.fetcher.base import FetchedContent
from app.services.parser.service import ParsedArticle


async def _reset_tasks_table():
    await init_db()
    async with async_session() as db:
        await db.execute(delete(Task))
        await db.commit()


async def _get_tasks():
    async with async_session() as db:
        result = await db.execute(select(Task).order_by(Task.created_at.asc()))
        return list(result.scalars().all())


def _test_client():
    return TestClient(app, raise_server_exceptions=True)


def test_task_batch_schema_accepts_multiple_task_blocks():
    payload = TaskBatchCreateRequest.model_validate(
        {
            "tasks": [
                {
                    "urls": ["https://example.com/1"],
                    "model_provider": "openai",
                    "model_name": "gpt-test",
                },
                {
                    "urls": ["https://example.com/2"],
                    "keep_citations": True,
                    "model_provider": "openai",
                    "model_name": "gpt-test",
                },
            ]
        }
    )

    assert len(payload.tasks) == 2
    assert payload.tasks[0].urls == ["https://example.com/1"]
    assert payload.tasks[1].keep_citations is True


def test_task_router_contains_batch_endpoint_and_multi_id_response_payload_shape():
    source = Path("app/routers/tasks.py").read_text(encoding="utf-8")

    assert '@router.post("/batch"' in source
    assert '"task_ids"' in source
    assert '"count"' in source


def test_post_tasks_batch_creates_one_task_per_block_and_returns_ids(monkeypatch):
    asyncio.run(_reset_tasks_table())

    captured_calls = []

    async def fake_run_pipeline(**kwargs):
        captured_calls.append(kwargs)

    import app.services.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "run_pipeline", fake_run_pipeline)

    client = _test_client()
    try:
        response = client.post(
            "/api/tasks/batch",
            json={
                "tasks": [
                    {
                        "urls": ["https://example.com/a"],
                        "model_provider": "openai",
                        "model_name": "gpt-test",
                    },
                    {
                        "urls": ["https://example.com/b"],
                        "keep_citations": True,
                        "model_provider": "openai",
                        "model_name": "gpt-test",
                    },
                ]
            },
        )
    finally:
        client.close()

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["task_ids"]) == 2
    assert len(set(data["task_ids"])) == 2

    tasks = asyncio.run(_get_tasks())
    assert len(tasks) == 2
    assert [task.urls for task in tasks] == [
        ["https://example.com/a"],
        ["https://example.com/b"],
    ]
    assert len(captured_calls) == 2
    assert [call["task_id"] for call in captured_calls] == data["task_ids"]


def test_task_create_template_uses_independent_task_blocks_and_batch_submit():
    source = Path("app/templates/task_create.html").read_text(encoding="utf-8")

    assert "tasks: [createTaskBlock()]" in source
    assert 'x-for="(task, taskIndex) in tasks"' in source
    assert 'x-model="task.urls[urlIndex]"' in source
    assert 'x-model="task.provider"' in source
    assert 'x-model="task.model"' in source
    assert 'x-model="task.keepCitations"' in source
    assert 'x-model="task.publishType"' in source
    assert 'x-model="task.scheduledAt"' in source
    assert '@click="addTask()"' in source
    assert "开始任务" in source
    assert "创建任务" not in source
    assert "'/api/tasks/batch'" in source or '"/api/tasks/batch"' in source


def test_run_pipeline_merges_multiple_urls_into_single_rewrite_input(monkeypatch):
    import app.services.pipeline as pipeline_module
    import app.services.fetcher.service as fetcher_module
    import app.services.parser.service as parser_module
    import app.services.storage.minio_client as minio_module

    events = []
    rewrite_calls = []

    fetched_content = {
        "https://example.com/one": FetchedContent(
            title="Source One",
            html_raw="<html><body>one</body></html>",
            text_content="one text",
            rich_html="<article><p>Alpha body</p></article>",
        ),
        "https://example.com/two": FetchedContent(
            title="Source Two",
            html_raw="<html><body>two</body></html>",
            text_content="two text",
            rich_html="<article><p>Beta body</p></article>",
        ),
    }

    parsed_content = {
        "Source One": ParsedArticle(
            title="Parsed Source One",
            clean_text="Alpha clean text",
            rich_html="<article><p>Alpha body</p></article>",
        ),
        "Source Two": ParsedArticle(
            title="Parsed Source Two",
            clean_text="Beta clean text",
            rich_html="<article><p>Beta body</p></article>",
        ),
    }

    async def fake_update_task(*args, **kwargs):
        return None

    async def fake_broadcast(*args, **kwargs):
        return None

    async def fake_load_pipeline_config(provider_key):
        return "http", {"api_key": "key", "base_url": "https://example.com"}

    async def fake_fetch(url, mode="http"):
        events.append(("fetch", url))
        return fetched_content[url]

    async def fake_parse(content):
        events.append(("parse", content.title))
        return parsed_content[content.title]

    async def fake_save_original(db, article_title, html_raw, parsed):
        events.append(("save_original", article_title))
        return f"minio/{article_title}", {}

    async def fake_rewrite_from_source(**kwargs):
        events.append(("rewrite", kwargs["source_title"]))
        rewrite_calls.append(kwargs)

    class _DummySession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(pipeline_module, "_update_task", fake_update_task)
    monkeypatch.setattr(pipeline_module, "_broadcast_update", fake_broadcast)
    monkeypatch.setattr(pipeline_module, "_load_pipeline_config", fake_load_pipeline_config)
    monkeypatch.setattr(pipeline_module, "_rewrite_from_source", fake_rewrite_from_source)
    monkeypatch.setattr(pipeline_module, "async_session", lambda: _DummySession())
    monkeypatch.setattr(fetcher_module.fetcher_service, "fetch", fake_fetch)
    monkeypatch.setattr(parser_module.parser_service, "parse", fake_parse)
    monkeypatch.setattr(minio_module.minio_storage, "save_original", fake_save_original)

    asyncio.run(
        pipeline_module.run_pipeline(
            task_id="task-1",
            urls=["https://example.com/one", "https://example.com/two"],
            provider_key="openai",
            model_name="gpt-test",
            keep_citations=False,
            publish_type="immediate",
            scheduled_at=None,
        )
    )

    assert rewrite_calls and len(rewrite_calls) == 1
    rewrite_source = rewrite_calls[0]["rewrite_source"]
    assert rewrite_calls[0]["source_title"] == "Parsed Source One"
    assert "Alpha body" in rewrite_source
    assert "Beta body" in rewrite_source
    assert "去重并处理冲突" in rewrite_source
    assert "不要按来源分别输出多篇文章" in rewrite_source
    assert rewrite_calls[0]["source_validation_html"].count("<article>") == 2
    assert events[-1] == ("rewrite", "Parsed Source One")
    assert [event for event in events if event[0] == "fetch"] == [
        ("fetch", "https://example.com/one"),
        ("fetch", "https://example.com/two"),
    ]
