# WeChat Image Attribute Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve richer WeChat image metadata in extracted rich HTML while keeping non-WeChat blog extraction behavior unchanged.

**Architecture:** Restrict the enhancement to the WeChat-specific sanitization path in `http_fetcher.py`. Expand the WeChat image attribute allowlist and add tests proving WeChat attributes survive while normal blog extraction still behaves as before.

**Tech Stack:** Python, BeautifulSoup/lxml, pytest

---

## File Structure

- Modify: `app/services/fetcher/http_fetcher.py`
  - Expand WeChat image attribute preservation.
- Modify: `tests/test_root_causes.py`
  - Add regression tests for WeChat attribute preservation and non-WeChat non-regression.

---

### Task 1: Preserve WeChat image metadata attributes without affecting normal blog extraction

**Files:**
- Modify: `tests/test_root_causes.py`
- Modify: `app/services/fetcher/http_fetcher.py`

- [ ] **Step 1: Write the failing tests**

```python
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
    assert img.get("data-imgfileid") == "100000385"
    assert img.get("data-croporisrc") is not None


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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_root_causes.py -k "preserves_image_metadata_attributes or does_not_gain_wechat_only_attributes" -v`

Expected: FAIL because those WeChat metadata attributes are not yet preserved.

- [ ] **Step 3: Implement minimal allowlist expansion**

```python
"img": [
    "src", "data-src", "data-original", "data-type", "alt", "width", "height", "class", "style",
    "data-ratio", "data-w", "data-s", "data-imgfileid",
    "data-croporisrc", "data-cropx2", "data-cropy1", "data-cropy2", "type",
]
```

Keep the change scoped to WeChat-safe rich HTML preservation.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_root_causes.py -k "preserves_image_metadata_attributes or does_not_gain_wechat_only_attributes" -v`

Expected: PASS

- [ ] **Step 5: Run broader regression checks**

Run: `python -m pytest tests/test_root_causes.py tests/test_content_rewrite_enhancement.py -k "wechat or media_urls or image_metadata or minio or escaped" -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/fetcher/http_fetcher.py tests/test_root_causes.py docs/superpowers/plans/2026-05-27-wechat-image-attribute-preservation.md
git commit -m "fix: preserve wechat image metadata attributes"
```
