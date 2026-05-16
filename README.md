# Auto-Halo

[中文文档](README.zh-CN.md)

Auto-Halo is a FastAPI-based content automation system that:

- fetches articles from one or more URLs
- merges multi-URL content into a single unified article via AI
- preserves original HTML, images, audio, video, and attachments
- uploads original assets to MinIO
- rewrites article title and body with AI
- validates rewritten HTML before publishing
- generates article tags automatically and syncs them to Halo
- publishes the final result to Halo v2.24
- supports both UI-driven and API-driven task creation

## Features

### Content acquisition
- HTTP fetch mode
- Playwright browser-render mode
- media extraction for images, audio, video, and attachments
- content-type based file classification (image/video/audio/attachment)
- original rich HTML preview retention

### Multi-URL content merging
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
- automatic tag extraction from rewritten content
- tag color coding (blue, indigo, teal, emerald, amber, rose)
- sync tags to Halo v2.24 with proper displayName/slug/color mapping

### Publishing
- Halo v2.24 publishing via core API
- duplicate-name auto-retry with renamed titles/slugs
- immediate publish or scheduled publish
- republish / retry from failed stage support

### Task workflow
- task creation from UI or API
- live progress updates via WebSocket
- retry from failed stage (fetching/parsing/rewriting/publishing)
- republish using saved rewritten content
- paginated task list with adjustable page size
- distinguish UI-created vs API-created tasks

### Open API
- multi-key support with labels and timestamps
- key CRUD (generate, copy, delete) from settings UI
- authenticated `POST /open-api/tasks` with `X-API-Key` header
- global default model fallback when request omits model selection
- built-in API documentation page at `/open-api/docs`
- any valid key from the key list is accepted

### Settings
- multi-provider model configuration (OpenAI, DeepSeek, MiniMax, Mofii, custom)
- preset templates for quick provider setup
- fetch model lists per provider with persistence
- model chips display and selection per provider
- global default model config with provider/model dropdown
- connection testing for MinIO, Halo, and model providers

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy + SQLite
- Jinja2 + Alpine.js + Tailwind CSS (CDN)
- MinIO
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

- `/` — task creation
- `/tasks` — task list (with pagination)
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

- Configure MinIO, Halo, model providers, Open API keys, and default model in `/settings`
- For browser-mode fetching, make sure Playwright Chromium is installed
- The system uses SQLite and auto-applies lightweight startup backfills for supported schema additions
- Tags are automatically synced to Halo before post creation

## Repository Status

This repository currently uses `master` as the active default branch.