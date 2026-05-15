# Open API Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authenticated open API for task creation with a single global API key, default model fallback, and an internal API docs page.

**Architecture:** Introduce a dedicated `open_api` router and schema layer while reusing the existing task creation and pipeline flow. Configuration for the API key and default model stays in `SystemConfig` and is surfaced through the existing settings page plus a new operator-facing docs page.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, Jinja2 + Alpine.js, existing task pipeline, pytest

---

### Task 1: Add open API config schemas

**Files:**
- Modify: `app/schemas/config.py`
- Create: `app/schemas/open_api.py`
- Test: `tests/test_open_api_enhancement.py`

- [ ] **Step 1: Write the failing tests**

```python
from app.schemas.config import ConfigSaveRequest
from app.schemas.open_api import OpenApiTaskCreateRequest


def test_open_api_task_request_accepts_optional_model_fields():
    payload = OpenApiTaskCreateRequest.model_validate(
        {
            "urls": ["https://example.com/post"],
            "publish_type": "immediate",
            "keep_citations": False,
        }
    )
    assert payload.model_provider is None
    assert payload.model_name is None


def test_config_save_request_supports_open_api_settings():
    payload = ConfigSaveRequest.model_validate(
        {
            "providers": [],
            "fetch_mode": "http",
            "open_api_key": "secret-key",
            "default_model_provider": "openai",
            "default_model_name": "gpt-4.1",
        }
    )
    assert payload.open_api_key == "secret-key"
    assert payload.default_model_provider == "openai"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_open_api_enhancement.py -k "optional_model_fields or open_api_settings" -v`
Expected: FAIL because schemas do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
# app/schemas/open_api.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class OpenApiTaskCreateRequest(BaseModel):
    urls: list[str]
    publish_type: str = "immediate"
    scheduled_at: Optional[datetime] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    keep_citations: bool = False


class OpenApiTaskCreateResponse(BaseModel):
    task_id: str
    status: str
    trigger_source: str
    message: str
```

```python
# app/schemas/config.py additions
open_api_key: Optional[str] = None
default_model_provider: Optional[str] = None
default_model_name: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_open_api_enhancement.py -k "optional_model_fields or open_api_settings" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/config.py app/schemas/open_api.py tests/test_open_api_enhancement.py
git commit -m "feat: add open api schemas and config fields"
```

---

### Task 2: Persist open API key and default model config

**Files:**
- Modify: `app/routers/config.py`
- Test: `tests/test_open_api_enhancement.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path


def test_config_router_persists_open_api_key_and_default_model_fields():
    source = Path("app/routers/config.py").read_text(encoding="utf-8")
    assert 'open_api.key' in source
    assert 'open_api.default_model' in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_open_api_enhancement.py::test_config_router_persists_open_api_key_and_default_model_fields -v`
Expected: FAIL because config keys do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
# app/routers/config.py
# GET /api/config reads:
#   open_api.key
#   open_api.default_model

# POST /api/config writes:
#   SystemConfig(key="open_api.key", value=json.dumps({"key": payload.open_api_key}))
#   SystemConfig(key="open_api.default_model", value=json.dumps({"provider": payload.default_model_provider, "model": payload.default_model_name}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_open_api_enhancement.py::test_config_router_persists_open_api_key_and_default_model_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/config.py tests/test_open_api_enhancement.py
git commit -m "feat: persist open api key and default model config"
```

---

### Task 3: Add open API authentication helper and router

**Files:**
- Create: `app/routers/open_api.py`
- Test: `tests/test_open_api_enhancement.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path


def test_open_api_router_contains_api_key_header_validation_and_task_endpoint():
    source = Path("app/routers/open_api.py").read_text(encoding="utf-8")
    assert 'X-API-Key' in source
    assert '@router.post("/tasks")' in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_router_contains_api_key_header_validation_and_task_endpoint -v`
Expected: FAIL because router file does not exist

- [ ] **Step 3: Write minimal implementation**

```python
import json

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from sqlalchemy import select

from app.db import async_session
from app.models.system_config import SystemConfig
from app.models.task import Task, TaskStatus, PublishType
from app.schemas.open_api import OpenApiTaskCreateRequest, OpenApiTaskCreateResponse

router = APIRouter(prefix="/open-api", tags=["open-api"])


async def _require_api_key(x_api_key: str | None) -> None:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    async with async_session() as db:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == "open_api.key"))
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=503, detail="Open API key is not configured")
        cfg = json.loads(row.value)
        if x_api_key != cfg.get("key"):
            raise HTTPException(status_code=403, detail="Invalid API key")


@router.post("/tasks", response_model=OpenApiTaskCreateResponse)
async def create_open_api_task(payload: OpenApiTaskCreateRequest, background_tasks: BackgroundTasks, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    await _require_api_key(x_api_key)
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_router_contains_api_key_header_validation_and_task_endpoint -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/open_api.py tests/test_open_api_enhancement.py
git commit -m "feat: add authenticated open api router"
```

---

### Task 4: Implement default model fallback and API task creation reuse

