import sqlite3
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

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
from app.services import pipeline
from app.services.publisher.payloads import build_halo_payload
from app.services.tagging.service import build_tag_records
from app.services.rewriter.prompt_builder import build_rewrite_prompt
from app.services.rewriter.validation import validate_rewritten_html


def test_task_response_supports_generated_tags():
    task = TaskResponse.model_validate(
        {
            "id": "task-1",
            "title": "Original",
            "urls": ["https://example.com"],
            "status": "completed",
            "progress": 100,
            "stage_detail": "done",
            "error_msg": None,
            "keep_citations": False,
            "publish_type": "immediate",
            "scheduled_at": None,
            "minio_original_path": None,
            "minio_rewritten_path": None,
            "original_content": "<p>orig</p>",
            "rewritten_content": "<p>rewritten</p>",
            "rewritten_title": "New Title",
            "generated_tags": [{"name": "Linux", "color": "blue"}],
            "failed_stage": None,
            "trigger_source": "ui",
            "halo_post_id": "slug-1",
            "model_provider": "openai",
            "model_name": "gpt-test",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    assert task.generated_tags == [{"name": "Linux", "color": "blue"}]


def test_build_halo_payload_includes_tags_when_present():
    payload = build_halo_payload(
        "Title",
        "<article><p>Hello</p></article>",
        tags=[{"name": "Linux", "color": "blue"}],
    )

    assert "tags" in payload["post"]["spec"]
    assert payload["post"]["spec"]["tags"] == ["Linux"]


def test_build_tag_records_assigns_allowed_colors_and_limits_count():
    tags = build_tag_records(["Linux", "SSH", "Docker", "运维"])
    assert 3 <= len(tags) <= 6
    assert all("name" in tag and "color" in tag for tag in tags)
    assert all(
        tag["color"] in {"blue", "indigo", "teal", "emerald", "amber", "rose"}
        for tag in tags
    )


def test_ensure_task1_task_columns_adds_generated_tags_for_existing_sqlite_db(tmp_path):
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
                rewritten_title VARCHAR(500),
                failed_stage VARCHAR(50),
                trigger_source VARCHAR(20) NOT NULL DEFAULT 'ui',
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

    assert "generated_tags" in columns
    assert columns["generated_tags"][2] == "JSON"


def test_html_rewrite_prompt_emphasizes_technical_depth_and_html_preservation():
    prompt = build_rewrite_prompt("<article><p>Hello</p><img src='a.jpg' /></article>")
    prompt_lower = prompt.lower()
    expected_preserve_tags_line = (
        "- preserve these tags and their intent: img, video, audio, source, a, pre, code, "
        "table, ul, ol, blockquote"
    )

    assert "experienced technical blogger" in prompt_lower or "技术读者" in prompt
    assert "更丰富、更完整" in prompt or "more complete" in prompt_lower
    assert "不得编造事实" in prompt or "accurate" in prompt_lower
    assert "preserve these tags and their intent" in prompt_lower
    assert expected_preserve_tags_line in prompt
    assert "do not remove media tags" in prompt_lower or "不要删除媒体标签" in prompt
    assert "do not rewrite code blocks into prose" in prompt_lower or "不要改写成普通文字" in prompt
    assert "严格遵循以下格式" in prompt or "strictly follow" in prompt_lower
    assert "TITLE:" in prompt
    assert "BODY:" in prompt


def test_rewritten_html_validator_rejects_when_original_has_images_but_rewritten_drops_all_images():
    ok, message = validate_rewritten_html(
        "<article><p>Hello</p><img src='a.jpg' /></article>",
        "<article><p>Rewritten</p></article>",
    )

    assert ok is False
    assert "image" in message.lower()


def test_rewritten_html_validator_accepts_when_media_and_code_are_preserved():
    ok, message = validate_rewritten_html(
        "<article><pre><code>x</code></pre><img src='a.jpg' /></article>",
        "<article><pre><code>x</code></pre><img src='a.jpg' /><p>More detail</p></article>",
    )

    assert ok is True


def test_rewritten_html_validator_accepts_html_fragments_not_starting_with_tag():
    ok, message = validate_rewritten_html(
        "<article><img src='a.jpg' /><p>Hello</p></article>",
        "BODY:\n<p>Rewritten</p><img src='a.jpg' />",
    )

    assert ok is True
    assert message == "OK"


def test_rewritten_html_validator_accepts_valid_html_with_non_whitelisted_tag():
    ok, message = validate_rewritten_html(
        "<article><p>Hello</p></article>",
        "<details><summary>More</summary></details>",
    )

    assert ok is True
    assert message == "OK"


def test_rewritten_html_validator_rejects_non_html_angle_bracket_text():
    ok, message = validate_rewritten_html(
        "<article><p>Hello</p></article>",
        "1 < 2 > 1",
    )

    assert ok is False
    assert "html" in message.lower()


def test_build_generated_tags_uses_rewritten_title_and_html_body_text(monkeypatch):
    captured = {}

    def fake_build_tag_records(names):
        captured["names"] = names
        return [{"name": name, "color": "blue"} for name in names]

    monkeypatch.setattr(pipeline, "build_tag_records", fake_build_tag_records)

    tags = pipeline._build_generated_tags(
        "Rewritten Kubernetes Guide",
        "<article><p>Deep Docker tuning</p><p>SSH hardening</p></article>",
    )

    assert captured["names"] == [
        "Rewritten",
        "Kubernetes",
        "Guide",
        "Deep",
        "Docker",
        "tuning",
    ]
    assert tags == [{"name": name, "color": "blue"} for name in captured["names"]]


def test_pipeline_source_validates_rewritten_html_and_persists_generated_tags():
    source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    assert "validate_rewritten_html(" in source
    assert "_build_generated_tags(rewritten_title, rewritten_body)" in source
    assert 'BeautifulSoup(rewritten_body or "", "html.parser")' in source
    assert "generated_tags=" in source


def test_halo_client_source_threads_tags_through_publish_and_payload_builder():
    source = Path("app/services/publisher/halo_client.py").read_text(encoding="utf-8")

    assert "tags: list[dict] | None = None" in source
    assert "tags=tags," in source


def test_publish_source_paths_thread_generated_tags_into_halo_publish_calls():
    pipeline_source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    scheduler_source = Path("app/services/scheduler.py").read_text(encoding="utf-8")

    assert "post_id = await halo_client.publish(db, rewritten_title, rewritten_body, tags=generated_tags)" in pipeline_source
    assert "post_id = await halo_client.publish(db, task.rewritten_title or task.title, task.rewritten_content, tags=task.generated_tags)" in scheduler_source


def test_task_list_template_contains_generated_tag_preview():
    source = Path("app/templates/task_list.html").read_text(encoding="utf-8")
    assert 'x-show="task.generated_tags && task.generated_tags.length"' in source
    assert 'x-for="tag in task.generated_tags"' in source
    assert 'x-text="tag.name"' in source
