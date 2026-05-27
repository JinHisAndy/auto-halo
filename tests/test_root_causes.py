import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import os
import types

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
    assert "halo_client.publish(db, rewritten_title, rewritten_body, tags=generated_tags, cover=cover)" in pipeline_source
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
    assert 'HALO_CONTENT_API_VERSION = "content.halo.run/v1alpha1"' in source
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


def test_wechat_js_content_prefers_data_src_images_for_rich_html():
    from bs4 import BeautifulSoup

    from app.services.fetcher.http_fetcher import _extract_wechat_rich_html

    image_url = "https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg"
    html = f'''
    <html><body>
      <div id="js_content">
        <p>intro</p>
        <img src="https://example.com/placeholder.gif" data-src="{image_url}" data-type="png" />
      </div>
    </body></html>
    '''

    rich_html = _extract_wechat_rich_html(html, "https://mp.weixin.qq.com/s/example")
    img = BeautifulSoup(rich_html, "lxml").find("img")

    assert img is not None
    assert img.get("src") == image_url
    assert "placeholder.gif" not in img.get("src", "")


def test_wechat_media_url_extraction_reads_js_content_image_urls():
    from app.services.fetcher.http_fetcher import _extract_media_urls

    image_url = "https://mmbiz.qpic.cn/sz_mmbiz_jpg/abc/640?wx_fmt=jpeg&from=appmsg"
    html = f'''
    <html><body>
      <img src="https://example.com/outside.jpg" />
      <div id="js_content">
        <img src="https://example.com/loading.gif" data-src="{image_url}" />
      </div>
    </body></html>
    '''

    urls = _extract_media_urls(html, "https://mp.weixin.qq.com/s/example")

    assert image_url in urls
    assert "https://example.com/outside.jpg" not in urls


def test_wechat_media_url_extraction_falls_back_to_picture_page_info_list():
    from app.services.fetcher.http_fetcher import _extract_media_urls

    html = '''
    <html><body>
      <div id="js_content"><p>only text, no usable image tag</p></div>
      <script>
        var picturePageInfoList = [{
          cdn_url: "https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg",
          width: "1080",
          height: "720"
        }];
      </script>
    </body></html>
    '''

    urls = _extract_media_urls(html, "https://mp.weixin.qq.com/s/example")

    assert "https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg" in urls


def test_non_wechat_media_url_extraction_does_not_use_picture_page_info_list():
    from app.services.fetcher.http_fetcher import _extract_media_urls

    html = '''
    <html><body>
      <img src="https://example.com/post-image.png" />
      <script>
        var picturePageInfoList = [{
          cdn_url: "https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg"
        }];
      </script>
    </body></html>
    '''

    urls = _extract_media_urls(html, "https://example.com/post")

    assert "https://example.com/post-image.png" in urls
    assert "https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg" not in urls


def test_wechat_rich_html_preserves_image_metadata_attributes():
    from bs4 import BeautifulSoup
    from app.services.fetcher.http_fetcher import _extract_wechat_rich_html

    html = '''
    <div id="js_content">
      <section style="text-align:center;">
        <img
          data-src="https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg"
          data-ratio="0.5"
          data-w="1080"
          data-s="300,640"
          data-imgfileid="100000385"
          data-type="png"
          data-croporisrc="https://mmbiz.qpic.cn/sz_mmbiz_png/abc/0?wx_fmt=png&from=appmsg"
          data-cropx2="1849"
          data-cropy1="16.4"
          data-cropy2="769.8"
          type="block"
        />
      </section>
    </div>
    '''

    rich_html = _extract_wechat_rich_html(html, "https://mp.weixin.qq.com/s/example")
    img = BeautifulSoup(rich_html, "lxml").find("img")

    assert img is not None
    assert img.get("data-ratio") == "0.5"
    assert img.get("data-w") == "1080"
    assert img.get("data-s") == "300,640"
    assert img.get("data-imgfileid") == "100000385"
    assert img.get("data-croporisrc") is not None
    assert img.get("data-cropx2") == "1849"
    assert img.get("data-cropy1") == "16.4"
    assert img.get("data-cropy2") == "769.8"
    assert img.get("type") == "block"


def test_non_wechat_summary_html_does_not_gain_wechat_only_attributes():
    from bs4 import BeautifulSoup
    from app.services.fetcher.http_fetcher import _process_summary_html

    rich_html = _process_summary_html(
        '<article><img src="https://example.com/image.png" data-ratio="0.5" data-imgfileid="123" /></article>',
        "https://example.com/post",
    )
    img = BeautifulSoup(rich_html, "lxml").find("img")

    assert img is not None
    assert img.get("src") == "https://example.com/image.png"


