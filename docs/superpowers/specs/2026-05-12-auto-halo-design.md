# Auto-Halo Design Spec

## Overview

Auto-Halo is a content repurposing tool that accepts article URLs (WeChat public accounts, blogs, etc.), fetches content, stores originals and media in MinIO, rewrites the article using AI while preserving meaning, and publishes to Halo CMS (v2.24).

## Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Frontend**: Jinja2 templates + Alpine.js + Tailwind CSS
- **Database**: SQLite (via SQLAlchemy + aiosqlite)
- **Background Tasks**: FastAPI BackgroundTasks + APScheduler
- **Content Fetching**: HTTP (requests + readability-lxml) + Playwright (configurable fallback)
- **AI Integration**: Independent API adapters per provider (OpenAI SDK-compatible)
- **Deployment**: Docker + docker-compose, also direct `python run.py`

## Core Flow

```
URL Input → Fetch → Parse (extract content + media) → MinIO (save original)
  → AI Rewrite → MinIO (save rewritten) → Halo Publish
```

## Directory Structure

```
auto-halo/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry, lifecycle, WebSocket
│   ├── config.py             # Global config, defaults
│   ├── db.py                 # SQLAlchemy async engine + session
│   ├── models/
│   │   ├── __init__.py
│   │   ├── task.py           # Task ORM model
│   │   └── system_config.py  # SystemConfig ORM model (key-value)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── task.py           # Pydantic schemas for tasks
│   │   └── config.py         # Pydantic schemas for config
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── tasks.py          # /api/tasks CRUD + status
│   │   ├── config.py         # /api/config CRUD + connectivity tests
│   │   ├── pages.py          # / page rendering (3 pages + WebSocket)
│   │   └── ws.py             # /ws/tasks WebSocket endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── fetcher/
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # Abstract fetcher
│   │   │   ├── http_fetcher.py
│   │   │   ├── browser_fetcher.py
│   │   │   └── service.py    # FetcherService orchestrator
│   │   ├── parser/
│   │   │   ├── __init__.py
│   │   │   └── service.py    # Content parsing + media extraction
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   └── minio_client.py
│   │   ├── rewriter/
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # Abstract rewriter
│   │   │   ├── registry.py   # Provider registry
│   │   │   ├── deepseek.py
│   │   │   ├── mofi.py       # 模力方舟
│   │   │   ├── minimax.py
│   │   │   ├── openai_rewriter.py
│   │   │   └── factory.py    # RewriterFactory
│   │   ├── publisher/
│   │   │   ├── __init__.py
│   │   │   └── halo_client.py
│   │   ├── pipeline.py       # Orchestrates full flow per task
│   │   └── scheduler.py      # APScheduler for scheduled publishing
│   ├── templates/
│   │   ├── base.html
│   │   ├── task_create.html
│   │   ├── task_list.html
│   │   └── settings.html
│   └── static/
│       └── css/
│           └── app.css       # Tailwind compiled CSS
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── run.py                    # Entry point
└── README.md
```

## Data Models

### Task

| Field | Type | Description |
|---|---|---|
| id | UUID (PK) | Auto-generated |
| title | str (nullable) | Extracted page title, filled after fetch |
| urls | JSON (list of str) | Input URLs |
| status | enum | `fetching`, `parsing`, `rewriting`, `publishing`, `scheduled`, `completed`, `failed` |
| progress | int (0-100) | Percentage complete |
| stage_detail | str | Human-readable current stage description |
| error_msg | str (nullable) | Failure reason |
| keep_citations | bool | Whether to preserve original blockquotes |
| publish_type | enum | `immediate`, `scheduled` |
| scheduled_at | datetime (nullable) | Scheduled publish time |
| minio_original_path | str (nullable) | MinIO path to original files folder |
| minio_rewritten_path | str (nullable) | MinIO path to rewritten markdown |
| original_content | text (nullable) | Extracted text for preview |
| rewritten_content | text (nullable) | Rewritten text for preview |
| halo_post_id | int (nullable) | Halo post ID after publish |
| model_provider | str | AI provider key (e.g., "deepseek") |
| model_name | str | AI model name |
| created_at | datetime | Auto on create |
| updated_at | datetime | Auto on update |

