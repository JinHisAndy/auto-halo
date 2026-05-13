# Content Rewrite Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Auto-Halo rewriting to produce richer technical HTML output with better media preservation and automatic tag generation for Halo publishing.

**Architecture:** Keep the existing HTML-first rewrite pipeline but strengthen it with three focused additions: richer prompt construction, post-rewrite HTML validation, and a new tagging service. Publishing remains centralized in the Halo publisher layer, which will accept generated tags alongside rewritten HTML.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, existing rewriter services, BeautifulSoup/lxml, Halo publisher service, pytest

---

### Task 1: Extend task model/schema for generated tags

**Files:**
- Modify: `app/models/task.py`
- Modify: `app/schemas/task.py`
- Test: `tests/test_content_rewrite_enhancement.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from app.schemas.task import TaskResponse


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_task_response_supports_generated_tags -v`
Expected: FAIL because `generated_tags` does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
# app/models/task.py
generated_tags = Column(JSON, nullable=True)

# app/schemas/task.py
generated_tags: Optional[list[dict]] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_task_response_supports_generated_tags -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/task.py app/schemas/task.py tests/test_content_rewrite_enhancement.py
git commit -m "feat: add generated tags to task model"
```

---

### Task 2: Strengthen rewrite prompt for technical HTML output

**Files:**
- Modify: `app/services/rewriter/prompt_builder.py`
- Test: `tests/test_content_rewrite_enhancement.py`

- [ ] **Step 1: Write failing tests for prompt requirements**

```python
from app.services.rewriter.prompt_builder import build_rewrite_prompt


def test_html_rewrite_prompt_emphasizes_technical_depth_and_html_preservation():
    prompt = build_rewrite_prompt("<article><p>Hello</p><img src='a.jpg' /></article>")
    assert "experienced technical blogger" in prompt.lower() or "技术" in prompt
    assert "do not remove media tags" in prompt.lower() or "不要删除媒体标签" in prompt
    assert "code blocks" in prompt.lower() or "代码块" in prompt
    assert "more complete" in prompt.lower() or "更完整" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_html_rewrite_prompt_emphasizes_technical_depth_and_html_preservation -v`
Expected: FAIL because prompt is not strong enough yet

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/rewriter/prompt_builder.py
HTML_REWRITE_PROMPT = """
你是一位资深技术博客作者...
- 面向技术人员写作
- 内容可以更完整、更专业，但必须准确
- 保留 img/video/audio/source/a/pre/code/table/ul/ol/blockquote
- 不要删除媒体标签
- 不要把代码块改写成 prose
... 
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_html_rewrite_prompt_emphasizes_technical_depth_and_html_preservation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/rewriter/prompt_builder.py tests/test_content_rewrite_enhancement.py
git commit -m "feat: strengthen HTML rewrite prompt for technical articles"
```

---

### Task 3: Add rewritten HTML validator

**Files:**
- Create: `app/services/rewriter/validation.py`
- Test: `tests/test_content_rewrite_enhancement.py`

- [ ] **Step 1: Write failing tests for validator heuristics**

```python
from app.services.rewriter.validation import validate_rewritten_html


def test_validator_rejects_when_original_has_images_but_rewritten_drops_all_images():
    ok, message = validate_rewritten_html(
        "<article><p>Hello</p><img src='a.jpg' /></article>",
        "<article><p>Rewritten</p></article>",
    )
    assert ok is False
    assert "image" in message.lower()


def test_validator_accepts_when_media_and_code_are_preserved():
    ok, message = validate_rewritten_html(
        "<article><pre><code>x</code></pre><img src='a.jpg' /></article>",
        "<article><pre><code>x</code></pre><img src='a.jpg' /><p>More detail</p></article>",
    )
    assert ok is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_rewrite_enhancement.py -k rewritten_html_validator -v`
Expected: FAIL because validator module does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
from bs4 import BeautifulSoup


def validate_rewritten_html(original_html: str, rewritten_html: str) -> tuple[bool, str]:
    if not rewritten_html or "<" not in rewritten_html or ">" not in rewritten_html:
        return False, "rewritten body is not html"
    original = BeautifulSoup(original_html, "lxml")
    rewritten = BeautifulSoup(rewritten_html, "lxml")
    if original.find_all("img") and not rewritten.find_all("img"):
        return False, "image tags were removed"
    if original.find_all("pre") and not rewritten.find_all("pre"):
        return False, "code blocks were removed"
    if original.find_all("video") and not rewritten.find_all("video"):
        return False, "video tags were removed"
    if original.find_all("audio") and not rewritten.find_all("audio"):
        return False, "audio tags were removed"
    return True, "ok"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_rewrite_enhancement.py -k rewritten_html_validator -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/rewriter/validation.py tests/test_content_rewrite_enhancement.py
git commit -m "feat: add rewritten HTML validation heuristics"
```

---

### Task 4: Add tag generation service

**Files:**
- Create: `app/services/tagging/service.py`
- Test: `tests/test_content_rewrite_enhancement.py`

- [ ] **Step 1: Write failing tests for tag generation shape**

```python
from app.services.tagging.service import build_tag_records


