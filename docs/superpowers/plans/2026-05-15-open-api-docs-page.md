# Open API Docs Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an internal HTML docs page at `/open-api/docs` that explains how to call `POST /open-api/tasks` with examples and regression coverage.

**Architecture:** Reuse the existing pages router and Jinja template setup so the new docs page behaves like the other internal pages. Add one focused source-level regression test first, then add the matching route and a standalone template that documents API key usage, request examples, and success/error responses.

**Tech Stack:** FastAPI, Jinja2 templates, pytest, Tailwind via existing base template

---

### File Structure

- `app/routers/pages.py` — existing HTML page router; add the `/open-api/docs` route here.
- `app/templates/open_api_docs.html` — new Jinja template for the internal API docs page.
- `tests/test_open_api_enhancement.py` — add the focused regression test required by the task.
- `app/main.py` — already includes `pages.router`; leave unchanged unless test evidence shows otherwise.

### Task 1: Add regression test for docs page existence and route string

**Files:**
- Modify: `tests/test_open_api_enhancement.py`
- Test: `tests/test_open_api_enhancement.py::test_open_api_docs_page_and_route_exist`

- [ ] **Step 1: Write the failing test**

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
Expected: FAIL because `app/templates/open_api_docs.html` does not exist yet.

### Task 2: Add the minimal route and template

**Files:**
- Modify: `app/routers/pages.py`
- Create: `app/templates/open_api_docs.html`
- Test: `tests/test_open_api_enhancement.py::test_open_api_docs_page_and_route_exist`

- [ ] **Step 1: Add the route in `app/routers/pages.py`**

```python
@router.get("/open-api/docs", response_class=HTMLResponse)
async def page_open_api_docs(request: Request):
    return templates.TemplateResponse("open_api_docs.html", {"request": request})
```

- [ ] **Step 2: Create `app/templates/open_api_docs.html` with the required content**

```html
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto space-y-6">
    <div class="bg-white rounded-lg shadow p-6">
        <h1 class="text-2xl font-bold mb-2">Open API 使用文档</h1>
        <p class="text-sm text-gray-600">使用 <code class="px-1 py-0.5 bg-gray-100 rounded">X-API-Key</code> 请求头调用内部开放接口。</p>
    </div>

    <div class="bg-white rounded-lg shadow p-6 space-y-3">
        <h2 class="text-lg font-semibold">API Key 用法</h2>
        <p class="text-sm text-gray-700">先在系统配置中设置 Open API Key，然后在每个请求里携带 <code class="px-1 py-0.5 bg-gray-100 rounded">X-API-Key: &lt;your-key&gt;</code>。</p>
    </div>

    <div class="bg-white rounded-lg shadow p-6 space-y-3">
        <h2 class="text-lg font-semibold">POST /open-api/tasks</h2>
        <p class="text-sm text-gray-700">创建一个抓取并生成文章的任务。请求体至少需要 <code class="px-1 py-0.5 bg-gray-100 rounded">urls</code>，其余字段可按需提供。</p>
        <pre class="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm"><code>{
  "urls": ["https://example.com/post"],
  "publish_type": "immediate",
  "keep_citations": false,
  "model_provider": "openai",
  "model_name": "gpt-4.1"
}</code></pre>
    </div>

    <div class="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 class="text-lg font-semibold">curl 示例</h2>
        <pre class="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm"><code>curl -X POST "http://localhost:8000/open-api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "urls": ["https://example.com/post"],
    "publish_type": "immediate",
    "keep_citations": false
  }'</code></pre>

        <h2 class="text-lg font-semibold">Python requests 示例</h2>
        <pre class="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm"><code>import requests

response = requests.post(
    "http://localhost:8000/open-api/tasks",
    headers={
        "Content-Type": "application/json",
        "X-API-Key": "your-api-key",
    },
    json={
        "urls": ["https://example.com/post"],
        "publish_type": "immediate",
        "keep_citations": False,
    },
)

print(response.status_code)
print(response.json())</code></pre>

        <h2 class="text-lg font-semibold">JavaScript fetch 示例</h2>
        <pre class="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm"><code>const response = await fetch("/open-api/tasks", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "your-api-key"
  },
  body: JSON.stringify({
    urls: ["https://example.com/post"],
    publish_type: "immediate",
    keep_citations: false
  })
});

const data = await response.json();
console.log(response.status, data);</code></pre>
    </div>

    <div class="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 class="text-lg font-semibold">成功响应示例</h2>
        <pre class="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm"><code>{
  "task_id": "task-123",
  "status": "fetching",
  "trigger_source": "api",
  "message": "任务已创建"
}</code></pre>

        <h2 class="text-lg font-semibold">错误响应示例</h2>
        <pre class="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm"><code>{
  "detail": "Missing X-API-Key header"
}</code></pre>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Run the focused test to verify it passes**

Run: `pytest tests/test_open_api_enhancement.py::test_open_api_docs_page_and_route_exist -v`
Expected: PASS

### Task 3: Run required verification and commit

**Files:**
- Modify: `tests/test_open_api_enhancement.py`
- Modify: `app/routers/pages.py`
- Create: `app/templates/open_api_docs.html`

- [ ] **Step 1: Run the required test file**

Run: `pytest tests/test_open_api_enhancement.py -v`
Expected: PASS for the full file, including the new docs page regression test.

- [ ] **Step 2: Commit the change**

```bash
git add tests/test_open_api_enhancement.py app/routers/pages.py app/templates/open_api_docs.html docs/superpowers/plans/2026-05-15-open-api-docs-page.md
git commit -m "feat: add internal open api docs page"
```

- [ ] **Step 3: Verify repository status is clean enough after commit**

Run: `git status --short`
Expected: no staged changes for the files in this task.