**Files:**
- Modify: `app/routers/open_api.py`
- Modify: `app/routers/tasks.py` (only if shared helper extraction is needed)
- Test: `tests/test_open_api_enhancement.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path


def test_open_api_router_uses_default_model_when_request_model_missing_and_sets_trigger_source_api():
    source = Path("app/routers/open_api.py").read_text(encoding="utf-8")
    assert 'open_api.default_model' in source
    assert 'trigger_source="api"' in source or "trigger_source='api'" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_router_uses_default_model_when_request_model_missing_and_sets_trigger_source_api -v`
Expected: FAIL until logic is added

- [ ] **Step 3: Write minimal implementation**

```python
async def _resolve_model_selection(payload: OpenApiTaskCreateRequest) -> tuple[str, str]:
    if payload.model_provider and payload.model_name:
        return payload.model_provider, payload.model_name
    if payload.model_provider or payload.model_name:
        raise HTTPException(status_code=400, detail="model_provider and model_name must be provided together")
    ... load open_api.default_model ...

task = Task(
    urls=payload.urls,
    keep_citations=payload.keep_citations,
    publish_type=PublishType(payload.publish_type),
    scheduled_at=payload.scheduled_at,
    trigger_source="api",
    model_provider=provider,
    model_name=model,
    status=TaskStatus.fetching,
    progress=0,
    stage_detail="等待开始...",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_router_uses_default_model_when_request_model_missing_and_sets_trigger_source_api -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/open_api.py app/routers/tasks.py tests/test_open_api_enhancement.py
git commit -m "feat: reuse task creation flow for open api requests"
```

---

### Task 5: Add scheduled request validation rules

**Files:**
- Modify: `app/routers/open_api.py`
- Test: `tests/test_open_api_enhancement.py`

- [ ] **Step 1: Write the failing tests**

```python
from app.schemas.open_api import OpenApiTaskCreateRequest
import pytest


def test_open_api_request_requires_scheduled_at_for_scheduled_publish():
    with pytest.raises(Exception):
        OpenApiTaskCreateRequest.model_validate({
            "urls": ["https://example.com"],
            "publish_type": "scheduled",
        })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_request_requires_scheduled_at_for_scheduled_publish -v`
Expected: FAIL until validation exists

- [ ] **Step 3: Write minimal implementation**

```python
# in open_api router before task creation
if payload.publish_type == "scheduled" and not payload.scheduled_at:
    raise HTTPException(status_code=400, detail="scheduled_at is required when publish_type=scheduled")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_request_requires_scheduled_at_for_scheduled_publish -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/open_api.py tests/test_open_api_enhancement.py
git commit -m "feat: validate scheduled publish input for open api"
```

---

### Task 6: Add settings UI section for Open API config

**Files:**
- Modify: `app/templates/settings.html`
- Test: `tests/test_open_api_enhancement.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path


def test_settings_template_contains_open_api_key_and_default_model_section():
    source = Path("app/templates/settings.html").read_text(encoding="utf-8")
    assert "Open API" in source
    assert "API Key" in source
    assert "默认模型" in source or "default model" in source.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_open_api_enhancement.py::test_settings_template_contains_open_api_key_and_default_model_section -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```html
<div class="bg-white rounded-lg shadow p-6">
  <h2 class="text-lg font-semibold mb-4">Open API</h2>
  <input type="password" x-model="openApiKey" ...>
  <select x-model="defaultModelProvider">...</select>
  <select x-model="defaultModelName">...</select>
  <a href="/open-api/docs">查看接口文档</a>
</div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_open_api_enhancement.py::test_settings_template_contains_open_api_key_and_default_model_section -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/settings.html tests/test_open_api_enhancement.py
git commit -m "feat: add open api config section to settings"
```

---

### Task 7: Add internal API docs page and route

**Files:**
- Modify: `app/routers/pages.py`
- Create: `app/templates/open_api_docs.html`
- Modify: `app/main.py`
- Test: `tests/test_open_api_enhancement.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path


def test_open_api_docs_page_and_route_exist():
    template = Path("app/templates/open_api_docs.html")
    assert template.exists()
    source = Path("app/routers/pages.py").read_text(encoding="utf-8")
    assert '/open-api/docs' in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_docs_page_and_route_exist -v`
Expected: FAIL because page/route do not exist

- [ ] **Step 3: Write minimal implementation**

```python
# app/routers/pages.py
@router.get("/open-api/docs", response_class=HTMLResponse)
async def page_open_api_docs(request: Request):
    return templates.TemplateResponse("open_api_docs.html", {"request": request})
```

Template must include:
- API key usage header
- POST /open-api/tasks docs
- curl example
- python requests example
- javascript fetch example
- success/error sample JSON

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_docs_page_and_route_exist -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/pages.py app/templates/open_api_docs.html app/main.py tests/test_open_api_enhancement.py
git commit -m "feat: add internal open api docs page"
```

---

### Task 8: Final regression verification

**Files:**
- Test: `tests/test_open_api_enhancement.py`

- [ ] **Step 1: Run focused open API suite**

Run: `pytest tests/test_open_api_enhancement.py -v`
Expected: all tests PASS

- [ ] **Step 2: Run full project suite**

Run: `pytest -q`
Expected: full suite PASS

- [ ] **Step 3: Commit final fixups if needed**

```bash
git add -A
git commit -m "fix: finalize open api enhancement regressions"
```
