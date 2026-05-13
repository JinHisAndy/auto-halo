# Task Execution Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add retry/republish workflow support, rewritten title handling, Halo duplicate-name auto-recovery, and task source distinction to Auto-Halo.

**Architecture:** Extend the task model with explicit retry metadata and rewritten title storage, then refactor the pipeline into resumable stage-oriented helpers while keeping the existing single orchestrator as the entry point. UI changes stay in the task list page and task router gains dedicated retry/republish endpoints.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, Jinja2 + Alpine.js, existing pipeline/publisher/rewriter services, pytest

---

### Task 1: Extend task model and schemas

**Files:**
- Modify: `app/models/task.py`
- Modify: `app/schemas/task.py`
- Test: `tests/test_task_execution_enhancement.py`

- [ ] **Step 1: Write failing test for new task fields**

```python
from datetime import datetime, timezone

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_execution_enhancement.py::test_task_response_supports_retry_metadata_and_rewritten_title -v`
Expected: FAIL because fields are missing from `TaskResponse`

- [ ] **Step 3: Implement minimal model/schema changes**

```python
# app/models/task.py
failed_stage = Column(String(50), nullable=True)
trigger_source = Column(String(20), nullable=False, default="ui")
rewritten_title = Column(String(500), nullable=True)

# app/schemas/task.py
failed_stage: Optional[str]
trigger_source: str
rewritten_title: Optional[str]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_execution_enhancement.py::test_task_response_supports_retry_metadata_and_rewritten_title -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/task.py app/schemas/task.py tests/test_task_execution_enhancement.py
git commit -m "feat: add retry metadata and rewritten title fields"
```

---

### Task 2: Add rewritten title parsing and duplicate-title helpers

**Files:**
- Create: `app/services/publisher/conflict_resolution.py`
- Modify: `app/services/rewriter/prompt_builder.py`
- Modify: `app/services/rewriter/deepseek.py`
- Modify: `app/services/rewriter/mofi.py`
- Modify: `app/services/rewriter/minimax.py`
- Modify: `app/services/rewriter/openai_rewriter.py`
- Test: `tests/test_task_execution_enhancement.py`

- [ ] **Step 1: Write failing tests for title/body extraction and duplicate title generation**

```python
from app.services.publisher.conflict_resolution import build_retry_title
from app.services.rewriter.prompt_builder import extract_title_and_body


def test_extract_title_and_body_from_structured_llm_output():
    title, body = extract_title_and_body("TITLE: New title\nBODY:\n<p>Hello</p>", "Fallback")
    assert title == "New title"
    assert body == "<p>Hello</p>"


def test_build_retry_title_for_duplicate_publish():
    assert build_retry_title("技术文章", 1) == "技术文章（重发版）"
    assert build_retry_title("技术文章", 2) == "技术文章（重发2）"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_task_execution_enhancement.py -k "extract_title_and_body or build_retry_title" -v`
Expected: FAIL because helpers do not exist

- [ ] **Step 3: Implement minimal helpers and prompt contract**

```python
# app/services/publisher/conflict_resolution.py
def build_retry_title(title: str, attempt: int) -> str:
    if attempt == 1:
        return f"{title}（重发版）"
    return f"{title}（重发{attempt}）"


# app/services/rewriter/prompt_builder.py
def extract_title_and_body(output: str, fallback_title: str) -> tuple[str, str]:
    if "TITLE:" not in output or "BODY:" not in output:
        return fallback_title, output.strip()
    title_part, body_part = output.split("BODY:", 1)
    title = title_part.replace("TITLE:", "", 1).strip() or fallback_title
    return title, body_part.strip()
```

- [ ] **Step 4: Update each rewriter to return structured title/body payload text**

```python
# inside prompt builder template
推荐输出格式：
TITLE: <重写后的标题>
BODY:
<重写后的正文>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_task_execution_enhancement.py -k "extract_title_and_body or build_retry_title" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/publisher/conflict_resolution.py app/services/rewriter/prompt_builder.py app/services/rewriter/deepseek.py app/services/rewriter/mofi.py app/services/rewriter/minimax.py app/services/rewriter/openai_rewriter.py tests/test_task_execution_enhancement.py
git commit -m "feat: add rewritten title parsing and publish conflict helpers"
```

---

### Task 3: Refactor pipeline for rewritten title and stage-aware failure recording

**Files:**
- Modify: `app/services/pipeline.py`
- Test: `tests/test_task_execution_enhancement.py`

- [ ] **Step 1: Write failing tests for stage-aware failure and rewritten title persistence**

```python
from pathlib import Path


def test_pipeline_source_persists_rewritten_title_and_failed_stage():
    source = Path("app/services/pipeline.py").read_text(encoding="utf-8")
    assert "rewritten_title=" in source
    assert "failed_stage" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_execution_enhancement.py::test_pipeline_source_persists_rewritten_title_and_failed_stage -v`
Expected: FAIL if either token is missing

- [ ] **Step 3: Implement minimal pipeline changes**

```python
# conceptual changes in app/services/pipeline.py
current_stage = "fetching"
...
current_stage = "rewriting"
rewritten_title, rewritten_body = extract_title_and_body(rewriter_output, parsed.title)
await _update_task(task_id, rewritten_title=rewritten_title, rewritten_content=rewritten_body)
...
current_stage = "publishing"
post_id = await halo_client.publish(db, rewritten_title, rewritten_body)
...
except Exception as e:
    await _update_task(task_id, status=TaskStatus.failed, failed_stage=current_stage, error_msg=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_execution_enhancement.py::test_pipeline_source_persists_rewritten_title_and_failed_stage -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/pipeline.py tests/test_task_execution_enhancement.py
git commit -m "feat: persist rewritten title and failed stage in pipeline"
```

