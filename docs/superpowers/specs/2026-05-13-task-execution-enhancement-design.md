# Task Execution Enhancement Design

## Scope

This spec covers the first enhancement group for Auto-Halo:

1. Retry failed tasks from the failed stage
2. Republish completed or publish-failed tasks without re-running earlier stages
3. Automatically rewrite article titles and handle Halo duplicate-name conflicts
4. Distinguish tasks created from UI vs API in the task list and task model

This spec does **not** yet cover the later enhancement groups (API key management, external API docs page, README, tag generation, or global default model UX) except where this work must leave extension points for them.

## Goals

- Avoid forcing users to recreate tasks after operational failures
- Reduce unnecessary re-fetching and re-rewriting when failure happens in later stages
- Prevent Halo publish failures caused by duplicate names
- Ensure rewritten title and rewritten body are treated as first-class publish artifacts
- Prepare the data model for future API-triggered tasks

## Non-Goals

- Full workflow engine redesign
- Persisted fine-grained per-step checkpoints for every internal helper call
- Automatic retry loops for network errors without user action
- Version history of multiple republish attempts

## Design Summary

The current pipeline is linear and stateless between major phases except for task record fields. This enhancement keeps that architecture but introduces:

- explicit `failed_stage`
- explicit `trigger_source`
- explicit `rewritten_title`
- retry/republish task endpoints
- publish conflict resolution for duplicate Halo names

The pipeline remains the single orchestrator, but it will be able to restart from a chosen stage using already persisted task artifacts.

## Data Model Changes

### Task additions

Add the following fields to `Task`:

- `failed_stage: str | null`
  - one of: `fetching`, `parsing`, `rewriting`, `publishing`
- `trigger_source: str`
  - one of: `ui`, `api`
- `rewritten_title: str | null`
  - AI-rewritten publish title

### Semantics

- `failed_stage` is set only when task status becomes `failed`
- `failed_stage` is cleared when retry starts successfully
- `trigger_source` is set when task is created and never changes
- `rewritten_title` is generated during rewrite phase and reused by republish

## Retry and Republish Behavior

### Retry

Only visible for failed tasks.

Behavior:

- If `failed_stage == fetching`
  - restart full pipeline from fetch
- If `failed_stage == parsing`
  - refetch current URL first, then continue from parse
  - reason: parser depends on fresh fetched content object
- If `failed_stage == rewriting`
  - reuse stored original content / parsed rich HTML where possible
  - continue from rewrite
- If `failed_stage == publishing`
  - reuse `rewritten_title` and `rewritten_content`
  - continue from publish only

### Republish

Visible for:

- completed tasks
- publish-failed tasks

Behavior:

- never refetch
- never reparse
- never rerun AI rewrite
- publish using saved `rewritten_title` and `rewritten_content`

If rewritten artifacts are missing, button should be hidden or the backend should return a clear validation error.

## Halo Duplicate Name Handling

### Root issue

Halo rejects duplicate resource names during post creation. Since current publish name is derived from title slug, repeated publishes can fail.

### Strategy

The publish layer will:

1. use `rewritten_title` as the primary title
2. attempt publish with generated slug
3. if response body indicates duplicate name / duplicate title condition:
   - regenerate title using retry suffix policy
   - regenerate slug from the new title
   - retry publish

### Title suffix policy

For a rewritten title `T`:

- first retry: `T（重发版）`
- second retry: `T（重发2）`
- third retry: `T（重发3）`

This policy is user-friendly and visible in Halo.

### Retry limit

Maximum automatic duplicate-resolution attempts: 5

If still failing after 5 attempts:

- mark task failed
- `failed_stage = publishing`
- preserve the last Halo error in `error_msg`

## Rewrite Phase Changes

### Current problem

Only body content is rewritten. Publish still uses original title, which creates duplicate-name risk and mismatch between rewritten article and title.

### New rewrite output contract

The rewrite phase must produce two artifacts:

- `rewritten_title`
- `rewritten_content`

