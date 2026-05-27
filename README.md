# Auto-Halo

> 一键将多篇网页文章抓取 → AI 整合重写 → 自动发布到 Halo 博客。

Auto-Halo 是面向 Halo CMS 的内容自动化中枢。你给它一个或多个 URL，它就能自动抓取文章正文与图片、调用 AI 将内容重写为技术博客风格、匹配或生成标签，并一键发布到你的 Halo 站点——全程无需手动编辑。

---

**English** | [中文](#-auto-halo)

> One-click: scrape multiple web articles → AI rewrite & merge → publish to Halo CMS.

Auto-Halo is a content automation hub built for Halo CMS. Give it one or more URLs, and it automatically fetches article content and images, uses AI to rewrite them in a technical blog style, matches or generates tags, and publishes everything to your Halo site—all hands-free.

---

<p align="center">
  <a href="#-快速开始">快速开始</a> •
  <a href="#-核心能力">核心能力</a> •
  <a href="#-Quick-Start">Quick Start</a> •
  <a href="#-Key-Features">Key Features</a>
</p>

---

## 🌏 中文

### 它是做什么的

在日常运营技术博客时，你可能会：

- 看到一篇好文章，想用自己的话整理发布到 Halo
- 看到多篇观点互补的文章，想把它们融合成一篇深度内容
- 需要批量搬运内容但不想反复手动排版、找图、打标签

Auto-Halo 把这些步骤全自动化了。**你只需要粘贴 URL**。

### 核心能力

- **多 URL 内容整合**：一个任务可以传入多个来源 URL，AI 自动去重、合并、形成逻辑统一的文章
- **技术博客风格重写**：不是机翻或摘要，而是用技术博主的口吻重写，保留核心事实和观点
- **图片 / 音视频保留**：自动提取正文中的图片和媒体文件，可上传到 MinIO 做镜像托管
- **智能标签**：AI 自动匹配 Halo 已有标签，无匹配时生成有实际含义的新标签
- **定时发布**：支持立即发布或设定未来时间自动发布
- **失败重试**：任务从失败阶段继续，不需要重新开始
- **Open API**：提供 REST API 供外部系统调用，支持多 API Key 管理

### 为什么选 Auto-Halo

| 对比 | 手动搬运 | Auto-Halo |
|------|----------|-----------|
| 多篇文章融合 | 逐篇阅读、手动整理 | AI 自动去重整合 |
| 图片处理 | 逐张下载、上传、替换 | 自动提取 → MinIO/本地 |
| 标签整理 | 手动回忆已有标签 | AI 语义匹配 + 生成 |
| 格式排版 | 逐段校对 | AI 产出排版好的 HTML |

### 快速开始

```bash
pip install -r requirements.txt
python run.py
# 访问 http://localhost:8808
```

或使用 Docker：

```bash
docker compose up --build
```

### 配置

1. 打开 `/settings` 配置模型供应商（OpenAI / DeepSeek / MiniMax / 模力方舟 / 自定义）
2. 配置 Halo 站点地址和令牌
3. （可选）配置 MinIO 镜像存储；不配则使用本地 `history/` 目录
4. 回到首页创建任务

### 页面

- `/` — 创建任务（支持多任务批量）
- `/tasks` — 任务列表（进度、预览）
- `/settings` — 系统配置
- `/open-api/docs` — Open API 文档

### Open API 示例

```bash
curl -X POST "http://localhost:8808/open-api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"urls": ["https://example.com/post"], "publish_type": "immediate"}'
```

---

**如果这个项目对你有帮助，欢迎 Star ⭐**

---

## 🌍 English

### What It Does

Maintaining a tech blog involves a lot of repetitive work:

- Finding great articles, rewriting them in your own voice
- Merging multiple sources into one coherent piece
- Manually downloading images, uploading to storage, replacing URLs
- Tagging each post by hand

Auto-Halo automates all of this. **Just paste the URLs.**

### Key Features

- **Multi-URL Content Merge**: Feed multiple source URLs per task and let AI deduplicate and unify them into a single coherent article
- **Technical Blog Rewriting**: Not summarization or translation—AI rewrites content in an authentic tech blogger voice while preserving core facts and opinions
- **Media Extraction & Mirroring**: Automatically extracts images, video and audio from articles with optional MinIO mirroring
- **Smart Tagging**: AI semantically matches existing Halo tags; generates meaningful new tags when no match is found
- **Scheduled Publishing**: Publish immediately or schedule for a future date
- **Failure Retry**: Tasks resume from the failed stage—no need to restart
- **Open API**: REST endpoints for external integrations, with multi-key management

### Why Auto-Halo

| Task | Manual | Auto-Halo |
|------|--------|-----------|
| Merge multiple articles | Read each, manually combine | AI merges automatically |
| Handle images | Download, upload, replace URLs one by one | Auto extract → MinIO/local |
| Tag posts | Remember and type existing tags | AI semantic matching + generation |
| Format content | Proofread paragraph by paragraph | AI outputs well-formatted HTML |

### Quick Start

```bash
pip install -r requirements.txt
python run.py
# Open http://localhost:8808
```

Or with Docker:

```bash
docker compose up --build
```

### Configuration

1. Open `/settings` to configure your AI provider (OpenAI / DeepSeek / MiniMax / MoFi / Custom)
2. Set your Halo site URL and API token
3. (Optional) Configure MinIO for media mirroring; local `history/` directory is used otherwise
4. Go to the homepage and create a task

### Pages

- `/` — Create tasks (supports batch creation)
- `/tasks` — Task list (progress, preview)
- `/settings` — System configuration
- `/open-api/docs` — Open API documentation

---

**If this project helps you, please Star ⭐**

---

## 技术栈 / Tech Stack

Python 3.11+ · FastAPI · SQLAlchemy + SQLite · Jinja2 · Alpine.js + Tailwind CSS · MinIO (optional) · Playwright · Halo v2.24 · trafilatura · readability-lxml