---

### Task 4: Add Halo duplicate-name auto-retry publish behavior

**Files:**
- Modify: `app/services/publisher/halo_client.py`
- Modify: `app/services/publisher/payloads.py`
- Test: `tests/test_task_execution_enhancement.py`

- [ ] **Step 1: Write failing test for duplicate-name retry logic**

```python
from app.services.publisher.conflict_resolution import build_retry_title


def test_duplicate_name_retry_titles_are_available_for_publish_loop():
    titles = [build_retry_title("标题", i) for i in range(1, 4)]
    assert titles == ["标题（重发版）", "标题（重发2）", "标题（重发3）"]
```

- [ ] **Step 2: Run test to verify current publish loop lacks retry behavior**

Run: `pytest tests/test_task_execution_enhancement.py -k duplicate_name_retry_titles_are_available_for_publish_loop -v`
Expected: PASS helper exists, then add source assertion below and watch it fail

- [ ] **Step 3: Add failing source-level assertion for auto-retry behavior**

```python
from pathlib import Path


def test_halo_client_source_contains_duplicate_name_retry_loop():
    source = Path("app/services/publisher/halo_client.py").read_text(encoding="utf-8")
    assert "名称重复" in source or "重复的名称" in source
    assert "for attempt in range(1, 6)" in source
```

- [ ] **Step 4: Implement minimal retry loop**

```python
for attempt in range(1, 6):
    payload = self._build_payload(current_title, content_html, publish_time)
    ...
    if resp.is_success:
        ...
    if "名称重复" in resp.text or "重复的名称" in resp.text:
        current_title = build_retry_title(base_title, attempt)
        continue
    raise Exception(...)
raise Exception("Halo 名称重复，自动重试 5 次后仍失败")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_task_execution_enhancement.py -k "duplicate_name_retry_titles_are_available_for_publish_loop or halo_client_source_contains_duplicate_name_retry_loop" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/publisher/halo_client.py app/services/publisher/payloads.py tests/test_task_execution_enhancement.py
git commit -m "feat: auto-retry Halo publish on duplicate names"
```

---

### Task 5: Add retry and republish task endpoints

**Files:**
- Modify: `app/routers/tasks.py`
- Modify: `app/services/pipeline.py`
- Test: `tests/test_task_execution_enhancement.py`

- [ ] **Step 1: Write failing tests for endpoint presence and validation rules**

```python
from pathlib import Path


def test_task_router_contains_retry_and_republish_endpoints():
    source = Path("app/routers/tasks.py").read_text(encoding="utf-8")
    assert '@router.post("/{task_id}/retry")' in source
    assert '@router.post("/{task_id}/republish")' in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_execution_enhancement.py::test_task_router_contains_retry_and_republish_endpoints -v`
Expected: FAIL because endpoints do not yet exist

- [ ] **Step 3: Implement minimal endpoints and pipeline entry helpers**

```python
# app/routers/tasks.py
@router.post("/{task_id}/retry")
async def retry_task(task_id: str, background_tasks: BackgroundTasks):
    ...

@router.post("/{task_id}/republish")
async def republish_task(task_id: str, background_tasks: BackgroundTasks):
    ...

# app/services/pipeline.py
async def retry_from_stage(task_id: str):
    ...

async def republish_task_content(task_id: str):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_execution_enhancement.py::test_task_router_contains_retry_and_republish_endpoints -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/tasks.py app/services/pipeline.py tests/test_task_execution_enhancement.py
git commit -m "feat: add retry and republish task endpoints"
```

---

### Task 6: Update task list UI for source badges and action buttons

**Files:**
- Modify: `app/templates/task_list.html`
- Test: `tests/test_task_execution_enhancement.py`

- [ ] **Step 1: Write failing tests for UI markers**

```python
from pathlib import Path


def test_task_list_template_contains_source_badges_and_retry_actions():
    source = Path("app/templates/task_list.html").read_text(encoding="utf-8")
    assert "UI创建" in source
    assert "API创建" in source
    assert "重试" in source
    assert "重新发布" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_execution_enhancement.py::test_task_list_template_contains_source_badges_and_retry_actions -v`
Expected: FAIL because labels/buttons are missing

- [ ] **Step 3: Implement minimal UI changes**

```html
<span x-text="task.trigger_source === 'api' ? 'API创建' : 'UI创建'"></span>
<button x-show="task.status === 'failed'" @click="retryTask(task.id)">重试</button>
<button x-show="task.status === 'completed' || (task.status === 'failed' && task.failed_stage === 'publishing')" @click="republishTask(task.id)">重新发布</button>
```

```javascript
async retryTask(taskId) { await fetch(`/api/tasks/${taskId}/retry`, { method: 'POST' }); await this.loadTasks(); }
async republishTask(taskId) { await fetch(`/api/tasks/${taskId}/republish`, { method: 'POST' }); await this.loadTasks(); }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_execution_enhancement.py::test_task_list_template_contains_source_badges_and_retry_actions -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/task_list.html tests/test_task_execution_enhancement.py
git commit -m "feat: add task source badges and retry actions to task list"
```

---

### Task 7: Final regression verification

**Files:**
- Test: `tests/test_task_execution_enhancement.py`

- [ ] **Step 1: Run focused enhancement test file**

Run: `pytest tests/test_task_execution_enhancement.py -v`
Expected: all enhancement tests PASS

- [ ] **Step 2: Run full test suite**

Run: `pytest -q`
Expected: full suite PASS

- [ ] **Step 3: Commit final fixups if needed**

```bash
git add -A
git commit -m "fix: finalize task execution enhancement regression issues"
```