def test_build_tag_records_assigns_allowed_colors_and_limits_count():
    tags = build_tag_records(["Linux", "SSH", "Docker", "运维"])
    assert 3 <= len(tags) <= 6
    assert all("name" in tag and "color" in tag for tag in tags)
    assert all(tag["color"] in {"blue", "indigo", "teal", "emerald", "amber", "rose"} for tag in tags)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_build_tag_records_assigns_allowed_colors_and_limits_count -v`
Expected: FAIL because tagging service does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
import random

ALLOWED_TAG_COLORS = ["blue", "indigo", "teal", "emerald", "amber", "rose"]


def build_tag_records(names: list[str]) -> list[dict]:
    cleaned = []
    for name in names:
        value = (name or "").strip()
        if value and value not in cleaned:
            cleaned.append(value)
    cleaned = cleaned[:6]
    if len(cleaned) < 3:
        cleaned = (cleaned + ["技术", "开发", "实践"])[:3]
    return [{"name": name, "color": random.choice(ALLOWED_TAG_COLORS)} for name in cleaned]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_build_tag_records_assigns_allowed_colors_and_limits_count -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/tagging/service.py tests/test_content_rewrite_enhancement.py
git commit -m "feat: add generated tag record service"
```

---

### Task 5: Integrate validator and generated tags into pipeline

**Files:**
- Modify: `app/services/pipeline.py`
- Test: `tests/test_content_rewrite_enhancement.py`

- [ ] **Step 1: Write failing tests for pipeline source markers**

```python
from pathlib import Path


def test_pipeline_source_validates_rewritten_html_and_persists_generated_tags():
    source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    assert "validate_rewritten_html(" in source
    assert "generated_tags=" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_pipeline_source_validates_rewritten_html_and_persists_generated_tags -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
from app.services.rewriter.validation import validate_rewritten_html
from app.services.tagging.service import build_tag_records

ok, message = validate_rewritten_html(parsed.rich_html or rewrite_source, rewritten_body)
if not ok:
    raise ValueError(message)

generated_tags = build_tag_records([...])
await _update_task(task_id, rewritten_title=rewritten_title, rewritten_content=rewritten_body, generated_tags=generated_tags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_pipeline_source_validates_rewritten_html_and_persists_generated_tags -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/pipeline.py tests/test_content_rewrite_enhancement.py
git commit -m "feat: validate rewritten HTML and persist generated tags"
```

---

### Task 6: Extend Halo publisher payload for tags

**Files:**
- Modify: `app/services/publisher/payloads.py`
- Modify: `app/services/publisher/halo_client.py`
- Test: `tests/test_content_rewrite_enhancement.py`

- [ ] **Step 1: Write failing test for payload tag inclusion**

```python
from app.services.publisher.payloads import build_halo_payload


def test_build_halo_payload_includes_tags_when_present():
    payload = build_halo_payload(
        "Title",
        "<article><p>Hello</p></article>",
        tags=[{"name": "Linux", "color": "blue"}],
    )
    assert "tags" in payload["post"]["spec"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_build_halo_payload_includes_tags_when_present -v`
Expected: FAIL because payload builder has no tags parameter

- [ ] **Step 3: Write minimal implementation**

```python
def build_halo_payload(title: str, content_html: str, publish_time=None, tags: list[dict] | None = None) -> dict:
    ...
    payload = {...}
    payload["post"]["spec"]["tags"] = [tag["name"] for tag in (tags or [])]
    return payload
```

```python
# halo_client.py
payload = self._build_payload(title, content_html, publish_time, tags=generated_tags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_build_halo_payload_includes_tags_when_present -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/publisher/payloads.py app/services/publisher/halo_client.py tests/test_content_rewrite_enhancement.py
git commit -m "feat: include generated tags in Halo publish payload"
```

---

### Task 7: Show generated tags in task list

**Files:**
- Modify: `app/templates/task_list.html`
- Test: `tests/test_content_rewrite_enhancement.py`

- [ ] **Step 1: Write failing test for tag preview UI marker**

```python
from pathlib import Path


def test_task_list_template_contains_generated_tag_preview():
    source = Path("app/templates/task_list.html").read_text(encoding="utf-8")
    assert "generated_tags" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_task_list_template_contains_generated_tag_preview -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```html
<div class="flex flex-wrap gap-2 mt-2" x-show="task.generated_tags && task.generated_tags.length">
  <template x-for="tag in task.generated_tags" :key="tag.name">
    <span class="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-700" x-text="tag.name"></span>
  </template>
</div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_rewrite_enhancement.py::test_task_list_template_contains_generated_tag_preview -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/task_list.html tests/test_content_rewrite_enhancement.py
git commit -m "feat: show generated tags in task list"
```

---

### Task 8: Final regression verification

**Files:**
- Test: `tests/test_content_rewrite_enhancement.py`

- [ ] **Step 1: Run focused enhancement suite**

Run: `pytest tests/test_content_rewrite_enhancement.py -v`
Expected: all tests PASS

- [ ] **Step 2: Run full project suite**

Run: `pytest -q`
Expected: full suite PASS

- [ ] **Step 3: Commit final fixups if needed**

```bash
git add -A
git commit -m "fix: finalize content rewrite enhancement regressions"
```
