# Auto-Halo

Auto-Halo 是一个基于 FastAPI 的内容自动化系统，支持：

- 从一个或多个 URL 抓取文章内容
- 保留原始 HTML、图片、音视频与附件
- 将原始资源保存到 MinIO
- 使用 AI 对文章标题和正文进行重写
- 在发布前校验重写后的 HTML
- 自动生成文章标签
- 发布到 Halo v2.24
- 同时支持 UI 创建任务和 API 创建任务

## 功能特性

### 内容抓取
- HTTP 抓取模式
- Playwright 浏览器渲染抓取模式
- 图片、音频、视频、附件提取
- 保留原始富文本 HTML 预览

### AI 重写
- 标题与正文一起重写
- 更偏技术博客风格的提示词
- 面向 HTML 的重写链路
- 媒体/代码保留校验

### 发布能力
- 发布到 Halo v2.24
- Halo 重名自动改标题/slug 重试
- 支持立即发布与定时发布
- 支持重新发布

### 任务流转
- 创建任务
- WebSocket 实时进度更新
- 从失败阶段重试
- 基于已保存重写结果重新发布
- 区分 UI 创建与 API 创建任务

### 开放 API
- 认证接口 `POST /open-api/tasks`
- 使用单个全局 API Key（`X-API-Key`）
- 未传模型时使用全局默认模型
- 内置接口文档页 `/open-api/docs`

## 技术栈

- Python 3.11+
- FastAPI
- SQLAlchemy + SQLite
- Jinja2 + Alpine.js + Tailwind CSS（CDN）
- MinIO
- Playwright
- Halo v2.24

## 本地运行

```bash
pip install -r requirements.txt
python run.py
```

默认访问地址：

```text
http://localhost:8808
```

## Docker 运行

```bash
docker compose up --build
```

## 主要页面

- `/` —— 创建任务
- `/tasks` —— 任务列表
- `/settings` —— 系统配置
- `/open-api/docs` —— 内部 API 文档页

## Open API 示例

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

## 使用说明

- 先在 `/settings` 中配置 MinIO、Halo、模型供应商、Open API Key 和默认模型
- 如果使用浏览器抓取模式，请确保已安装 Playwright Chromium
- 系统使用 SQLite，并会在启动时对已支持的字段变更执行轻量补列

## 分支说明

当前仓库使用 `master` 作为默认工作分支。