def test_fetch_http_prefers_wechat_dom_rich_html_when_extractor_drops_images(monkeypatch):
    from app.services.fetcher import http_fetcher

    class FakeResponse:
        text = """
        <html><head><title>Wechat</title></head><body>
          <div id=\"js_content\"><p>hello</p><img data-src=\"https://mmbiz.qpic.cn/a.png\" /></div>
        </body></html>
        """

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(http_fetcher.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(http_fetcher, "_extract_with_trafilatura", lambda *_: ("generic text " * 10, "<p>generic text only</p>"))
    monkeypatch.setattr(http_fetcher, "_extract_with_wechat_dom_priority", lambda *_: ("wechat text " * 10, '<div><img src="https://mmbiz.qpic.cn/a.png" /></div>'))

    fetched = asyncio.run(http_fetcher.fetch_http("https://mp.weixin.qq.com/s/example"))

    assert "mmbiz.qpic.cn/a.png" in fetched.rich_html


def test_wechat_dom_priority_keeps_image_heavy_short_posts():
    from app.services.fetcher.http_fetcher import _extract_with_wechat_dom_priority

    result = _extract_with_wechat_dom_priority(
        '<div id="js_content"><img data-src="https://mmbiz.qpic.cn/a.png" /></div>',
        "https://mp.weixin.qq.com/s/example",
    )

    assert result is not None
    text, rich_html = result
    assert text == ""
    assert "mmbiz.qpic.cn/a.png" in rich_html


def test_wechat_dom_priority_returns_none_without_js_content():
    from app.services.fetcher.http_fetcher import _extract_with_wechat_dom_priority

    result = _extract_with_wechat_dom_priority(
        '<html><body><p>generic content</p></body></html>',
        "https://mp.weixin.qq.com/s/example",
    )

    assert result is None


def test_parser_classifies_direct_media_urls_by_actual_type():
    ps = parser_service

    assert ps._classify_url("https://example.com/file.mp4?token=1") == "video"
    assert ps._classify_url("https://example.com/file.mp3?token=1") == "audio"
    assert ps._classify_url("https://example.com/file.png?token=1") == "image"
    assert ps._classify_url("https://example.com/download?file=clip.mp4") == "video"
    assert ps._classify_url("https://example.com/download?file=sound.mp3") == "audio"


def test_fetch_browser_prefers_wechat_dom_rich_html_when_extractor_drops_images(monkeypatch):
    from app.services.fetcher import browser_fetcher

    html = """
    <html><head><title>Wechat</title></head><body>
      <div id=\"js_content\"><p>hello</p><img data-src=\"https://mmbiz.qpic.cn/a.png\" /></div>
    </body></html>
    """

    class FakePage:
        async def goto(self, url, wait_until=None, timeout=None):
            return None

        async def content(self):
            return html

        async def title(self):
            return "Wechat"

    class FakeBrowser:
        async def new_page(self):
            return FakePage()

        async def close(self):
            return None

    class FakePlaywright:
        chromium = types.SimpleNamespace(launch=lambda **kwargs: _fake_launch())

    async def _fake_launch():
        return FakeBrowser()

    class FakeAsyncPlaywrightContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(
        sys.modules,
        "playwright.async_api",
        types.SimpleNamespace(async_playwright=lambda: FakeAsyncPlaywrightContext()),
    )
    monkeypatch.setattr(browser_fetcher, "_extract_with_trafilatura", lambda *_: ("generic text " * 10, "<p>generic text only</p>"))
    monkeypatch.setattr(browser_fetcher, "_extract_with_wechat_dom_priority", lambda *_: ("wechat text " * 10, '<div><img src="https://mmbiz.qpic.cn/a.png" /></div>'), raising=False)

    fetched = asyncio.run(browser_fetcher.fetch_browser("https://mp.weixin.qq.com/s/example"))

    assert "mmbiz.qpic.cn/a.png" in fetched.rich_html


def test_parser_keeps_wechat_image_item_even_when_download_fails(monkeypatch):
    wechat_image_url = "https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg"

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            raise RuntimeError("download failed")

    monkeypatch.setattr("app.services.parser.service.httpx.AsyncClient", FakeAsyncClient)

    parsed = asyncio.run(
        parser_service.parse(
            FetchedContent(
                title="t",
                html_raw=f"<img data-src='{wechat_image_url}' />",
                text_content="hello",
                rich_html=f"<img src='{wechat_image_url}' />",
                media_urls=[wechat_image_url],
            )
        )
    )

    assert len(parsed.media_items) == 1
    assert parsed.attachment_items == []
    assert parsed.media_items[0].url == wechat_image_url
    assert parsed.media_items[0].file_type == "image"
    assert parsed.media_items[0].filename == "image_000.jpg"
    assert parsed.media_items[0].local_path == ""
