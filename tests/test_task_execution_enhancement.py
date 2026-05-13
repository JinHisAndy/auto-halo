from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys
import types

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault(
    "app.config",
    types.SimpleNamespace(
        settings=types.SimpleNamespace(database_url="sqlite+aiosqlite:///:memory:")
    ),
)

from app.db import ensure_task1_task_columns
from app.schemas.task import TaskResponse


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
