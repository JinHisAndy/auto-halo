# Auto-Halo

[中文文档](README.md)

Auto-Halo is a FastAPI-based content automation system that:

- creates multiple task blocks in one batch from the UI or API
- lets each task block fetch articles from one or more URLs
- merges multi-URL content inside one task block into a single unified article via AI
- preserves original HTML, images, audio, video, and attachments
- uploads original assets to MinIO (optional, falls back to local `history/` directory)
- rewrites article title and body with AI
- validates rewritten HTML before publishing
- AI semantic tag matching with existing Halo tags or generates new meaningful tags
- automatically extracts article cover image and syncs to Halo
- publishes the final result to Halo v2.24
- supports both UI-driven and API-driven task creation

## Features

### Content acquisition
- HTTP fetch mode
- Playwright browser-render mode
- media extraction for images, audio, video, and attachments
- content-type based file classification (image/video/audio/attachment)
- original rich HTML preview retention

### Multi-task batch creation
- create multiple independent task blocks in one submission from the UI
- submit the same batch shape through the API
- tasks run concurrently without blocking each other
- each task block runs as its own task record and progress flow

### Multi-URL content merging
- each task block can include multiple source URLs
- fetch and parse content from multiple URLs in a single task
- merge all fetched articles into one unified piece through AI
- single rewrite pass, single publish

### AI rewriting
- rewritten title + rewritten body
- technical-blog oriented prompt style
- HTML-aware rewrite flow
- multi-source merge prompt support
- media/code preservation validation

### Tag generation and sync
- AI semantic matching: fetch existing Halo tags first, AI judges which to reuse
- generates meaningful new tags from a blog reader's perspective when needed
- tag color coding
- sync tags to Halo v2.24 with proper displayName/slug/color mapping

### Publishing
- Halo v2.24 publishing via core API
- duplicate-name auto-retry with renamed titles/slugs
- immediate publish or scheduled publish
- automatic cover image extraction (first image from article)
- one-click retry from failed stage for failed tasks

### Task workflow
- batch task creation from UI or API
- live progress updates via WebSocket
- retry from failed stage (fetching/parsing/rewriting/publishing)
- paginated task list with adjustable page size
- distinguish UI-created vs API-created tasks

### Storage options
- configurable MinIO object storage (recommended)
- automatic fallback to local `history/` directory when MinIO is not configured
- preserves original image/audio/video URLs when MinIO is unavailable

### Open API
- multi-key support with labels and timestamps
- key CRUD (generate, copy, preview, delete) from settings UI
- authenticated `POST /open-api/tasks` with `X-API-Key` header
- global default model fallback when request omits model selection
- built-in API documentation page at `/open-api/docs`
- any valid key from the key list is accepted

### Settings
- multi-provider model configuration (OpenAI, DeepSeek, MiniMax, Mofii, custom)
- preset templates for quick provider setup
- auto-fetch model lists after provider connection tests and persist them per provider
- model chips display
- global default model config with provider/model dropdown for a consistent fallback UX
- connection testing for MinIO, Halo, and model providers
- MinIO configuration is optional

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy + SQLite
- Jinja2 + Alpine.js + Tailwind CSS (CDN)
- MinIO (optional)
- Playwright
- Halo v2.24

## Run Locally

```bash
pip install -r requirements.txt
python run.py
```

Default URL:

```text
http://localhost:8808
```

## Docker

```bash
docker compose up --build
```

## Main Pages

- `/` — task creation (supports multi-block batch creation)
- `/tasks` — task list (with pagination, progress bars, preview)
- `/settings` — system configuration
- `/open-api/docs` — internal API documentation page

## Open API Example

```bash
curl -X POST "http://localhost:8808/open-api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "urls": ["https://example.com/post"],
    "publish_type": "immediate",
    "keep_citations": false
  }'
```

## Notes

- Configure model providers, Halo, Open API keys, and default model in `/settings`
- MinIO is optional — if not configured, local `history/` directory is used instead
- For browser-mode fetching, make sure Playwright Chromium is installed
- The system uses SQLite and auto-applies lightweight startup backfills for supported schema additions
- Tags are automatically synced to Halo before post creation (AI semantic matching with existing tags)

## Repository Status

This repository currently uses `master` as the active default branch.