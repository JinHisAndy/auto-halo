# WeChat Image Dimension Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backfill `width` and `height` attributes into WeChat `rich_html` image nodes from script-side image metadata, while keeping non-WeChat blog extraction unchanged.

**Architecture:** Parse `cdn_url`, `width`, and `height` from WeChat script metadata and use it only in the WeChat-specific `rich_html` path. Match metadata entries to `<img>` nodes by normalized URL and only fill `width/height` when the node does not already provide them.

**Tech Stack:** Python, BeautifulSoup/lxml, regex, pytest

---

## File Structure

- Modify: `app/services/fetcher/http_fetcher.py`
  - Add WeChat script metadata parsing and image dimension backfill helper.
- Modify: `tests/test_root_causes.py`
  - Add TDD coverage for WeChat-only width/height backfill and non-WeChat non-regression.

---

### Task 1: Backfill WeChat image width/height from script metadata only for WeChat pages

**Files:**
- Modify: `tests/test_root_causes.py`
- Modify: `app/services/fetcher/http_fetcher.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_wechat_rich_html_backfills_width_and_height_from_picture_page_info_list():
    from bs4 import BeautifulSoup
    from app.services.fetcher.http_fetcher import _extract_wechat_rich_html

    html = '''
    <html><body>
      <div id="js_content">
        <img data-src="https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg" />
      </div>
      <script>
        var picturePageInfoList = [{
          cdn_url: "https://mmbiz.qpic.cn/sz_mmbiz_png/abc/640?wx_fmt=png&from=appmsg",
          width: "1080",
          height: "720"
        }];
      </script>
    </body></html>
    '''

    rich_html = _extract_wechat_rich_html(html, "https://mp.weixin.qq.com/s/example")
    img = BeautifulSoup(rich_html, "lxml").find("img")

    assert img is not None
    assert img.get("width") == "1080"
    assert img.get("height") == "720"


def test_non_wechat_rich_html_does_not_backfill_dimensions_from_picture_page_info_list():
    from bs4 import BeautifulSoup
    from app.services.fetcher.http_fetcher import _process_summary_html

    rich_html = _process_summary_html(
        '<article><img src="https://example.com/post-image.png" /></article>',
        "https://example.com/post",
    )
    img = BeautifulSoup(rich_html, "lxml").find("img")

    assert img is not None
    assert img.get("width") is None
    assert img.get("height") is None
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_root_causes.py -k "backfills_width_and_height or does_not_backfill_dimensions" -v`

Expected: FAIL because script-side dimensions are not yet applied.

- [ ] **Step 3: Implement minimal WeChat-only dimension backfill**

```python
def _extract_wechat_picture_page_info(html: str) -> dict[str, tuple[str, str]]:
    ...


def _normalise_media_url(url: str) -> str:
    return url.split("#", 1)[0]


def _backfill_wechat_image_dimensions(rich_html: str, html: str) -> str:
    ...
```

Call the helper only from `_extract_wechat_rich_html()`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_root_causes.py -k "backfills_width_and_height or does_not_backfill_dimensions" -v`

Expected: PASS

- [ ] **Step 5: Run broader regression checks**

Run: `python -m pytest tests/test_root_causes.py tests/test_content_rewrite_enhancement.py -k "wechat or media_urls or image_metadata or width or height or minio or escaped" -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/fetcher/http_fetcher.py tests/test_root_causes.py docs/superpowers/plans/2026-05-27-wechat-image-dimension-backfill.md
git commit -m "fix: backfill wechat image dimensions from script metadata"
```
