# WeChat Image Extraction Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make WeChat official account articles preserve and display images reliably, prioritizing MinIO mirroring when configured and falling back to original WeChat CDN image URLs when MinIO is unavailable or an individual upload fails.

**Architecture:** Split WeChat article handling into two paths: text extraction can still use general extractors, but image extraction and rich HTML preservation must use the raw `#js_content` DOM as the authoritative source. Build a WeChat-specific normalized rich HTML fragment, extract image candidates from that fragment, and apply MinIO replacement with per-image fallback so failed uploads never remove displayable images.

**Tech Stack:** Python, BeautifulSoup/lxml, httpx, FastAPI service layer, pytest

---

## File Structure

- Modify: `app/services/fetcher/http_fetcher.py`
  - Add WeChat-specific DOM normalization helpers.
  - Build a WeChat-preserving `rich_html` from `#js_content` instead of trusting trafilatura/readability for image retention.
  - Extract WeChat image URLs from the preserved DOM.
- Modify: `app/services/parser/service.py`
  - Preserve original image URLs when media download fails.
  - Ensure failed MinIO/download paths do not erase image display capability.
- Modify: `app/services/storage/minio_client.py`
  - Return URL mappings only for successfully uploaded files.
  - Keep original URL available as fallback when upload is missing.
- Modify: `app/services/pipeline.py`
  - Reuse `_replace_media_urls()` for normal and escaped URLs.
  - Ensure rewritten body keeps original WeChat image URL if MinIO mapping is absent.
- Modify: `tests/test_content_rewrite_enhancement.py`
  - Add regression tests for escaped URLs, WeChat DOM preservation, MinIO fallback, and no-MinIO fallback.
- Create or modify: `tests/test_root_causes.py`
  - Add focused fetcher/parser unit tests for `#js_content` image extraction behavior.
