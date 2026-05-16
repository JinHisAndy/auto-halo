# Multi-Task UI And Merge Design

## Scope

This spec corrects the previously mis-implemented task creation workflow.

It covers:

1. Multiple task blocks on the task creation page
2. One task block can contain multiple source URLs
3. Multiple URLs inside one task are merged into one final article
4. One click starts all configured task blocks concurrently
5. Settings UX improvements for provider models and default model persistence
6. Nav tab active-state polish
7. Halo tag sync reliability
8. README updates

## Core model

- **One task block = one final article**
- **Multiple URLs inside one task block = multiple sources for that one article**
- **Multiple task blocks on the page = multiple independent tasks submitted together**

## UI behavior

- Add a `+` control after each task block's publish settings to append another task block
- Rename `创建任务` button to `开始任务`
- Clicking `开始任务` submits all task blocks in one batch
- Each task block becomes one backend task row

## Merge behavior

For each task row with multiple URLs:

1. Fetch all URLs
2. Parse all URLs
3. Preserve each source's rich HTML/media references
4. Merge sources into one AI rewrite input with source separators
5. Ask AI to produce a logically unified article rather than treating them as independent posts

## Settings behavior

- Remove manual `获取模型列表` button
- Successful provider connection test should auto-load models
- Persist fetched provider model lists
- Global default model remains at bottom of provider section and must be sourced from already-loaded provider models

## Navigation

Top tabs must clearly show current page.

## Halo tags

Ensure tags exist before post creation and are attached to the published article using the format Halo 2.24 expects.
