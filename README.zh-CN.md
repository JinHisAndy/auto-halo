# Auto-Halo

[English](README.md)

Auto-Halo 是一个基于 FastAPI 的内容自动化系统，支持：

- 通过 UI 或 API 一次创建多个任务块的批量任务
- 每个任务块可从一个或多个 URL 抓取文章内容
- 将单个任务块中的多 URL 内容通过 AI 整合成一篇统一文章
- 保留原始 HTML、图片、音视频与附件
- 将原始资源上传保存到 MinIO
- 使用 AI 对文章标题和正文进行重写
- 在发布前校验重写后的 HTML
- 自动生成文章标签并同步到 Halo
- 发布到 Halo v2.24
- 同时支持 UI 创建任务和 API 创建任务

## 功能特性

### 内容抓取
- HTTP 抓取模式
- Playwright 浏览器渲染抓取模式
- 图片、音频、视频、附件提取
- 基于 Content-Type 的文件类型分类（image/video/audio/attachment）
- 保留原始富文本 HTML 预览

### 多任务批量创建
- 支持在 UI 中一次提交多个彼此独立的任务块
- API 也支持提交同样的批量任务结构
- 每个任务块都会作为独立任务记录执行完整流程

### 多URL 内容整合
- 每个任务块都可以包含多个来源 URL
- 单任务内抓取并解析多个 URL 的文章内容
- 通过 AI 将多篇文章整合成一篇逻辑清晰、层次分明的统一文章
- 一次重写、一次发布

### AI 重写
- 标题与正文一起重写
- 更偏技术博客风格的提示词
- 面向 HTML 的重写链路
- 多来源整合提示词支持
- 媒体/代码保留校验

### 标签生成与同步
- 从重写内容中自动提取标签
- 标签颜色编码（蓝色、靛蓝、青色、翠绿、琥珀、玫瑰）
- 在创建文章前同步到 Halo v2.24（含 displayName/slug/color 完整映射）

### 发布能力
- 通过 Halo 核心 API 发布到 v2.24
- Halo 重名自动改标题/slug 重试
- 支持立即发布与定时发布
- 支持重新发布 / 从失败阶段重试

### 任务流转
- 通过 UI 或 API 批量创建任务
- WebSocket 实时进度更新
- 从失败阶段重试（抓取/解析/重写/发布）
- 基于已保存重写结果重新发布
- 任务列表分页，支持调整每页条数
- 区分 UI 创建与 API 创建任务

### 开放 API
- 多 Key 支持，含标签和时间戳
- Key 的增删改查（生成、复制、删除）在设置页操作
- 认证接口 `POST /open-api/tasks`（`X-API-Key` 请求头）
- 未传模型时使用全局默认模型
- 内置 API 文档页 `/open-api/docs`
- 全部有效 Key 均可通过认证

### 系统配置
- 多供应商模型配置（OpenAI、DeepSeek、MiniMax、模力方舟、自定义）
- 预设模板快速配置供应商
- 在供应商连接测试成功后自动拉取并持久化模型列表
- 模型标签展示与选择
- 全局默认模型配置（含供应商/模型下拉选择），提供统一默认模型体验
- MinIO、Halo、模型供应商连接测试

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
- `/tasks` —— 任务列表（含分页）
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
- 标签会在文章发布前自动同步到 Halo，非图片资源会继续按 Content-Type 进行分类处理

## 分支说明

当前仓库使用 `master` 作为默认工作分支。
