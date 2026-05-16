# Multi-Task UI And Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the task creation page submit multiple independent task blocks at once, while each task block can merge multiple source URLs into one final article.

**Architecture:** Add a batch task-creation endpoint for UI use, preserve the existing single-task API paths, and refactor the pipeline to merge multiple source URLs within a single task before rewrite/publish. Keep settings and docs changes narrowly scoped to the existing templates and routers.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, Jinja2 + Alpine.js, existing pipeline/rewrite/publisher services, pytest

---

### Task 1: Add batch task creation schemas and endpoint

**Files:**
- Modify: `app/schemas/task.py`
- Modify: `app/routers/tasks.py`
- Test: `tests/test_task_batch_and_merge.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run failing tests**
- [ ] **Step 3: Add `TaskBatchCreateRequest` and `POST /api/tasks/batch`**
- [ ] **Step 4: Run tests green**
- [ ] **Step 5: Commit**

### Task 2: Refactor task creation page into multiple task blocks

**Files:**
- Modify: `app/templates/task_create.html`
- Test: `tests/test_task_batch_and_merge.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run failing tests**
- [ ] **Step 3: Change page state from single task to tasks[] blocks, add `+`, rename button to `开始任务`, submit batch**
- [ ] **Step 4: Run tests green**
- [ ] **Step 5: Commit**

### Task 3: Merge multiple URLs inside one task before rewrite

**Files:**
- Modify: `app/services/pipeline.py`
- Test: `tests/test_task_batch_and_merge.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run failing tests**
- [ ] **Step 3: Fetch/parse all URLs in a task and merge them into one rewrite input**
- [ ] **Step 4: Run tests green**
- [ ] **Step 5: Commit**

### Task 4: Auto-fetch and persist provider model lists; keep default model at provider section bottom

**Files:**
- Modify: `app/templates/settings.html`
- Test: `tests/test_settings_provider_models.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run failing tests**
- [ ] **Step 3: Remove manual fetch button, auto-fetch after successful test, persist models, preserve default model section**
- [ ] **Step 4: Run tests green**
- [ ] **Step 5: Commit**

### Task 5: Ensure active nav tab styling and verify Halo tags attachment behavior

**Files:**
- Modify: `app/templates/base.html`
- Modify: `app/services/publisher/halo_client.py`
- Modify: `app/services/publisher/payloads.py`
- Test: `tests/test_nav_and_halo_tags.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run failing tests**
- [ ] **Step 3: Implement active-tab styles and correct tag attach path for Halo 2.24**
- [ ] **Step 4: Run tests green**
- [ ] **Step 5: Commit**

### Task 6: Update bilingual README files

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Update feature descriptions and language links**
- [ ] **Step 2: Commit**

### Task 7: Final verification

**Files:**
- Test: `tests/test_task_batch_and_merge.py`
- Test: `tests/test_settings_provider_models.py`
- Test: `tests/test_nav_and_halo_tags.py`

- [ ] **Step 1: Run focused suites**
- [ ] **Step 2: Run full `pytest -q`**
- [ ] **Step 3: Commit final fixups if needed**