### Prompt contract

The rewriter will be instructed to return structured output with these rules:

- rewrite title into a professional technical-blog style
- body can be more complete than source, but must stay accurate
- body should remain professional and technically expressive
- preserve HTML structure/media placeholders when content source is HTML

Recommended response contract:

```text
TITLE: <rewritten title>
BODY:
<rewritten content>
```

The parsing logic in the rewrite layer will split the response into title/body. If the model fails to follow the format, fallback rules apply:

- keep original title only as emergency fallback
- still mark this as successful rewrite only if body exists

## Trigger Source Distinction

### Data

`trigger_source` values:

- `ui`
- `api`

### UI presentation

Task list card will display a small badge, e.g.:

- `UI创建`
- `API创建`

This is stored on task creation so future external API tasks fit naturally without refactoring the task list later.

## API Changes

### Task router additions

Add endpoints:

- `POST /api/tasks/{task_id}/retry`
- `POST /api/tasks/{task_id}/republish`

### Retry endpoint rules

- task must exist
- task status must be `failed`
- `failed_stage` must be present
- endpoint enqueues appropriate continuation workflow

### Republish endpoint rules

- task must exist
- task status in `completed` or `failed`
- `rewritten_title` and `rewritten_content` must exist
- endpoint starts publish-only workflow

## Pipeline Refactor Plan

The pipeline should be split conceptually into resumable stage functions:

- `run_fetch_stage(...)`
- `run_parse_stage(...)`
- `run_rewrite_stage(...)`
- `run_publish_stage(...)`

The top-level pipeline remains coordinator, but retry logic can invoke the proper stage entry point.

### Persistence needed between stages

To resume safely, store enough artifacts on task record:

- `original_content` → rich HTML preview/original content
- `rewritten_content`
- `rewritten_title`
- `minio_original_path`
- `minio_rewritten_path`

Where a live fetched object is needed again (e.g. retry from parse), the system may refetch rather than trying to serialize the entire fetched object into DB.

## Task List UI Changes

Each task card gains:

- source badge (`UI创建` / `API创建`)
- retry button for failed tasks
- republish button for completed or publish-failed tasks

### Button visibility rules

- `重试`
  - only when `status == failed`
- `重新发布`
  - when `status == completed`
  - or when `status == failed && failed_stage == publishing`

### UX details

- buttons should disable while request is in flight
- on success, task list should refresh the single affected task or reload tasks
- toast should explain whether action is retry or republish

## Error Handling

### Failure recording

When any stage fails:

- `status = failed`
- `failed_stage = current_stage`
- `error_msg = detailed message`

### Duplicate title publish failure

Do not expose raw 400 only. Store user-meaningful message like:

- `Halo 名称重复，系统已自动重试标题...`
- if retries exhausted: `Halo 名称重复，自动重试 5 次后仍失败`

## Testing Strategy

### Automated tests

Add tests for:

1. `TaskResponse` serializes new fields correctly
2. rewrite parser extracts title + body from structured model output
3. duplicate title strategy generates expected retry titles/slugs
4. retry endpoint rejects invalid task states
5. republish endpoint rejects tasks with missing rewritten artifacts
6. publish-only path reuses saved rewritten title/body

### Manual verification

1. Create a task via UI and confirm `UI创建` badge
2. Force a publish duplicate-name error and verify auto rename succeeds
3. Force publish stage failure and click `重试`
4. Complete one task and click `重新发布`

## Files Expected to Change

- `app/models/task.py`
- `app/schemas/task.py`
- `app/routers/tasks.py`
- `app/services/pipeline.py`
- `app/services/publisher/halo_client.py`
- `app/services/publisher/payloads.py`
- `app/services/rewriter/*`
- `app/templates/task_list.html`

## Future Compatibility

This design intentionally prepares the next enhancement groups by introducing:

- `trigger_source` for API-created tasks
- `rewritten_title` for smarter publishing workflows
- retry/republish endpoints that later external API callers can also use
