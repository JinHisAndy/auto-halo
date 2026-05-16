import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.task import TaskResponse
from app.services.fetcher.base import FetchedContent
from app.services.parser.service import parser_service


def test_parser_classifies_file_by_content_type():
    ps = parser_service
    assert ps._classify_content_type("image/jpeg")[0] == "image"
    assert ps._classify_content_type("image/png")[0] == "image"
    assert ps._classify_content_type("video/mp4")[0] == "video"
    assert ps._classify_content_type("audio/mpeg")[0] == "audio"
    assert ps._classify_content_type("application/pdf")[0] == "attachment"


def test_parser_content_type_falls_back_to_url_extension():
    ps = parser_service
    file_type, ext = ps._classify_content_type("application/octet-stream")
    assert file_type == "attachment"
    assert ext == ".bin"


def test_parser_image_with_content_type_gets_correct_extension():
    ps = parser_service
    file_type, ext = ps._classify_content_type("image/webp")
    assert file_type == "image"
    assert ext == ".webp"


def test_parser_unknown_image_content_type_uses_mimetypes():
    ps = parser_service
    file_type, ext = ps._classify_content_type("image/x-icon")
    assert file_type == "image"


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

    assert "保留 HTML 文档的整体结构" in prompt or "HTML 文档的整体结构" in prompt
    assert "img" in prompt.lower() and "video" in prompt.lower() and "pre" in prompt.lower()
    assert "不得直接复制粘贴" in prompt or "直接复制粘贴" in prompt
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
    assert "halo_client.publish(db, rewritten_title, rewritten_body, tags=generated_tags)" in pipeline_source
    assert "parsed.clean_text" in pipeline_source


def test_pipeline_iterates_over_all_urls():
    pipeline_source = (Path(__file__).resolve().parents[1] / "app" / "services" / "pipeline.py").read_text(encoding="utf-8")

    assert "for idx, url in enumerate(urls)" in pipeline_source
    assert "idx == 0" in pipeline_source
    assert "len(urls)" in pipeline_source
    assert "all_parsed_rich_html" in pipeline_source
    assert "merged_rich_html" in pipeline_source


def test_halo_client_ensures_tags_exist_before_publish():
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "publisher" / "halo_client.py").read_text(encoding="utf-8")

    assert "async def _ensure_tags_exist(" in source
    assert "_ensure_tags_exist(client, site_url, api_token, tags)" in source
    assert "tag.halo.run/v1alpha1" in source
    assert "displayName" in source
    assert '"kind": "Tag"' in source


def test_halo_payload_uses_tag_slugs_not_display_names():
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "publisher" / "halo_client.py").read_text(encoding="utf-8")

    assert "tag_slugs = tags" in source
    assert "tag_slugs = await self._ensure_tags_exist(" in source
    assert "tags=tag_slugs" in source


def test_payload_handles_tag_strings_and_tag_dicts():
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "publisher" / "payloads.py").read_text(encoding="utf-8")

    assert 'isinstance(first, dict)' in source
    assert 'payload["post"]["spec"]["tags"] = list(tags)' in source


def test_pipeline_has_multi_url_merge_instruction():
    pipeline_source = (Path(__file__).resolve().parents[1] / "app" / "services" / "pipeline.py").read_text(encoding="utf-8")

    assert "MULTI_URL_MERGE_INSTRUCTION" in pipeline_source
    assert "以下是从多个来源收集的文章内容" in pipeline_source
    assert "multi_url = len(urls) > 1" in pipeline_source
    assert "MULTI_URL_MERGE_INSTRUCTION + (merged_rich_html" in pipeline_source


def test_pipeline_collects_all_url_mappings():
    pipeline_source = (Path(__file__).resolve().parents[1] / "app" / "services" / "pipeline.py").read_text(encoding="utf-8")

    assert "all_url_mappings: dict[str, str] = {}" in pipeline_source
    assert "all_url_mappings.update(url_mapping)" in pipeline_source
    assert "final_url_mapping = all_url_mappings if all_url_mappings else None" in pipeline_source
