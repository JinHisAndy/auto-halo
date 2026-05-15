# Open API Enhancement Design

## Scope

This spec covers the third enhancement group for Auto-Halo:

1. Expose an authenticated external HTTP API for task creation
2. Add a single global API key configuration
3. Support default-model fallback for API-triggered tasks
4. Add an internal API documentation page with examples and key management
5. Reuse the existing task pipeline and task-source distinction

This spec does not yet cover multi-key management, HMAC signatures, rate limiting, or README work beyond what is needed to document this API later.

## Goals

- Allow external systems to trigger the existing Auto-Halo workflow reliably
- Keep API invocation aligned with UI task creation behavior
- Avoid duplicate orchestration logic
- Provide self-service docs and examples inside the product
- Keep authentication simple for current internal/private use

## Non-Goals

- Public internet hardening (rate limits, rotating keys, audit logs)
- Multi-tenant API credentials
- Fine-grained permissions per key
- Webhook callbacks for task completion

## Selected Approach

Use a **single global API key** validated via request header.

The system will expose a narrow external API namespace, e.g. `/open-api/...`, separate from internal UI/admin routes. External task creation will internally reuse the existing task-creation/pipeline flow and persist `trigger_source = api`.

## Architecture Summary

The new API layer adds three concepts:

1. **Global API key config**
2. **Open API router** for authenticated task creation
3. **API docs page** for human operators

The actual workflow remains unchanged:

External request → API key validation → task creation → existing pipeline → task list / retry / republish reuse

## Authentication Model

### Request header

All open API requests must include:

```http
X-API-Key: <configured-key>
```

### Validation rules

- missing header → `401 Unauthorized`
- wrong key → `403 Forbidden`
- no configured key in system settings → `503 Service Unavailable` or `500` with explicit configuration message

### Why header-based key

- simple to integrate with scripts and cron jobs
- avoids query-string leakage
- matches current single-user/internal-service use case

## Open API Task Creation

### Endpoint

Recommended endpoint:

- `POST /open-api/tasks`

### Request body

```json
{
  "urls": ["https://example.com/post-1"],
  "publish_type": "immediate",
  "scheduled_at": null,
  "model_provider": "openai",
  "model_name": "gpt-4.1",
  "keep_citations": false
}
```

### Field rules

- `urls`: required, one or more URLs
- `publish_type`: optional, defaults to `immediate`
- `scheduled_at`: required only when `publish_type == scheduled`
- `model_provider`: optional
- `model_name`: optional
- `keep_citations`: optional, defaults to `false`

### Model selection logic

If request provides both `model_provider` and `model_name`, use them.

If request omits them, use system-wide defaults:

- `default_model_provider`
- `default_model_name`

If no request model and no global default exist:

- reject request with `400` and clear message

## Data Model / Config Changes

### System configuration additions

Store in `SystemConfig`:

- `open_api.key`
- `open_api.default_model`

Suggested values:

```json
{
  "key": "<random-secret-string>"
}
```

```json
{
  "provider": "openai",
  "model": "gpt-4.1"
}
```

### Task integration

When creating tasks through open API:

- `trigger_source = api`

This directly reuses the task-source feature already built in group 1.

## Internal API Docs Page

### Route

Recommended page route:

- `GET /open-api/docs`

### Page sections

#### Top section: key management

- current API key masked by default
- regenerate/update key input
- save button

#### Default model section

- provider dropdown
- model dropdown
- description of fallback behavior

#### Endpoint reference section

For `POST /open-api/tasks`:

- URL
- method
- required header
- request fields
- field descriptions
- example request
- example success response
- example error responses

#### Example blocks

- cURL example
- Python `requests` example
- JavaScript `fetch` example

## Settings UI Integration

The existing settings page should be extended with an “Open API” section containing:

- API key input
- default provider/model selectors
- quick link to API docs page

This keeps operational configuration in one place.

## Router Strategy

### New router

Add a dedicated router such as:

- `app/routers/open_api.py`

Responsibilities:

- authenticate incoming open API calls
- validate request payload
- resolve model defaults if omitted
- create task record with `trigger_source = api`
- enqueue existing pipeline

### Why separate router

- avoids mixing internal UI/admin routes with external integration routes
- keeps auth policy explicit
- easier future extension (`/open-api/tasks/{id}`, status endpoints, etc.)

## Request/Response Behavior

### Success response

Return minimal task creation result:

```json
{
  "task_id": "uuid",
  "status": "fetching",
  "trigger_source": "api",
  "message": "任务已创建"
}
```

### Error responses

Examples:

```json
{"detail": "Missing X-API-Key header"}
```

```json
{"detail": "Invalid API key"}
```

```json
{"detail": "Default model is not configured"}
```

```json
{"detail": "scheduled_at is required when publish_type=scheduled"}
```

## Validation Rules

Open API validation should mirror current UI validation plus:

- API key required
- if only one of `model_provider` / `model_name` is supplied, reject request
- if `publish_type == scheduled` and `scheduled_at` missing, reject

## Reuse of Existing Pipeline

Do not build a second workflow for API calls.

Open API task creation should call the same lower-level task creation behavior already used by UI, so that:

- retry works
- republish works
- task list shows same progress states
- task source distinction works automatically

## Docs and UX Behavior

### API docs page intent

This page is for operators/integrators, not for anonymous users. It should explain:

- where to put the API key
- how default model fallback works
- what fields are optional
- how immediate vs scheduled publish behaves

### Task list distinction

No extra design needed beyond current `trigger_source` badge. API-created tasks will automatically show `API创建`.

## Testing Strategy

### Automated tests

Add tests for:

1. missing API key rejected
2. wrong API key rejected
3. request without model uses global default model
4. request with explicit model overrides default model
5. task created through open API gets `trigger_source = api`
6. scheduled publish requires `scheduled_at`
7. docs/settings config path stores API key and default model

### Manual verification

1. set global API key and default model in settings
2. call `POST /open-api/tasks` with header + no model fields
3. verify task appears as `API创建`
4. call again with explicit model and verify override is used
5. open `/open-api/docs` and verify examples/key management are visible

## Files Expected to Change

- `app/schemas/config.py`
- `app/schemas/task.py` (if separate open-api request schema is added there or nearby)
- `app/routers/config.py`
- `app/routers/pages.py`
- `app/templates/settings.html`

Likely new files:

- `app/routers/open_api.py`
- `app/schemas/open_api.py`
- `app/templates/open_api_docs.html`

## Forward Compatibility

This design intentionally leaves room for future upgrades:

- multiple keys
- API task status query endpoints
- richer examples / SDK snippets
- audit metadata on API calls
