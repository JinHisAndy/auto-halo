import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.task import TaskResponse
from app.services.fetcher.base import FetchedContent
from app.services.parser.service import parser_service


def test_task_response_accepts_string_halo_post_id():
    task = TaskResponse.model_validate(
        {
            "id": "task-1",
            "title": "Example",
            "urls": ["https://example.com/article"],
            "status": "completed",
            "progress": 100,
            "stage_detail": "done",
            "error_msg": None,
            "keep_citations": False,
            "publish_type": "immediate",
            "scheduled_at": None,
            "minio_original_path": None,
            "minio_rewritten_path": None,
            "original_content": "<p>original</p>",
            "rewritten_content": "<p>rewritten</p>",
            "halo_post_id": "post-slug-123",
            "model_provider": "openai",
            "model_name": "gpt-test",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    assert task.halo_post_id == "post-slug-123"


def test_parser_preserves_rich_html_for_downstream_rewrite_and_preview():
    parsed = asyncio.run(
        parser_service.parse(
            FetchedContent(
                title="Article",
                html_raw="<html><body><article><h1>Title</h1><p>Plain body</p></article></body></html>",
                text_content="Title\n\nPlain body",
                rich_html="<article><h1>Title</h1><p>Plain body</p><img src=\"hero.jpg\" /></article>",
                media_urls=[],
            )
        )
    )

    assert parsed.rich_html == "<article><h1>Title</h1><p>Plain body</p><img src=\"hero.jpg\" /></article>"


def test_html_rewrite_prompt_preserves_structure_and_media_placeholders():
    from app.services.rewriter import openai_rewriter

    build_rewrite_prompt = openai_rewriter.build_rewrite_prompt
    prompt = build_rewrite_prompt(
        "<article><h1>Title</h1><p>Hello</p><img src=\"hero.jpg\" /></article>",
        keep_citations=False,
        content_format="html",
    )

    assert "preserve overall structure" in prompt.lower()
    assert "preserve image/audio/video" in prompt.lower()
    assert "rewrite textual nodes only" in prompt.lower()
    assert "<img src=\"hero.jpg\" />" in prompt


def test_halo_payload_uses_html_content_for_publish():
    from app.services.publisher.payloads import build_halo_payload

    payload = build_halo_payload("Example Title", "<article><p>Rendered HTML</p></article>")

    assert payload["content"]["raw"] == "<article><p>Rendered HTML</p></article>"
    assert payload["content"]["content"] == "<article><p>Rendered HTML</p></article>"
    assert payload["content"]["rawType"] == "HTML"


def test_task_list_template_renders_rewritten_preview_as_html():
    template = Path(__file__).resolve().parents[1] / "app" / "templates" / "task_list.html"
    content = template.read_text(encoding="utf-8")

    assert 'x-show="previewTab===\'rewritten\'" x-html="previewContent"' in content
    assert 'renderMarkdown(previewContent)' not in content


def test_pipeline_prefers_rich_html_for_rewrite_and_publish_paths():
    pipeline_source = (Path(__file__).resolve().parents[1] / "app" / "services" / "pipeline.py").read_text(encoding="utf-8")

    assert "rewriter.rewrite(parsed.rich_html" in pipeline_source or "rewriter.rewrite(rewrite_source" in pipeline_source
    assert "halo_client.publish(db, rewritten_title, rewritten_body)" in pipeline_source
    assert "parsed.clean_text" in pipeline_source
