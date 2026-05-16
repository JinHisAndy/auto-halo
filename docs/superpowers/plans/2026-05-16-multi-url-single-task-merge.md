# Multi-URL Single-Task Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one task with multiple URLs fetch and parse every source first, then send one merged consolidation input to AI so the task still produces exactly one article.

**Architecture:** Keep the change inside the existing pipeline flow in `app/services/pipeline.py`. Add a focused regression test in `tests/test_task_batch_and_merge.py` that proves the pipeline rewrites once with a merged multi-source input containing an explicit consolidation instruction, then make the minimal pipeline change needed to satisfy it.

**Tech Stack:** Python, pytest, asyncio, existing pipeline services

---

### Task 1: Add regression coverage for merged multi-URL rewrite input

**Files:**
- Modify: `tests/test_task_batch_and_merge.py`
- Test: `tests/test_task_batch_and_merge.py`

- [ ] **Step 1: Write the failing test**

```python
def test_run_pipeline_merges_multiple_urls_into_single_rewrite_input(monkeypatch):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_batch_and_merge.py::test_run_pipeline_merges_multiple_urls_into_single_rewrite_input -v`
Expected: FAIL because the rewrite input does not yet match the required merged multi-source behavior exactly.

- [ ] **Step 3: Write minimal implementation**

```python
if len(urls) > 1:
    rewrite_source = _build_multi_source_rewrite_input(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_batch_and_merge.py::test_run_pipeline_merges_multiple_urls_into_single_rewrite_input -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_task_batch_and_merge.py app/services/pipeline.py docs/superpowers/plans/2026-05-16-multi-url-single-task-merge.md
git commit -m "fix: merge multi-url task sources before rewrite"
```

### Task 2: Keep the implementation tight in the pipeline

**Files:**
- Modify: `app/services/pipeline.py`
- Test: `tests/test_task_batch_and_merge.py`

- [ ] **Step 1: Keep fetch/parse-before-rewrite behavior explicit for multi-URL tasks**

```python
all_parsed_rich_html = []
all_parsed_clean_text = []
for idx, url in enumerate(urls):
    content = await fetcher_service.fetch(url, mode=mode)
    parsed = await parser_service.parse(content)
    all_parsed_rich_html.append(parsed.rich_html or content.rich_html)
    all_parsed_clean_text.append(parsed.clean_text or content.text_content)
```

- [ ] **Step 2: Build one consolidation-oriented rewrite input**

```python
MULTI_URL_MERGE_INSTRUCTION = (
    "以下内容来自多个不同来源的文章。"
    "请先综合理解全部信息，去重并处理冲突，"
    "再按清晰的逻辑结构整合成一篇统一文章，"
    "不要按来源分别输出多篇文章。\n\n"
)
```

- [ ] **Step 3: Reuse the single rewrite/publish path**

```python
await _rewrite_from_source(
    task_id=task_id,
    ...,
    rewrite_source=rewrite_source,
    ...,
)
```

- [ ] **Step 4: Run focused regression coverage**

Run: `pytest tests/test_task_batch_and_merge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_task_batch_and_merge.py app/services/pipeline.py docs/superpowers/plans/2026-05-16-multi-url-single-task-merge.md
git commit -m "fix: merge multi-url task sources before rewrite"
```
