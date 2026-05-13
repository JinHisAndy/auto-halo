# Content Rewrite Enhancement Design

## Scope

This spec covers the second enhancement group for Auto-Halo:

1. Upgrade rewriting so title and body are both rewritten in a more professional technical style
2. Accept rich HTML input and allow model-driven HTML output while strongly preserving key media/code structures
3. Add rewrite output validation and failure fallback
4. Generate article tags from rewritten content and publish them with the article

This spec does not yet cover the external API surface, API key management, or README work except where this group must leave integration points for them.

## Goals

- Produce richer, more professional, more technical rewritten articles
- Allow rewritten output to exceed original length while staying accurate
- Preserve images, audio, video, links, code blocks, and important technical structures in the final published article
- Rewrite the title along with the body to avoid duplicate-name problems and improve article coherence
- Generate useful publish-time article tags automatically

## Non-Goals

- Full DOM-diff or AST-patch rewriting engine
- Multi-pass human approval workflow for rewrite quality
- Semantic fact-checking against outside sources
- Theme-specific Halo rendering customization

## Selected Approach

Use **rich HTML whole-document rewriting with structured prompt constraints**.

The model receives the original rich HTML and is explicitly instructed to:

- preserve critical media/code/link structures
- keep technical accuracy
- rewrite title and textual sections in a more polished technical-blog style
- return structured output with rewritten title and rewritten HTML body

This is intentionally more flexible than strict node-level replacement. It gives better writing quality while still preserving high-value structural content through prompt rules and post-validation.

## Architecture Summary

The rewrite stage becomes a richer content transformation pipeline:

1. Fetch rich HTML
2. Parse and normalize HTML/media references
3. Send rich HTML to rewriter with stronger technical prompt
4. Parse structured response into:
   - `rewritten_title`
   - `rewritten_content_html`
5. Validate rewritten HTML output
6. Generate tags from rewritten article
7. Publish HTML + tags to Halo

## Rewrite Input/Output Contract

### Input to rewriter

The rewriter receives:

- original title
- original rich HTML
- keep-citations preference

### Output from rewriter

Structured output format remains:

```text
TITLE: <rewritten title>
BODY:
<rewritten html>
```

The `BODY` section must be valid HTML or HTML-like content that can be normalized.

## Prompt Design

### Core rewrite goals

The new prompt must emphasize:

- output should sound like an experienced technical blogger
- explanation can be richer and more complete than the original
- technical interpretation must remain accurate
- examples, background explanation, and implementation detail can be expanded
- no invented facts, APIs, commands, or results

### HTML preservation rules

The prompt must explicitly state:

- keep `img`, `video`, `audio`, `source`, `a`, `pre`, `code`, `table`, `ul`, `ol`, `blockquote` structures unless absolutely necessary for valid HTML
- do not remove media tags
- do not replace media tags with plain text placeholders
- do not rewrite code blocks into prose
- do not alter link targets unless malformed in source

### Output style rules

- title should be rewritten, not copied
- tone should be technically professional, concise but rich
- content may be expanded for clarity and completeness
- output should favor explanation quality for engineers and technical readers

## Validation Rules

After the model returns content, validate:

1. `TITLE:` exists
2. `BODY:` exists
3. body is not empty
4. body looks like HTML
5. if original contains media/code blocks, rewritten output still contains corresponding structural markers at a reasonable level

### Validation heuristics

Compare original rich HTML against rewritten HTML for:

- image count > 0 in original and rewritten count unexpectedly becomes 0
- code block count > 0 in original and rewritten count unexpectedly becomes 0
- video/audio tags present in original but fully missing in rewritten

If validation fails:

- mark task failed in `rewriting`
- store validator message in `error_msg`
- keep raw model response for debugging if possible

## Tag Generation

### Inputs

Tag generation runs after successful rewrite using:

- `rewritten_title`
- rewritten body text (plain-text summary extracted from HTML)

### Output

Generate 3 to 6 tags.

Rules:

- tags should be concise
- technical topics should dominate when article is technical
- avoid meaningless tags like “文章”, “博客”, “经验分享” unless absolutely needed

### Color assignment

For each tag, assign a random color from a controlled palette, e.g.:

- blue
- indigo
- teal
- emerald
- amber
- rose

If Halo tag API supports color metadata, publish both name and color.
If not, publish tag names to Halo and keep color mapping internally for later UI use.

## Data Model Changes

Add task-level storage for tags:

- `generated_tags: JSON | null`
  - shape:

```json
[
  {"name": "Linux", "color": "blue"},
  {"name": "SSH", "color": "indigo"}
]
```

This allows preview and later API export.

## Pipeline Changes

### Rewrite stage

Rewrite stage now:

1. uses rich HTML as primary source
2. requests structured title/body output
3. validates rewritten HTML
4. stores `rewritten_title`, `rewritten_content`

### Tag stage

After rewrite succeeds and before publish:

1. extract readable plain text from rewritten HTML
2. run tag generation helper
3. persist `generated_tags`

### Publish stage

Publish must use:

- `rewritten_title`
- `rewritten_content` as HTML
- generated tag list

## Publisher Integration

Halo publish logic should be extended to support tags.

Possible flow:

1. ensure tags exist in Halo (lookup or create)
2. collect tag identifiers or references expected by Halo payload
3. include tags in post spec payload

If Halo requires separate tag creation API calls, publisher service should isolate that work in helper methods rather than bloating `publish()`.

## UI Changes

### Task list preview

Preview continues to show:

- original rich HTML
- rewritten rich HTML

Additional optional enhancement:

- show generated tags beneath the task card when task completed or rewritten

### Task card metadata

Add a compact tag preview, e.g. colored pills, once `generated_tags` exists.

## Failure Behavior

### Rewrite failure

Examples:

- model output missing title/body wrapper
- rewritten HTML stripped media/code content excessively
- model returned unsupported multimodal error such as image input unsupported

Recommended handling:

- set `status = failed`
- `failed_stage = rewriting`
- provide specific `error_msg`

If the model returns a message like:

`Cannot read "image.png" (this model does not support image input)`

do not retry automatically. Surface this clearly to the user so they can switch models.

## Testing Strategy

### Automated tests

Add tests for:

1. prompt contains stronger technical-writing constraints
2. prompt contains structured HTML preservation rules
3. rewritten output validator catches media/code removal regressions
4. tag generator returns 3–6 tags with allowed colors
5. pipeline persists `generated_tags`
6. publisher payload includes tags when available

### Manual verification

1. rewrite a technical article with images and code blocks
2. confirm rewritten title differs from original
3. confirm rewritten article is longer and more technical in tone
4. confirm images/code blocks remain visible in preview
5. confirm published Halo article contains tags

## File Impact

Likely files to change:

- `app/models/task.py`
- `app/schemas/task.py`
- `app/services/rewriter/prompt_builder.py`
- `app/services/rewriter/*`
- `app/services/pipeline.py`
- `app/services/publisher/halo_client.py`
- `app/services/publisher/payloads.py`
- `app/templates/task_list.html`

Likely new files:

- `app/services/rewriter/validation.py`
- `app/services/tagging/service.py`

## Branch Rename Note

Separately from this enhancement group, the repository branch should move from local `master` to `main` to match the remote default branch. This is an operational git task, not part of the rewrite architecture itself.
