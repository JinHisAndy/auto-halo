import sqlite3
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest
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
from app.services.tagging.service import build_tag_records, generate_tags_from_rewritten_content
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
        "- img、video、audio、source、a、pre、code、table、ul、ol、blockquote"
    )

    assert "常年写技术博客" in prompt or "技术博主" in prompt
    assert "不要改变原文的核心信息" in prompt or "补充必要的技术背景" in prompt
    assert "不得凭空编造" in prompt or "不能凭空编造" in prompt
    assert "img" in prompt_lower and "video" in prompt_lower and "pre" in prompt_lower and "code" in prompt_lower
    assert expected_preserve_tags_line in prompt
    assert "不要删除任何媒体标签" in prompt or "不要删除媒体标签" in prompt
    assert "绝对不要改写成普通文字" in prompt or "改写成普通文字" in prompt
    assert "严格遵守" in prompt or "严格遵循" in prompt
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


def test_generate_tags_from_rewritten_content_filters_generic_terms_and_keeps_useful_tags():
    tags = generate_tags_from_rewritten_content(
        "Rewritten Kubernetes Guide",
        "<article><p>Docker tuning with SSH hardening for Linux and Nginx.</p><p>容器 编排 运维 经验分享 文章 博客</p></article>",
    )

    names = [tag["name"] for tag in tags]

    assert 3 <= len(tags) <= 6
    assert "Rewritten" not in names
    assert "Guide" not in names
    assert "经验分享" not in names
    assert "文章" not in names
    assert "博客" not in names
    assert any(name in names for name in ["Kubernetes", "Docker", "SSH", "Linux", "Nginx", "容器", "编排", "运维"])
    assert all(
        tag["color"] in {"blue", "indigo", "teal", "emerald", "amber", "rose"}
        for tag in tags
    )


def test_rewritten_html_validator_rejects_heavy_media_loss_even_if_one_image_remains():
    ok, message = validate_rewritten_html(
        "<article><img src='1.jpg' /><img src='2.jpg' /><img src='3.jpg' /><img src='4.jpg' /></article>",
        "<article><p>Rewritten</p><img src='1.jpg' /></article>",
    )

    assert ok is False
    assert "image" in message.lower()


def test_pipeline_source_validates_rewritten_html_and_persists_generated_tags():
    source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    assert "validate_rewritten_html(" in source
    assert "suggest_tags(rewritten_title, body_text, existing_tag_names)" in source
    assert "from app.services.tagging.service import build_tag_records" in source
    assert "generated_tags=" in source


def test_halo_client_source_threads_tags_through_publish_and_payload_builder():
    source = Path("app/services/publisher/halo_client.py").read_text(encoding="utf-8")

    assert "tags: list[dict] | None = None" in source
    assert "tags=tags," in source


def test_publish_source_paths_thread_generated_tags_into_halo_publish_calls():
    pipeline_source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    scheduler_source = Path("app/services/scheduler.py").read_text(encoding="utf-8")

    assert "post_id = await halo_client.publish(db, rewritten_title, rewritten_body, tags=generated_tags, cover=cover)" in pipeline_source
    assert "post_id = await halo_client.publish(db, task.rewritten_title or task.title, task.rewritten_content, tags=task.generated_tags)" in scheduler_source


def test_task_list_template_contains_generated_tag_preview():
    source = Path("app/templates/task_list.html").read_text(encoding="utf-8")
    assert 'x-show="task.generated_tags && task.generated_tags.length"' in source
    assert 'x-for="tag in task.generated_tags"' in source
    assert 'x-text="tag.name"' in source


def test_task_list_template_renders_tags_with_color_classes():
    source = Path("app/templates/task_list.html").read_text(encoding="utf-8")
    assert "tag.color === 'blue'" in source
    assert "tag.color === 'indigo'" in source
    assert "tag.color === 'teal'" in source
    assert "tag.color === 'emerald'" in source
    assert "tag.color === 'amber'" in source
    assert "tag.color === 'rose'" in source
    assert "bg-blue-100 text-blue-700" in source
    assert "bg-indigo-100 text-indigo-700" in source


def test_minio_save_original_returns_url_mapping():
    source = Path("app/services/storage/minio_client.py").read_text(encoding="utf-8")
    assert "url_mapping" in source
    assert "tuple[str, dict[str, str]]" in source
    assert "_build_minio_url" in source


def test_pipeline_replaces_original_urls_with_minio_urls_in_rewritten_content():
    source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    assert "url_mapping" in source
    assert "minio_path, url_mapping = await minio_storage.save_original" in source


def test_pipeline_replaces_html_escaped_wechat_image_urls_with_minio_urls():
    from app.services.pipeline import _replace_media_urls

    original_url = "https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png&from=appmsg"
    rewritten_body = (
        '<p><img src="https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png&amp;from=appmsg"></p>'
    )

    replaced = _replace_media_urls(rewritten_body, {original_url: "https://minio.example.com/article/media/image_001.png"})

    assert "https://minio.example.com/article/media/image_001.png" in replaced
    assert "mmbiz.qpic.cn" not in replaced


def test_pipeline_replaces_plain_media_urls_with_minio_urls():
    from app.services.pipeline import _replace_media_urls

    original_url = "https://example.com/image.png"
    rewritten_body = '<p><img src="https://example.com/image.png"></p>'

    replaced = _replace_media_urls(rewritten_body, {original_url: "https://minio.example.com/article/media/image_001.png"})

    assert replaced == '<p><img src="https://minio.example.com/article/media/image_001.png"></p>'


def test_pipeline_keeps_original_wechat_image_when_minio_mapping_missing():
    from app.services.pipeline import _replace_media_urls

    html = '<img src="https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&amp;from=appmsg">'

    assert _replace_media_urls(html, {}) == html
    assert _replace_media_urls(html, None) == html


@pytest.mark.asyncio
async def test_minio_save_original_only_maps_successfully_uploaded_media(tmp_path, monkeypatch):
    from app.services.storage import minio_client

    media_file = tmp_path / "wechat-image.png"
    media_file.write_bytes(b"image-bytes")

    parsed_article = types.SimpleNamespace(
        media_items=[
            types.SimpleNamespace(
                url="https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg",
                filename="wechat-image.png",
                local_path=str(media_file),
            ),
            types.SimpleNamespace(
                url="https://mmbiz.qpic.cn/sz_mmbiz_png/def/640?wx_fmt=png&from=appmsg",
                filename="missing-image.png",
                local_path="",
            ),
        ],
        attachment_items=[],
    )

    async def fake_load_config(*_args, **_kwargs):
        return None

    monkeypatch.setattr(minio_client, "LOCAL_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setattr(minio_client.MinioStorage, "_load_config", fake_load_config)

    _, url_mapping = await minio_client.minio_storage.save_original(
        db_session=None,
        article_title="wechat-article",
        html_raw="<img src='https://mmbiz.qpic.cn/example.png'>",
        parsed_article=parsed_article,
    )

    copied_file = tmp_path / "history" / "wechat-article" / "media" / "wechat-image.png"
    assert copied_file.exists()
    assert url_mapping == {}