### SystemConfig

| Field | Type | Description |
|---|---|---|
| key | str (PK) | Config key, namespaced (e.g., `providers.deepseek`) |
| value | text (JSON) | JSON-encoded config value |
| updated_at | datetime | Auto on update |

**Config key namespaces:**
- `providers.{name}` — JSON: `{"name": "DeepSeek", "api_key": "...", "base_url": "...", "models": [...]}`
- `minio` — JSON: `{"endpoint": "...", "access_key": "...", "secret_key": "...", "bucket": "...", "secure": false}`
- `halo` — JSON: `{"site_url": "...", "api_token": "..."}`
- `fetch.mode` — String: `"http"` or `"browser"`

## Service Layer Design

### 1. FetcherService

Input: URL + mode (`http` | `browser`)
Output: FetchedContent(title, html_raw, text_content, media_urls[])

- `http` mode: requests.get() → readability-lxml extracts main content
- `browser` mode: Playwright headless → page.content() → readability-lxml extraction
- Auto-fallback: if HTTP returns insufficient content (< 50 chars), retry with browser

### 2. ParserService

Input: FetchedContent
Output: ParsedArticle(title, clean_text, media_list[{url, type, filename}], attachment_list[])

- Classify media by extension: image (jpg/png/gif/webp/svg), video (mp4/webm), audio (mp3/wav), attachment (pdf/doc/docx/xlsx/zip)
- Download each media file to temp storage for upload
- Preserve `<blockquote>` tags in clean_text when keep_citations is requested
- Convert HTML to clean plain text (remove scripts, styles, navigation)

### 3. MinioStorage

- `save_original(article_title, html_raw, parsed_article)` — creates folder structure:
  ```
  <sanitized_title>/
  ├── original.html
  ├── original.pdf       (wkhtmltopdf generated)
  ├── media/
  │   ├── image_001.jpg
  │   └── ...
  └── attachments/
      └── ...
  ```
- `save_rewritten(article_title, markdown_content)` — saves `rewritten.md` in same folder
- `test_connection()` — attempts list_buckets, returns bool + message

### 4. Rewriter

Abstract base class defining interface:
- `list_models() -> list[dict]` — calls provider's `/models` endpoint
- `rewrite(text, keep_citations=False) -> str` — core rewrite logic
- `test_connection() -> bool`

**Provider adapters:**
Each provider implements the base class with its own base_url and headers. All use OpenAI-compatible chat completions API.

**Rewrite prompt template:**
```
你是一位资深博客作者。请将以下文章内容用你自己的话重写一遍。
要求：
- 保持原文的核心信息和观点不变
- 用博客的轻松自然口吻表达
- 不得直接复制粘贴原文的句子
- 可以调整文章结构和段落顺序
{f"-- 保留以下原文引用内容（blockquote中的内容需要保留原样）：\n{citations}" if keep_citations else ""}

原文内容：
{text}
```

**Provider presets (default base_url):**
- DeepSeek: `https://api.deepseek.com/v1`
- 模力方舟(Gitee AI): `https://ai.gitee.com/v1`
- MiniMax: `https://api.minimax.chat/v1`
- OpenAI: `https://api.openai.com/v1`

### 5. HaloClient

Halo v2.24 REST API integration:
- **Auth**: `Authorization: Bearer {pat_token}` header
- **Endpoint**: `POST /apis/api.console.halo.run/v1alpha1/posts`
- **Payload**: content in Markdown format, metadata (title, slug, published status)
- `publish(title, content_md, publish_time=None)`:
  - `publish_time=None` → create with `spec.publish: true`, `spec.releaseSnapshot` at current time
  - `publish_time=future` → create as draft, then schedule via Halo's publish mechanism
- `test_connection()` → GET site info/api, verify 200

