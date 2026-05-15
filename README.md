# Auto-Halo

Auto-Halo is a FastAPI-based content automation system that:

- fetches articles from one or more URLs
- preserves original HTML, images, audio, video, and attachments
- stores original assets in MinIO
- rewrites article title and body with AI
- validates rewritten HTML before publishing
- generates article tags automatically
- publishes the final result to Halo v2.24
- supports both UI-driven and API-driven task creation

## Features

### Content acquisition
- HTTP fetch mode
- Playwright browser-render mode
- media extraction for images, audio, video, and attachments
- original rich HTML preview retention

### AI rewriting
- rewritten title + rewritten body
- technical-blog oriented prompt style
- HTML-aware rewrite flow
- media/code preservation validation

### Publishing
- Halo v2.24 publishing
- duplicate-name auto-retry with renamed titles/slugs
- immediate publish or scheduled publish
- republish support

### Task workflow
- task creation
- live progress updates via WebSocket
- retry from failed stage
- republish using saved rewritten content
- distinguish UI-created vs API-created tasks

### Open API
- authenticated `POST /open-api/tasks`
- single global API key via `X-API-Key`
- default model fallback when request omits model selection
- built-in docs page at `/open-api/docs`

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
- `/tasks` — task list
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

- Configure MinIO, Halo, model providers, Open API key, and default model in `/settings`
- For browser-mode fetching, make sure Playwright Chromium is installed
- The system uses SQLite and auto-applies lightweight startup backfills for supported schema additions

## Repository Status

This repository currently uses `master` as the active default branch.
