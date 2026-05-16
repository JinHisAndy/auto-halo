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