### 6. Pipeline (Orchestrator)

```python
async def run_pipeline(task_id, urls, provider_key, model_name, keep_citations, publish_type, scheduled_at):
    task = fetch_and_set_status(task_id, "fetching", progress=0)
    
    # Stage 1: Fetch
    update_stage(task, "fetching", 10, "正在抓取网页内容...")
    content = await fetcher_service.fetch(urls[0])  # first URL
    
    # Stage 2: Parse
    update_stage(task, "parsing", 25, "正在解析文章内容和媒体文件...")
    parsed = await parser_service.parse(content)
    task.title = parsed.title
    task.original_content = parsed.clean_text
    
    # Stage 3: Save original to MinIO
    update_stage(task, "rewriting", 40, "正在上传原始文件到MinIO...")
    minio_original_path = await minio.save_original(parsed.title, content.html_raw, parsed)
    task.minio_original_path = minio_original_path
    
    # Stage 4: Rewrite
    update_stage(task, "rewriting", 55, "AI正在重写文章...")
    rewriter = RewriterFactory.create(provider_key, model_name)
    rewritten = await rewriter.rewrite(parsed.clean_text, keep_citations)
    task.rewritten_content = rewritten
    
    # Stage 5: Save rewritten to MinIO
    update_stage(task, "rewriting", 75, "正在备份重写稿到MinIO...")
    minio_rewritten_path = await minio.save_rewritten(parsed.title, rewritten)
    task.minio_rewritten_path = minio_rewritten_path
    
    # Stage 6: Publish
    if publish_type == "immediate":
        update_stage(task, "publishing", 85, "正在发布到Halo...")
        post_id = await halo_client.publish(task.title, rewritten)
        task.halo_post_id = post_id
        task.status = "completed"
        task.progress = 100
    else:
        task.status = "scheduled"
        task.progress = 90
        update_stage(task, "scheduled", 90, f"等待定时发布: {scheduled_at}")
        scheduler.schedule_publish(task_id, scheduled_at)
    
    db.commit()
```

## Pages

### Task Create (`/`)
- Multi-URL input with add/remove
- Model provider + model dropdowns (cascading)
- Keep citations checkbox
- Publish type: immediate / scheduled with datetime picker
- Submit creates task and redirects to list

### Task List (`/tasks`)
- Real-time status updates via WebSocket
- Progress bar + stage description per task
- Status badges: fetching(blue), parsing(blue), rewriting(blue), publishing(blue), scheduled(orange), completed(green), failed(red)
- Preview modals: original content / rewritten content tabs
- Sorted by created_at descending
- Direct link to Halo post when completed

### Settings (`/settings`)
- Provider management: add/remove, per-provider api_key + base_url + model list (auto-fetch)
- Provider preset templates for quick add
- MinIO config: endpoint, access_key, secret_key, bucket
- Halo config: site_url, api_token
- Fetch mode preference: http / browser
- Connectivity test buttons per section
- Secret fields masked by default

## WebSocket Protocol

Endpoint: `ws://host/ws/tasks`

**Server → Client messages:**
```json
{
  "type": "task_update",
  "task_id": "uuid",
  "status": "rewriting",
  "progress": 55,
  "stage_detail": "AI正在重写文章...",
  "updated_at": "2026-05-12T10:00:00"
}
```

**Client → Server messages:**
```json
{"type": "subscribe", "task_ids": ["uuid1", "uuid2"]}
```

On page load, task list page subscribes to all active tasks. Updates are merged into Alpine.js state.

## Error Handling

- Any stage failure sets task status to `failed` with `error_msg`
- WebSocket pushes failure notification with error details
- Failed tasks can be inspected (original content may be partially available)
- Retry not automatic — user manually creates new task

## Deployment

### Direct run
```bash
pip install -r requirements.txt
python run.py
```

### Docker
```yaml
services:
  auto-halo:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data  # SQLite db persistence
    environment:
      - DATABASE_URL=sqlite:///data/auto-halo.db
```