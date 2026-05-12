# Auto-Halo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a content repurposing tool that fetches article URLs, stores content in MinIO, rewrites via AI, and publishes to Halo CMS.

**Architecture:** FastAPI monolith with Jinja2+Alpine.js+Tailwind frontend, SQLite persistence, service-layer separation (fetcher/parser/storage/rewriter/publisher/pipeline), WebSocket for real-time progress, APScheduler for timed publishing.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy+aiosqlite, Jinja2, Alpine.js, Tailwind CSS, Playwright, readability-lxml, httpx, minio-py, APScheduler

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `run.py`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/db.py`

- [ ] **Step 1: Create requirements.txt**

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0
jinja2==3.1.4
python-multipart==0.0.18
httpx==0.28.1
readability-lxml==0.8.1
lxml==5.3.0
beautifulsoup4==4.12.3
playwright==1.49.1
minio==7.2.10
openai==1.58.1
apscheduler==3.10.4
websockets==14.1
python-slugify==8.0.4
pdfkit==1.0.0
pydantic==2.10.4
pydantic-settings==2.7.1
```

- [ ] **Step 2: Create app/__init__.py**

```python
```

- [ ] **Step 3: Create app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///data/auto-halo.db"
    host: str = "0.0.0.0"
    port: int = 8000
    secret_key: str = "change-me-in-production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

- [ ] **Step 4: Create app/db.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 5: Create run.py**

```python
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
```

- [ ] **Step 6: Verify project runs (will fail until main.py exists, just check imports)**

Run: `python -c "import app.config; import app.db; print('imports OK')"`
Expected: "imports OK"

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with FastAPI, SQLAlchemy, config"
```

---

### Task 2: Data Models

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/task.py`
- Create: `app/models/system_config.py`

- [ ] **Step 1: Create app/models/__init__.py**

```python
from app.models.task import Task
from app.models.system_config import SystemConfig
```

- [ ] **Step 2: Create app/models/task.py**

```python
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Enum, JSON
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from app.db import Base


class TaskStatus(str, enum.Enum):
    fetching = "fetching"
    parsing = "parsing"
    rewriting = "rewriting"
    publishing = "publishing"
    scheduled = "scheduled"
    completed = "completed"
    failed = "failed"


class PublishType(str, enum.Enum):
    immediate = "immediate"
    scheduled = "scheduled"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=True)
    urls = Column(JSON, nullable=False, default=list)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.fetching)
    progress = Column(Integer, nullable=False, default=0)
    stage_detail = Column(String(500), nullable=False, default="等待开始...")
    error_msg = Column(Text, nullable=True)
    keep_citations = Column(Boolean, nullable=False, default=False)
    publish_type = Column(Enum(PublishType), nullable=False, default=PublishType.immediate)
    scheduled_at = Column(DateTime, nullable=True)
    minio_original_path = Column(String(500), nullable=True)
    minio_rewritten_path = Column(String(500), nullable=True)
    original_content = Column(Text, nullable=True)
    rewritten_content = Column(Text, nullable=True)
    halo_post_id = Column(Integer, nullable=True)
    model_provider = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 3: Create app/models/system_config.py**

```python
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime

from app.db import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(200), primary_key=True)
    value = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Verify imports**

Run: `python -c "from app.models import Task, SystemConfig; print('models OK')"`
Expected: "models OK"

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add Task and SystemConfig data models"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/task.py`
- Create: `app/schemas/config.py`

- [ ] **Step 1: Create app/schemas/__init__.py**

```python
```

- [ ] **Step 2: Create app/schemas/task.py**

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    urls: list[str]
    keep_citations: bool = False
    publish_type: str = "immediate"
    scheduled_at: Optional[datetime] = None
    model_provider: str
    model_name: str


class TaskResponse(BaseModel):
    id: str
    title: Optional[str]
    urls: list[str]
    status: str
    progress: int
    stage_detail: str
    error_msg: Optional[str]
    keep_citations: bool
    publish_type: str
    scheduled_at: Optional[datetime]
    minio_original_path: Optional[str]
    minio_rewritten_path: Optional[str]
    original_content: Optional[str]
    rewritten_content: Optional[str]
    halo_post_id: Optional[int]
    model_provider: str
    model_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
```

- [ ] **Step 3: Create app/schemas/config.py**

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProviderConfig(BaseModel):
    name: str
    api_key: str
    base_url: str
    models: list[str] = []


class MinioConfig(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False


class HaloConfig(BaseModel):
    site_url: str
    api_token: str


class ConfigResponse(BaseModel):
    providers: list[ProviderConfig]
    minio: Optional[MinioConfig]
    halo: Optional[HaloConfig]
    fetch_mode: str = "http"

    class Config:
        from_attributes = True


class ConfigSaveRequest(BaseModel):
    providers: list[ProviderConfig] = []
    minio: Optional[MinioConfig] = None
    halo: Optional[HaloConfig] = None
    fetch_mode: str = "http"


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
```

- [ ] **Step 4: Verify imports**

Run: `python -c "from app.schemas.task import TaskCreate, TaskResponse; from app.schemas.config import ProviderConfig, MinioConfig; print('schemas OK')"`
Expected: "schemas OK"

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add Pydantic schemas for task and config"
```

---

### Task 4: Fetcher Service (HTTP)

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/fetcher/__init__.py`
- Create: `app/services/fetcher/base.py`
- Create: `app/services/fetcher/http_fetcher.py`

- [ ] **Step 1: Create app/services/__init__.py**

```python
```

- [ ] **Step 2: Create app/services/fetcher/__init__.py**

```python
```

- [ ] **Step 3: Create app/services/fetcher/base.py**

```python
from dataclasses import dataclass, field


@dataclass
class FetchedContent:
    title: str
    html_raw: str
    text_content: str
    media_urls: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Create app/services/fetcher/http_fetcher.py**

```python
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from readability import Document

from app.services.fetcher.base import FetchedContent


async def fetch_http(url: str) -> FetchedContent:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    doc = Document(html)
    title = doc.title()
    summary_html = doc.summary()

    soup = BeautifulSoup(summary_html, "lxml")
    text_content = soup.get_text(separator="\n", strip=True)

    media_urls = _extract_media_urls(html, url)

    return FetchedContent(
        title=title,
        html_raw=html,
        text_content=text_content,
        media_urls=media_urls,
    )


def _extract_media_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls = set()

    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src")
        if src:
            urls.add(urljoin(base_url, src))

    for tag in soup.find_all("video"):
        src = tag.get("src")
        if src:
            urls.add(urljoin(base_url, src))
        for source in tag.find_all("source"):
            src = source.get("src")
            if src:
                urls.add(urljoin(base_url, src))

    for tag in soup.find_all("audio"):
        src = tag.get("src")
        if src:
            urls.add(urljoin(base_url, src))
        for source in tag.find_all("source"):
            src = source.get("src")
            if src:
                urls.add(urljoin(base_url, src))

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if re.search(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z)$", href, re.IGNORECASE):
            urls.add(urljoin(base_url, href))

    return list(urls)
```

- [ ] **Step 5: Verify fetch works (optional, needs network)**

Run: `python -c "import asyncio; from app.services.fetcher.http_fetcher import fetch_http; print('http_fetcher OK')"`
Expected: "http_fetcher OK"

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add HTTP fetcher with readability-lxml + media extraction"
```

---

### Task 5: Fetcher Service (Browser + Orchestrator)

**Files:**
- Create: `app/services/fetcher/browser_fetcher.py`
- Create: `app/services/fetcher/service.py`

- [ ] **Step 1: Create app/services/fetcher/browser_fetcher.py**

```python
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from readability import Document

from app.services.fetcher.base import FetchedContent


async def fetch_browser(url: str) -> FetchedContent:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)
        html = await page.content()
        title = await page.title()
        await browser.close()

    doc = Document(html)
    summary_html = doc.summary()

    soup = BeautifulSoup(summary_html, "lxml")
    text_content = soup.get_text(separator="\n", strip=True)

    from app.services.fetcher.http_fetcher import _extract_media_urls
    media_urls = _extract_media_urls(html, url)

    return FetchedContent(
        title=title,
        html_raw=html,
        text_content=text_content,
        media_urls=media_urls,
    )
```

- [ ] **Step 2: Create app/services/fetcher/service.py**

```python
from app.services.fetcher.base import FetchedContent
from app.services.fetcher.http_fetcher import fetch_http
from app.services.fetcher.browser_fetcher import fetch_browser


class FetcherService:
    async def fetch(self, url: str, mode: str = "http") -> FetchedContent:
        if mode == "http":
            content = await fetch_http(url)
            if len(content.text_content.strip()) >= 50:
                return content
            return await fetch_browser(url)
        else:
            return await fetch_browser(url)


fetcher_service = FetcherService()
```

- [ ] **Step 3: Verify imports**

Run: `python -c "from app.services.fetcher.service import fetcher_service; print('fetcher service OK')"`
Expected: "fetcher service OK"

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add browser fetcher and FetcherService orchestrator"
```

---

### Task 6: Parser Service

**Files:**
- Create: `app/services/parser/__init__.py`
- Create: `app/services/parser/service.py`

- [ ] **Step 1: Create app/services/parser/__init__.py**

```python
```

- [ ] **Step 2: Create app/services/parser/service.py**

```python
import os
import re
import tempfile
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.fetcher.base import FetchedContent


@dataclass
class MediaItem:
    url: str
    file_type: str  # image, video, audio, attachment
    filename: str
    local_path: str  # downloaded temp path


@dataclass
class ParsedArticle:
    title: str
    clean_text: str
    media_items: list[MediaItem] = field(default_factory=list)
    attachment_items: list[MediaItem] = field(default_factory=list)


class ParserService:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}
    VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}
    ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar", ".7z"}

    def _classify_url(self, url: str) -> str:
        path = urlparse(url).path.lower()
        ext = os.path.splitext(path)[1]
        if ext in self.IMAGE_EXTENSIONS:
            return "image"
        if ext in self.VIDEO_EXTENSIONS:
            return "video"
        if ext in self.AUDIO_EXTENSIONS:
            return "audio"
        return "attachment"

    async def parse(self, content: FetchedContent) -> ParsedArticle:
        sanitized_title = re.sub(r'[<>:"/\\|?*]', "_", content.title or "untitled")[:200]
        clean_text = self._clean_html(content.html_raw)

        media_items = []
        attachment_items = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=headers) as client:
            for idx, url in enumerate(content.media_urls):
                file_type = self._classify_url(url)
                ext = os.path.splitext(urlparse(url).path.lower().split("?")[0])[1] or ".bin"
                filename = f"{file_type}_{idx:03d}{ext}"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    tmp_path = os.path.join(tempfile.gettempdir(), f"auto_halo_{filename}")
                    with open(tmp_path, "wb") as f:
                        f.write(resp.content)
                    item = MediaItem(url=url, file_type=file_type, filename=filename, local_path=tmp_path)
                except Exception:
                    item = MediaItem(url=url, file_type=file_type, filename=filename, local_path="")

                if file_type in ("image", "video", "audio"):
                    media_items.append(item)
                else:
                    attachment_items.append(item)

        clean_text = self._post_process_text(content.text_content)

        return ParsedArticle(
            title=sanitized_title,
            clean_text=clean_text,
            media_items=media_items,
            attachment_items=attachment_items,
        )

    def _clean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                if attr not in ("href", "src", "alt"):
                    del tag[attr]
        return str(soup)

    def _post_process_text(self, text: str) -> str:
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        result = []
        prev_empty = False
        for line in lines:
            if not line:
                if not prev_empty:
                    result.append("")
                prev_empty = True
            else:
                result.append(line)
                prev_empty = False
        return "\n".join(result)


parser_service = ParserService()
```

- [ ] **Step 3: Verify imports**

Run: `python -c "from app.services.parser.service import parser_service, ParsedArticle; print('parser service OK')"`
Expected: "parser service OK"

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add parser service with media classification and download"
```

---

### Task 7: MinIO Storage Service

**Files:**
- Create: `app/services/storage/__init__.py`
- Create: `app/services/storage/minio_client.py`

- [ ] **Step 1: Create app/services/storage/__init__.py**

```python
```

- [ ] **Step 2: Create app/services/storage/minio_client.py**

```python
import io
import json
from pathlib import Path

from minio import Minio

from app.models.system_config import SystemConfig


class MinioStorage:
    def _get_client(self, config: dict) -> Minio:
        return Minio(
            endpoint=config["endpoint"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            secure=config.get("secure", False),
        )

    async def _load_config(self, db_session) -> dict | None:
        from sqlalchemy import select

        result = await db_session.execute(
            select(SystemConfig).where(SystemConfig.key == "minio")
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return json.loads(row.value)

    async def test_connection(self, db_session) -> tuple[bool, str]:
        config = await self._load_config(db_session)
        if not config:
            return False, "MinIO 配置未设置"
        try:
            client = self._get_client(config)
            client.list_buckets()
            return True, "MinIO 连接成功"
        except Exception as e:
            return False, f"MinIO 连接失败: {str(e)}"

    async def save_original(
        self, db_session, article_title: str, html_raw: str, parsed_article
    ) -> str:
        config = await self._load_config(db_session)
        client = self._get_client(config)
        bucket = config["bucket"]

        folder = f"{article_title}/"

        client.put_object(
            bucket,
            f"{folder}original.html",
            io.BytesIO(html_raw.encode("utf-8")),
            len(html_raw.encode("utf-8")),
            content_type="text/html",
        )

        for item in parsed_article.media_items:
            if item.local_path:
                local = Path(item.local_path)
                if local.exists():
                    client.fput_object(
                        bucket,
                        f"{folder}media/{item.filename}",
                        str(local),
                    )

        for item in parsed_article.attachment_items:
            if item.local_path:
                local = Path(item.local_path)
                if local.exists():
                    client.fput_object(
                        bucket,
                        f"{folder}attachments/{item.filename}",
                        str(local),
                    )

        return folder

    async def save_rewritten(self, db_session, article_title: str, markdown_content: str) -> str:
        config = await self._load_config(db_session)
        client = self._get_client(config)
        bucket = config["bucket"]

        folder = f"{article_title}/"
        path = f"{folder}rewritten.md"
        data = markdown_content.encode("utf-8")
        client.put_object(
            bucket,
            path,
            io.BytesIO(data),
            len(data),
            content_type="text/markdown",
        )
        return path


minio_storage = MinioStorage()
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add MinIO storage service with original and rewritten saving"
```

---

### Task 8: AI Rewriter — Base + Factory

**Files:**
- Create: `app/services/rewriter/__init__.py`
- Create: `app/services/rewriter/base.py`
- Create: `app/services/rewriter/registry.py`
- Create: `app/services/rewriter/factory.py`

- [ ] **Step 1: Create app/services/rewriter/__init__.py**

```python
```

- [ ] **Step 2: Create app/services/rewriter/base.py**

```python
from abc import ABC, abstractmethod


class BaseRewriter(ABC):
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    @abstractmethod
    async def list_models(self) -> list[dict]:
        ...

    @abstractmethod
    async def rewrite(self, text: str, keep_citations: bool = False) -> str:
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        ...
```

- [ ] **Step 3: Create app/services/rewriter/registry.py**

```python
from app.services.rewriter.deepseek import DeepSeekRewriter
from app.services.rewriter.mofi import MofiRewriter
from app.services.rewriter.minimax import MiniMaxRewriter
from app.services.rewriter.openai_rewriter import OpenAIRewriter

PROVIDER_REGISTRY = {
    "deepseek": DeepSeekRewriter,
    "mofi": MofiRewriter,
    "minimax": MiniMaxRewriter,
    "openai": OpenAIRewriter,
}
```

- [ ] **Step 4: Create app/services/rewriter/factory.py**

```python
from app.services.rewriter.base import BaseRewriter

try:
    from app.services.rewriter.registry import PROVIDER_REGISTRY
except ImportError:
    PROVIDER_REGISTRY = {}


class RewriterFactory:
    @staticmethod
    def create(provider_key: str, api_key: str, base_url: str, model_name: str) -> BaseRewriter:
        if provider_key in PROVIDER_REGISTRY:
            return PROVIDER_REGISTRY[provider_key](api_key, base_url, model_name)
        from app.services.rewriter.openai_rewriter import OpenAIRewriter
        return OpenAIRewriter(api_key, base_url, model_name)
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add AI rewriter base class, registry, and factory"
```

---

### Task 9: AI Rewriter — Provider Implementations (Part 1)

**Files:**
- Create: `app/services/rewriter/deepseek.py`
- Create: `app/services/rewriter/openai_rewriter.py`

- [ ] **Step 1: Create app/services/rewriter/deepseek.py**

```python
import httpx
from app.services.rewriter.base import BaseRewriter

REWRITE_PROMPT = """你是一位资深博客作者。请将以下文章内容用你自己的话重写一遍。
要求：
- 保持原文的核心信息和观点不变
- 用博客的轻松自然口吻表达
- 不得直接复制粘贴原文的句子
- 可以调整文章结构和段落顺序
{extra}

原文内容：
{text}"""

CITATION_EXTRA = "保留以下原文引用内容（blockquote中的内容需要保留原样）：\n"


class DeepSeekRewriter(BaseRewriter):
    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [{"id": m["id"], "name": m.get("id", "")} for m in data.get("data", [])]

    async def rewrite(self, text: str, keep_citations: bool = False) -> str:
        extra = CITATION_EXTRA if keep_citations else ""
        prompt = REWRITE_PROMPT.format(extra=extra, text=text)

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def test_connection(self) -> bool:
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False
```

- [ ] **Step 2: Create app/services/rewriter/openai_rewriter.py**

```python
import httpx
from app.services.rewriter.base import BaseRewriter

REWRITE_PROMPT = """你是一位资深博客作者。请将以下文章内容用你自己的话重写一遍。
要求：
- 保持原文的核心信息和观点不变
- 用博客的轻松自然口吻表达
- 不得直接复制粘贴原文的句子
- 可以调整文章结构和段落顺序
{extra}

原文内容：
{text}"""

CITATION_EXTRA = "保留以下原文引用内容（blockquote中的内容需要保留原样）：\n"


class OpenAIRewriter(BaseRewriter):
    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [{"id": m["id"], "name": m.get("id", "")} for m in data.get("data", [])]

    async def rewrite(self, text: str, keep_citations: bool = False) -> str:
        extra = CITATION_EXTRA if keep_citations else ""
        prompt = REWRITE_PROMPT.format(extra=extra, text=text)

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def test_connection(self) -> bool:
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add DeepSeek and OpenAI rewriter implementations"
```

---

### Task 10: AI Rewriter — Provider Implementations (Part 2)

**Files:**
- Create: `app/services/rewriter/mofi.py`
- Create: `app/services/rewriter/minimax.py`

- [ ] **Step 1: Create app/services/rewriter/mofi.py**

```python
import httpx
from app.services.rewriter.base import BaseRewriter

REWRITE_PROMPT = """你是一位资深博客作者。请将以下文章内容用你自己的话重写一遍。
要求：
- 保持原文的核心信息和观点不变
- 用博客的轻松自然口吻表达
- 不得直接复制粘贴原文的句子
- 可以调整文章结构和段落顺序
{extra}

原文内容：
{text}"""

CITATION_EXTRA = "保留以下原文引用内容（blockquote中的内容需要保留原样）：\n"


class MofiRewriter(BaseRewriter):
    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [{"id": m["id"], "name": m.get("id", "")} for m in data.get("data", [])]

    async def rewrite(self, text: str, keep_citations: bool = False) -> str:
        extra = CITATION_EXTRA if keep_citations else ""
        prompt = REWRITE_PROMPT.format(extra=extra, text=text)

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def test_connection(self) -> bool:
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False
```

- [ ] **Step 2: Create app/services/rewriter/minimax.py**

```python
import httpx
from app.services.rewriter.base import BaseRewriter

REWRITE_PROMPT = """你是一位资深博客作者。请将以下文章内容用你自己的话重写一遍。
要求：
- 保持原文的核心信息和观点不变
- 用博客的轻松自然口吻表达
- 不得直接复制粘贴原文的句子
- 可以调整文章结构和段落顺序
{extra}

原文内容：
{text}"""

CITATION_EXTRA = "保留以下原文引用内容（blockquote中的内容需要保留原样）：\n"


class MiniMaxRewriter(BaseRewriter):
    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [{"id": m["id"], "name": m.get("id", "")} for m in data.get("data", [])]

    async def rewrite(self, text: str, keep_citations: bool = False) -> str:
        extra = CITATION_EXTRA if keep_citations else ""
        prompt = REWRITE_PROMPT.format(extra=extra, text=text)

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def test_connection(self) -> bool:
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False
```

- [ ] **Step 3: Verify imports**

Run: `python -c "from app.services.rewriter.mofi import MofiRewriter; from app.services.rewriter.minimax import MiniMaxRewriter; print('all rewriters OK')"`
Expected: "all rewriters OK"

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add Mofi and MiniMax rewriter implementations"
```

---

### Task 11: Halo Publisher Service

**Files:**
- Create: `app/services/publisher/__init__.py`
- Create: `app/services/publisher/halo_client.py`

- [ ] **Step 1: Create app/services/publisher/__init__.py**

```python
```

- [ ] **Step 2: Create app/services/publisher/halo_client.py**

```python
import json
import re

import httpx
from slugify import slugify

from app.models.system_config import SystemConfig
from sqlalchemy import select


class HaloClient:
    async def _load_config(self, db_session) -> dict | None:
        result = await db_session.execute(
            select(SystemConfig).where(SystemConfig.key == "halo")
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return json.loads(row.value)

    async def test_connection(self, db_session) -> tuple[bool, str]:
        config = await self._load_config(db_session)
        if not config:
            return False, "Halo 配置未设置"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{config['site_url'].rstrip('/')}/actuator/health",
                    headers={"Authorization": f"Bearer {config['api_token']}"},
                )
                if resp.status_code == 200:
                    return True, "Halo 连接成功"
                return False, f"Halo 响应异常: HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Halo 连接失败: {str(e)}"

    async def publish(
        self, db_session, title: str, content_md: str, publish_time=None
    ) -> int:
        config = await self._load_config(db_session)
        site_url = config["site_url"].rstrip("/")
        api_token = config["api_token"]

        slug = slugify(title, max_length=80)
        publish = publish_time is None

        payload = {
            "post": {
                "spec": {
                    "title": title,
                    "slug": slug,
                    "publish": publish,
                    "publishTime": publish_time.isoformat() if publish_time else None,
                },
                "apiVersion": "content.halo.run/v1alpha1",
                "kind": "Post",
                "metadata": {"name": slug},
            },
            "content": {
                "raw": content_md,
                "content": content_md,
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{site_url}/apis/api.console.halo.run/v1alpha1/posts",
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["metadata"].get("name", slug)


halo_client = HaloClient()
```

- [ ] **Step 3: Verify imports**

Run: `python -c "from app.services.publisher.halo_client import halo_client; print('halo client OK')"`
Expected: "halo client OK"

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add Halo publisher client for v2.24 API"
```

---

### Task 12: Pipeline Orchestrator

**Files:**
- Create: `app/services/pipeline.py`

- [ ] **Step 1: Create app/services/pipeline.py**

```python
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import async_session
from app.models.task import Task, TaskStatus, PublishType
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


async def _update_task(task_id: str, **kwargs):
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        for key, value in kwargs.items():
            setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return task


async def _broadcast_update(task_id: str, status: str, progress: int, stage_detail: str):
    from app.routers.ws import ws_manager
    await ws_manager.broadcast_task_update(task_id, status, progress, stage_detail)


async def _get_config(db_session, key: str) -> dict | None:
    result = await db_session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        return json.loads(row.value)
    return None


async def run_pipeline(
    task_id: str,
    urls: list[str],
    provider_key: str,
    model_name: str,
    keep_citations: bool,
    publish_type: str,
    scheduled_at: str | None,
):
    try:
        task = await _update_task(task_id, status=TaskStatus.fetching, progress=0)
        await _broadcast_update(task_id, "fetching", 0, "等待开始...")

        async with async_session() as db:
            fetch_mode = await _get_config(db, "fetch.mode") or {"value": "http"}
            provider_cfg = await _get_config(db, f"providers.{provider_key}")
            if not provider_cfg:
                raise ValueError(f"Provider {provider_key} not configured")

        mode = fetch_mode if isinstance(fetch_mode, str) else fetch_mode.get("value", "http")

        from app.services.fetcher.service import fetcher_service
        from app.services.parser.service import parser_service
        from app.services.storage.minio_client import minio_storage
        from app.services.publisher.halo_client import halo_client

        await _update_task(task_id, stage_detail="正在抓取网页内容...", progress=10)
        await _broadcast_update(task_id, "fetching", 10, "正在抓取网页内容...")
        content = await fetcher_service.fetch(urls[0], mode=mode)

        await _update_task(
            task_id,
            status=TaskStatus.parsing,
            title=content.title,
            stage_detail="正在解析文章内容和媒体文件...",
            progress=25,
        )
        await _broadcast_update(task_id, "parsing", 25, "正在解析文章内容和媒体文件...")
        parsed = await parser_service.parse(content)

        await _update_task(
            task_id,
            original_content=parsed.clean_text,
            stage_detail="正在上传原始文件到MinIO...",
            progress=40,
        )
        await _broadcast_update(task_id, "parsing", 40, "正在上传原始文件到MinIO...")

        async with async_session() as db:
            minio_path = await minio_storage.save_original(db, parsed.title, content.html_raw, parsed)

        await _update_task(
            task_id,
            status=TaskStatus.rewriting,
            minio_original_path=minio_path,
            stage_detail="AI正在重写文章...",
            progress=55,
        )
        await _broadcast_update(task_id, "rewriting", 55, "AI正在重写文章...")

        from app.services.rewriter.factory import RewriterFactory
        rewriter = RewriterFactory.create(
            provider_key,
            provider_cfg.get("api_key", ""),
            provider_cfg.get("base_url", ""),
            model_name,
        )
        rewritten = await rewriter.rewrite(parsed.clean_text, keep_citations)

        await _update_task(
            task_id,
            rewritten_content=rewritten,
            stage_detail="正在备份重写稿到MinIO...",
            progress=75,
        )
        await _broadcast_update(task_id, "rewriting", 75, "正在备份重写稿到MinIO...")

        async with async_session() as db:
            rewritten_path = await minio_storage.save_rewritten(db, parsed.title, rewritten)

        await _update_task(task_id, minio_rewritten_path=rewritten_path)

        if publish_type == "immediate":
            await _update_task(task_id, status=TaskStatus.publishing, progress=85)
            await _broadcast_update(task_id, "publishing", 85, "正在发布到Halo...")

            async with async_session() as db:
                post_id = await halo_client.publish(db, parsed.title, rewritten)

            await _update_task(
                task_id,
                status=TaskStatus.completed,
                progress=100,
                halo_post_id=post_id,
                stage_detail="已完成",
            )
            await _broadcast_update(task_id, "completed", 100, "已完成")
        else:
            scheduled_dt = datetime.fromisoformat(scheduled_at) if scheduled_at else None
            await _update_task(
                task_id,
                status=TaskStatus.scheduled,
                progress=90,
                scheduled_at=scheduled_dt,
                stage_detail=f"等待定时发布: {scheduled_at}",
            )
            await _broadcast_update(task_id, "scheduled", 90, f"等待定时发布: {scheduled_at}")

            from app.services.scheduler import scheduler_service
            scheduler_service.schedule_publish(task_id, scheduled_at, provider_key, model_name)

    except Exception as e:
        logger.exception(f"Pipeline failed for task {task_id}")
        await _update_task(
            task_id,
            status=TaskStatus.failed,
            error_msg=str(e),
            stage_detail=f"失败: {str(e)}",
        )
        await _broadcast_update(task_id, "failed", 0, f"失败: {str(e)}")
```

- [ ] **Step 2: Verify import**

Run: `python -c "from app.services.pipeline import run_pipeline; print('pipeline OK')"`
Expected: Note: will warn about missing scheduler, that's fine

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add pipeline orchestrator for full task flow"
```

---

### Task 13: Scheduler Service

**Files:**
- Create: `app/services/scheduler.py`

- [ ] **Step 1: Create app/services/scheduler.py**

```python
import asyncio
import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db import async_session
from app.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()

    def schedule_publish(self, task_id: str, scheduled_at: str, provider_key: str, model_name: str):
        if isinstance(scheduled_at, str):
            run_date = datetime.fromisoformat(scheduled_at)
        else:
            run_date = scheduled_at

        self._scheduler.add_job(
            self._execute_publish,
            "date",
            run_date=run_date,
            args=[task_id],
            id=f"publish_{task_id}",
        )
        logger.info(f"Scheduled publish for task {task_id} at {run_date}")

    async def _execute_publish(self, task_id: str):
        logger.info(f"Executing scheduled publish for task {task_id}")

        from app.services.publisher.halo_client import halo_client

        async with async_session() as db:
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if not task or task.status != TaskStatus.scheduled:
                return

            task.status = TaskStatus.publishing
            task.progress = 95
            task.stage_detail = "正在发布到Halo..."
            task.updated_at = datetime.now(timezone.utc)
            await db.commit()

            from app.routers.ws import ws_manager
            await ws_manager.broadcast_task_update(task_id, "publishing", 95, "正在发布到Halo...")

            try:
                post_id = await halo_client.publish(db, task.title, task.rewritten_content)

                result = await db.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one()
                task.status = TaskStatus.completed
                task.progress = 100
                task.halo_post_id = post_id
                task.stage_detail = "已完成"
                task.updated_at = datetime.now(timezone.utc)
                await db.commit()

                await ws_manager.broadcast_task_update(task_id, "completed", 100, "已完成")
            except Exception as e:
                result = await db.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one()
                task.status = TaskStatus.failed
                task.error_msg = str(e)
                task.stage_detail = f"发布失败: {str(e)}"
                task.updated_at = datetime.now(timezone.utc)
                await db.commit()

                await ws_manager.broadcast_task_update(task_id, "failed", 0, f"发布失败: {str(e)}")

    def shutdown(self):
        self._scheduler.shutdown()


scheduler_service = SchedulerService()
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add APScheduler service for timed publishing"
```

---

### Task 14: WebSocket Manager + API Routers

**Files:**
- Create: `app/routers/__init__.py`
- Create: `app/routers/ws.py`
- Create: `app/routers/tasks.py`
- Create: `app/routers/config.py`

- [ ] **Step 1: Create app/routers/__init__.py**

```python
```

- [ ] **Step 2: Create app/routers/ws.py**

```python
import json
from fastapi import WebSocket, WebSocketDisconnect

class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        data = await websocket.receive_text()
        msg = json.loads(data)
        if msg.get("type") == "subscribe":
            task_ids = msg.get("task_ids", [])
            for tid in task_ids:
                if tid not in self._connections:
                    self._connections[tid] = []
                self._connections[tid].append(websocket)
        else:
            if "_all" not in self._connections:
                self._connections["_all"] = []
            self._connections["_all"].append(websocket)

    def disconnect(self, websocket: WebSocket):
        for tid in list(self._connections.keys()):
            self._connections[tid] = [ws for ws in self._connections[tid] if ws != websocket]
            if not self._connections[tid]:
                del self._connections[tid]

    async def broadcast_task_update(self, task_id: str, status: str, progress: int, stage_detail: str):
        from datetime import datetime, timezone
        message = json.dumps({
            "type": "task_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "stage_detail": stage_detail,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        connections = self._connections.get(task_id, []) + self._connections.get("_all", [])
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                pass


ws_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

- [ ] **Step 3: Create app/routers/tasks.py**

```python
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select

from app.db import async_session, get_db
from app.models.task import Task, TaskStatus, PublishType
from app.schemas.task import TaskCreate, TaskResponse, TaskListResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse)
async def create_task(payload: TaskCreate, background_tasks: BackgroundTasks):
    task = Task(
        urls=payload.urls,
        keep_citations=payload.keep_citations,
        publish_type=PublishType(payload.publish_type),
        scheduled_at=payload.scheduled_at,
        model_provider=payload.model_provider,
        model_name=payload.model_name,
        status=TaskStatus.fetching,
        progress=0,
        stage_detail="等待开始...",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async with async_session() as db:
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = task.id

    from app.services.pipeline import run_pipeline

    background_tasks.add_task(
        run_pipeline,
        task_id=task_id,
        urls=payload.urls,
        provider_key=payload.model_provider,
        model_name=payload.model_name,
        keep_citations=payload.keep_citations,
        publish_type=payload.publish_type,
        scheduled_at=payload.scheduled_at.isoformat() if payload.scheduled_at else None,
    )

    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks():
    async with async_session() as db:
        result = await db.execute(
            select(Task).order_by(Task.created_at.desc())
        )
        tasks = result.scalars().all()
    return TaskListResponse(tasks=[TaskResponse.model_validate(t) for t in tasks])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)
```

- [ ] **Step 4: Create app/routers/config.py**

```python
import json
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import async_session
from app.models.system_config import SystemConfig
from app.schemas.config import (
    ConfigSaveRequest,
    ConfigResponse,
    ProviderConfig,
    MinioConfig,
    HaloConfig,
    TestConnectionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config():
    async with async_session() as db:
        result = await db.execute(select(SystemConfig))
        rows = result.scalars().all()

    providers = []
    minio_cfg = None
    halo_cfg = None
    fetch_mode = "http"

    for row in rows:
        value = json.loads(row.value)
        if row.key.startswith("providers."):
            providers.append(ProviderConfig(**value))
        elif row.key == "minio":
            minio_cfg = MinioConfig(**value)
        elif row.key == "halo":
            halo_cfg = HaloConfig(**value)
        elif row.key == "fetch.mode":
            fetch_mode = value if isinstance(value, str) else value.get("value", "http")

    return ConfigResponse(
        providers=providers,
        minio=minio_cfg,
        halo=halo_cfg,
        fetch_mode=fetch_mode,
    )


@router.post("")
async def save_config(payload: ConfigSaveRequest):
    async with async_session() as db:
        existing = await db.execute(select(SystemConfig))
        existing_keys = {r.key for r in existing.scalars().all()}

        provider_keys = set()
        for provider in payload.providers:
            key = f"providers.{provider.name.lower()}"
            provider_keys.add(key)
            value = json.dumps(provider.model_dump())

            result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                db.add(SystemConfig(key=key, value=value))

        for old_key in existing_keys:
            if old_key.startswith("providers.") and old_key not in provider_keys:
                row = await db.execute(select(SystemConfig).where(SystemConfig.key == old_key))
                row = row.scalar_one_or_none()
                if row:
                    await db.delete(row)

        if payload.minio:
            key = "minio"
            value = json.dumps(payload.minio.model_dump())
            result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                db.add(SystemConfig(key=key, value=value))

        if payload.halo:
            key = "halo"
            value = json.dumps(payload.halo.model_dump())
            result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                db.add(SystemConfig(key=key, value=value))

        key = "fetch.mode"
        value = json.dumps({"value": payload.fetch_mode})
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=key, value=value))

        await db.commit()

    return {"message": "配置已保存"}


@router.post("/test/{service}", response_model=TestConnectionResponse)
async def test_connection(service: str):
    if service == "minio":
        async with async_session() as db:
            from app.services.storage.minio_client import minio_storage
            success, message = await minio_storage.test_connection(db)
    elif service == "halo":
        async with async_session() as db:
            from app.services.publisher.halo_client import halo_client
            success, message = await halo_client.test_connection(db)
    elif service.startswith("provider."):
        provider_key = service.split(".", 1)[1]
        async with async_session() as db:
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.key == f"providers.{provider_key}")
            )
            row = result.scalar_one_or_none()
            if not row:
                raise HTTPException(status_code=404, detail="Provider not configured")
            cfg = json.loads(row.value)
            from app.services.rewriter.factory import RewriterFactory
            rewriter = RewriterFactory.create(
                provider_key,
                cfg.get("api_key", ""),
                cfg.get("base_url", ""),
                cfg.get("models", [""])[0] if cfg.get("models") else "default",
            )
            ok = await rewriter.test_connection()
            if ok:
                success, message = True, "模型供应商连接成功"
            else:
                success, message = False, "模型供应商连接失败"
    else:
        raise HTTPException(status_code=400, detail="Unknown service")

    return TestConnectionResponse(success=success, message=message)


@router.post("/models/{provider_key}")
async def list_models(provider_key: str):
    async with async_session() as db:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == f"providers.{provider_key}")
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Provider not configured")

        cfg = json.loads(row.value)
        from app.services.rewriter.factory import RewriterFactory
        rewriter = RewriterFactory.create(
            provider_key,
            cfg.get("api_key", ""),
            cfg.get("base_url", ""),
            cfg.get("models", [""])[0] if cfg.get("models") else "default",
        )
        try:
            models = await rewriter.list_models()
            return {"models": models}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add WebSocket manager, task and config API routers"
```

---

### Task 15: Page Router + Templates

**Files:**
- Create: `app/routers/pages.py`
- Create: `app/templates/base.html`
- Create: `app/templates/task_create.html`
- Create: `app/templates/task_list.html`
- Create: `app/templates/settings.html`

- [ ] **Step 1: Create app/routers/pages.py**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def page_task_create(request: Request):
    return templates.TemplateResponse("task_create.html", {"request": request})


@router.get("/tasks", response_class=HTMLResponse)
async def page_task_list(request: Request):
    return templates.TemplateResponse("task_list.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})
```

- [ ] **Step 2: Create app/templates/base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auto-Halo</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <nav class="bg-white shadow-sm border-b">
        <div class="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6">
            <a href="/" class="text-xl font-bold text-indigo-600">Auto-Halo</a>
            <a href="/" class="text-gray-600 hover:text-indigo-600">创建任务</a>
            <a href="/tasks" class="text-gray-600 hover:text-indigo-600">任务列表</a>
            <a href="/settings" class="text-gray-600 hover:text-indigo-600">系统配置</a>
        </div>
    </nav>
    <main class="max-w-6xl mx-auto px-4 py-6">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 3: Create app/templates/task_create.html**

```html
{% extends "base.html" %}
{% block content %}
<div x-data="taskCreate()" class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold mb-6">新建任务</h1>

    <div class="bg-white rounded-lg shadow p-6 space-y-5">
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">目标 URL</label>
            <template x-for="(url, idx) in urls" :key="idx">
                <div class="flex gap-2 mb-2">
                    <input type="url" x-model="urls[idx]" class="flex-1 border rounded px-3 py-2 text-sm" placeholder="https://...">
                    <button @click="removeUrl(idx)" class="text-red-500 hover:text-red-700 px-2" x-show="urls.length > 1">&times;</button>
                </div>
            </template>
            <button @click="addUrl" class="text-sm text-indigo-600 hover:text-indigo-800">+ 添加更多URL</button>
        </div>

        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">AI 重写配置</label>
            <div class="grid grid-cols-2 gap-3">
                <select x-model="provider" @change="fetchModels" class="border rounded px-3 py-2 text-sm">
                    <option value="">选择供应商</option>
                    <template x-for="p in providers" :key="p">
                        <option :value="p" x-text="p"></option>
                    </template>
                </select>
                <select x-model="model" class="border rounded px-3 py-2 text-sm">
                    <option value="">选择模型</option>
                    <template x-for="m in models" :key="m.id">
                        <option :value="m.id" x-text="m.name || m.id"></option>
                    </template>
                </select>
            </div>
            <label class="flex items-center gap-2 mt-3 text-sm text-gray-600">
                <input type="checkbox" x-model="keepCitations">
                保留原文引用
            </label>
        </div>

        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">发布设置</label>
            <div class="flex items-center gap-4">
                <label class="flex items-center gap-2 text-sm">
                    <input type="radio" x-model="publishType" value="immediate">
                    立即发布
                </label>
                <label class="flex items-center gap-2 text-sm">
                    <input type="radio" x-model="publishType" value="scheduled">
                    定时发布
                </label>
                <input type="datetime-local" x-model="scheduledAt" x-show="publishType === 'scheduled'" class="border rounded px-3 py-2 text-sm">
            </div>
        </div>

        <button @click="submit" class="w-full bg-indigo-600 text-white rounded-lg py-2.5 hover:bg-indigo-700 font-medium" :disabled="submitting">
            <span x-show="!submitting">创建任务</span>
            <span x-show="submitting">创建中...</span>
        </button>
    </div>
</div>

<script>
function taskCreate() {
    return {
        urls: [''],
        provider: '',
        model: '',
        keepCitations: false,
        publishType: 'immediate',
        scheduledAt: '',
        providers: [],
        models: [],
        submitting: false,

        async init() {
            const resp = await fetch('/api/config');
            const cfg = await resp.json();
            this.providers = cfg.providers.map(p => p.name.toLowerCase());
            if (this.providers.length > 0) {
                this.provider = this.providers[0];
                this.fetchModels();
            }
        },

        addUrl() { this.urls.push(''); },
        removeUrl(idx) { this.urls.splice(idx, 1); },

        async fetchModels() {
            if (!this.provider) return;
            this.models = [];
            this.model = '';
            try {
                const resp = await fetch(`/api/config/models/${this.provider}`, { method: 'POST' });
                const data = await resp.json();
                this.models = data.models || [];
                if (this.models.length > 0) this.model = this.models[0].id;
            } catch (e) { console.error(e); }
        },

        async submit() {
            this.submitting = true;
            try {
                const payload = {
                    urls: this.urls.filter(u => u.trim()),
                    keep_citations: this.keepCitations,
                    publish_type: this.publishType,
                    scheduled_at: this.publishType === 'scheduled' ? this.scheduledAt : null,
                    model_provider: this.provider,
                    model_name: this.model,
                };
                const resp = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                if (resp.ok) {
                    window.location.href = '/tasks';
                } else {
                    alert('创建失败');
                }
            } catch (e) { alert('创建失败: ' + e.message); }
            this.submitting = false;
        }
    }
}
</script>
{% endblock %}
```

- [ ] **Step 4: Create app/templates/task_list.html**

```html
{% extends "base.html" %}
{% block content %}
<div x-data="taskList()" class="max-w-4xl mx-auto">
    <h1 class="text-2xl font-bold mb-6">任务列表</h1>

    <div class="space-y-4">
        <template x-for="task in tasks" :key="task.id">
            <div class="bg-white rounded-lg shadow p-5">
                <div class="flex items-center justify-between mb-2">
                    <h3 class="font-semibold text-gray-800" x-text="task.title || '未命名任务'"></h3>
                    <span class="px-2.5 py-0.5 rounded-full text-xs font-medium"
                        :class="statusClass(task.status)"
                        x-text="statusLabel(task.status)"></span>
                </div>

                <div class="w-full bg-gray-200 rounded-full h-2.5 mb-2">
                    <div class="h-2.5 rounded-full transition-all duration-500"
                        :class="progressColor(task.status)"
                        :style="'width: ' + task.progress + '%'"></div>
                </div>

                <p class="text-sm text-gray-500 mb-3" x-text="task.stage_detail"></p>

                <div class="flex gap-2 text-sm" x-show="task.status === 'completed' || task.status === 'scheduled' || task.status === 'failed'">
                    <button @click="preview(task, 'original')" class="text-indigo-600 hover:text-indigo-800" x-show="task.original_content">预览原文</button>
                    <button @click="preview(task, 'rewritten')" class="text-indigo-600 hover:text-indigo-800" x-show="task.rewritten_content">预览重写稿</button>
                </div>
            </div>
        </template>

        <div x-show="tasks.length === 0" class="text-center text-gray-400 py-12">
            暂无任务，<a href="/" class="text-indigo-600">创建第一个任务</a>
        </div>
    </div>

    <div x-show="showPreview" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showPreview=false">
        <div class="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            <div class="flex items-center justify-between p-4 border-b">
                <div class="flex gap-3">
                    <button @click="previewTab='original'" :class="previewTab==='original' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'" class="pb-1 px-1 text-sm font-medium">原文</button>
                    <button @click="previewTab='rewritten'" :class="previewTab==='rewritten' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'" class="pb-1 px-1 text-sm font-medium">重写稿</button>
                </div>
                <button @click="showPreview=false" class="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div class="p-4 overflow-y-auto flex-1 whitespace-pre-wrap text-sm text-gray-700" x-text="previewContent"></div>
        </div>
    </div>
</div>

<script>
function taskList() {
    return {
        tasks: [],
        showPreview: false,
        previewTab: 'original',
        previewContent: '',
        ws: null,
        currentPreviewTask: null,

        async init() {
            await this.loadTasks();
            this.connectWs();
        },

        async loadTasks() {
            const resp = await fetch('/api/tasks');
            const data = await resp.json();
            this.tasks = data.tasks || [];
        },

        connectWs() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(protocol + '//' + location.host + '/ws/tasks');

            this.ws.onopen = () => {
                const activeIds = this.tasks.filter(t => !['completed', 'failed'].includes(t.status)).map(t => t.id);
                if (activeIds.length > 0) {
                    this.ws.send(JSON.stringify({ type: 'subscribe', task_ids: activeIds }));
                }
            };

            this.ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'task_update') {
                    const idx = this.tasks.findIndex(t => t.id === msg.task_id);
                    if (idx >= 0) {
                        this.tasks[idx].status = msg.status;
                        this.tasks[idx].progress = msg.progress;
                        this.tasks[idx].stage_detail = msg.stage_detail;
                        if (msg.status === 'completed' || msg.status === 'failed') {
                            this.loadTasks();
                        }
                    }
                }
            };
        },

        statusLabel(status) {
            const map = {
                fetching: '抓取中', parsing: '解析中', rewriting: '重写中',
                publishing: '发布中', scheduled: '定时发布中', completed: '已完成', failed: '失败'
            };
            return map[status] || status;
        },

        statusClass(status) {
            const map = {
                fetching: 'bg-blue-100 text-blue-700', parsing: 'bg-blue-100 text-blue-700',
                rewriting: 'bg-blue-100 text-blue-700', publishing: 'bg-blue-100 text-blue-700',
                scheduled: 'bg-orange-100 text-orange-700', completed: 'bg-green-100 text-green-700',
                failed: 'bg-red-100 text-red-700'
            };
            return map[status] || 'bg-gray-100 text-gray-700';
        },

        progressColor(status) {
            if (status === 'failed') return 'bg-red-500';
            if (status === 'completed') return 'bg-green-500';
            if (status === 'scheduled') return 'bg-orange-500';
            return 'bg-blue-500';
        },

        preview(task, tab) {
            this.currentPreviewTask = task;
            this.previewTab = tab;
            this.previewContent = tab === 'original' ? task.original_content : task.rewritten_content;
            this.showPreview = true;
        },
    }
}
</script>
{% endblock %}
```

- [ ] **Step 5: Create app/templates/settings.html**

```html
{% extends "base.html" %}
{% block content %}
<div x-data="settingsPage()" class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold mb-6">系统配置</h1>

    <div class="space-y-6">
        <div class="bg-white rounded-lg shadow p-6">
            <h2 class="text-lg font-semibold mb-4">模型供应商</h2>

            <template x-for="(provider, pidx) in providers" :key="pidx">
                <div class="border rounded-lg p-4 mb-3">
                    <div class="flex justify-between items-center mb-3">
                        <input type="text" x-model="provider.name" class="font-medium border rounded px-2 py-1 text-sm" placeholder="供应商名称">
                        <button @click="removeProvider(pidx)" class="text-red-500 text-sm hover:text-red-700">删除</button>
                    </div>
                    <div class="space-y-2">
                        <input type="text" x-model="provider.base_url" class="w-full border rounded px-3 py-2 text-sm" placeholder="Base URL">
                        <input type="password" x-model="provider.api_key" class="w-full border rounded px-3 py-2 text-sm" placeholder="API Key" @focus="provider.api_key=''" x-bind:placeholder="provider.api_key ? '••••••••' : 'API Key'">
                        <div class="flex gap-2">
                            <button @click="fetchProviderModels(provider)" class="text-sm px-3 py-1.5 border rounded hover:bg-gray-50">获取模型列表</button>
                            <button @click="testProviderConnection(provider)" class="text-sm px-3 py-1.5 border rounded hover:bg-gray-50" x-text="provider.testing ? '测试中...' : '测试连接'"></button>
                        </div>
                        <div x-show="provider.models.length > 0" class="text-xs text-gray-500">
                            可用模型: <span x-text="provider.models.map(m => m.id).join(', ')"></span>
                        </div>
                    </div>
                </div>
            </template>

            <div class="flex gap-2">
                <button @click="addProvider" class="text-sm text-indigo-600 hover:text-indigo-800">+ 添加供应商</button>
                <span class="text-gray-300">|</span>
                <div class="relative" x-data="{ open: false }">
                    <button @click="open = !open" class="text-sm text-indigo-600 hover:text-indigo-800">从预设模板添加</button>
                    <div x-show="open" @click.outside="open=false" class="absolute left-0 top-6 bg-white border rounded-lg shadow-lg py-1 z-10">
                        <template x-for="preset in presets" :key="preset.name">
                            <button @click="addPreset(preset); open=false" class="block w-full text-left px-4 py-2 text-sm hover:bg-gray-50" x-text="preset.name"></button>
                        </template>
                    </div>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
            <h2 class="text-lg font-semibold mb-4">MinIO 存储</h2>
            <div class="space-y-3">
                <input type="text" x-model="minio.endpoint" class="w-full border rounded px-3 py-2 text-sm" placeholder="Endpoint (e.g. play.min.io:9000)">
                <input type="text" x-model="minio.access_key" class="w-full border rounded px-3 py-2 text-sm" placeholder="Access Key">
                <input type="password" x-model="minio.secret_key" class="w-full border rounded px-3 py-2 text-sm" placeholder="Secret Key" @focus="minio.secret_key=''" x-bind:placeholder="minio.secret_key ? '••••••••' : 'Secret Key'">
                <input type="text" x-model="minio.bucket" class="w-full border rounded px-3 py-2 text-sm" placeholder="Bucket Name">
                <button @click="testConnection('minio')" class="text-sm px-3 py-1.5 border rounded hover:bg-gray-50" x-text="minio.testing ? '测试中...' : '测试连接'"></button>
            </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
            <h2 class="text-lg font-semibold mb-4">Halo 发布</h2>
            <div class="space-y-3">
                <input type="url" x-model="halo.site_url" class="w-full border rounded px-3 py-2 text-sm" placeholder="站点地址 (e.g. https://blog.example.com)">
                <input type="password" x-model="halo.api_token" class="w-full border rounded px-3 py-2 text-sm" placeholder="API Token" @focus="halo.api_token=''" x-bind:placeholder="halo.api_token ? '••••••••' : 'API Token'">
                <button @click="testConnection('halo')" class="text-sm px-3 py-1.5 border rounded hover:bg-gray-50" x-text="halo.testing ? '测试中...' : '测试连接'"></button>
            </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
            <h2 class="text-lg font-semibold mb-4">抓取设置</h2>
            <div class="flex gap-4">
                <label class="flex items-center gap-2 text-sm">
                    <input type="radio" x-model="fetchMode" value="http">
                    HTTP快速抓取
                </label>
                <label class="flex items-center gap-2 text-sm">
                    <input type="radio" x-model="fetchMode" value="browser">
                    浏览器渲染（更完整）
                </label>
            </div>
        </div>

        <button @click="save" class="w-full bg-indigo-600 text-white rounded-lg py-2.5 hover:bg-indigo-700 font-medium" :disabled="saving">
            <span x-show="!saving">保存所有配置</span>
            <span x-show="saving">保存中...</span>
        </button>

        <div x-show="toast" x-text="toast" class="fixed bottom-4 right-4 bg-gray-800 text-white px-4 py-2 rounded-lg shadow text-sm"></div>
    </div>
</div>

<script>
function settingsPage() {
    return {
        providers: [],
        minio: { endpoint: '', access_key: '', secret_key: '', bucket: '', testing: false },
        halo: { site_url: '', api_token: '', testing: false },
        fetchMode: 'http',
        saving: false,
        toast: '',

        presets: [
            { name: 'DeepSeek', base_url: 'https://api.deepseek.com/v1', api_key: '' },
            { name: '模力方舟', base_url: 'https://ai.gitee.com/v1', api_key: '' },
            { name: 'MiniMax', base_url: 'https://api.minimax.chat/v1', api_key: '' },
            { name: 'OpenAI', base_url: 'https://api.openai.com/v1', api_key: '' },
        ],

        async init() {
            const resp = await fetch('/api/config');
            const cfg = await resp.json();
            this.providers = cfg.providers.map(p => ({
                name: p.name, api_key: p.api_key, base_url: p.base_url,
                models: p.models || [], testing: false,
            }));
            if (cfg.minio) this.minio = { ...this.minio, ...cfg.minio, testing: false };
            if (cfg.halo) this.halo = { ...this.halo, ...cfg.halo, testing: false };
            this.fetchMode = cfg.fetch_mode || 'http';
        },

        addProvider() {
            this.providers.push({ name: '', api_key: '', base_url: '', models: [], testing: false });
        },

        removeProvider(idx) { this.providers.splice(idx, 1); },

        addPreset(preset) {
            this.providers.push({ ...preset, models: [], testing: false });
        },

        async fetchProviderModels(provider) {
            if (!provider.name) return;
            try {
                const resp = await fetch(`/api/config/models/${provider.name.toLowerCase()}`, { method: 'POST' });
                const data = await resp.json();
                provider.models = data.models || [];
                this.showToast('模型列表获取成功');
            } catch (e) {
                this.showToast('获取模型列表失败: ' + e.message);
            }
        },

        async testConnection(service) {
            let url;
            if (service === 'minio') {
                this.minio.testing = true;
                url = '/api/config/test/minio';
            } else if (service === 'halo') {
                this.halo.testing = true;
                url = '/api/config/test/halo';
            }
            try {
                const resp = await fetch(url, { method: 'POST' });
                const data = await resp.json();
                this.showToast(data.message);
            } catch (e) {
                this.showToast('测试失败: ' + e.message);
            }
            if (service === 'minio') this.minio.testing = false;
            if (service === 'halo') this.halo.testing = false;
        },

        async testProviderConnection(provider) {
            if (!provider.name) return;
            provider.testing = true;
            try {
                const resp = await fetch(`/api/config/test/provider.${provider.name.toLowerCase()}`, { method: 'POST' });
                const data = await resp.json();
                this.showToast(data.message);
            } catch (e) {
                this.showToast('测试失败: ' + e.message);
            }
            provider.testing = false;
        },

        async save() {
            this.saving = true;
            try {
                const payload = {
                    providers: this.providers,
                    minio: this.minio,
                    halo: this.halo,
                    fetch_mode: this.fetchMode,
                };
                const resp = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                if (resp.ok) {
                    this.showToast('配置保存成功');
                } else {
                    this.showToast('保存失败');
                }
            } catch (e) {
                this.showToast('保存失败: ' + e.message);
            }
            this.saving = false;
        },

        showToast(msg) {
            this.toast = msg;
            setTimeout(() => { this.toast = ''; }, 3000);
        },
    }
}
</script>
{% endblock %}
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add page router and all three page templates with Alpine.js"
```

---

### Task 16: FastAPI Main Application

**Files:**
- Create: `app/main.py`

- [ ] **Step 1: Create app/main.py**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db, Base, engine
from app.routers import tasks, config, pages, ws

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield
    from app.services.scheduler import scheduler_service
    scheduler_service.shutdown()
    logger.info("Scheduler shut down")


app = FastAPI(title="Auto-Halo", version="0.1.0", lifespan=lifespan)

app.include_router(tasks.router)
app.include_router(config.router)
app.include_router(pages.router)
app.add_websocket_route("/ws/tasks", ws.websocket_endpoint)

try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception:
    pass
```

- [ ] **Step 2: Verify the app starts**

Run: `python run.py` (in a new terminal, Ctrl+C after confirming it starts)
Expected: "Uvicorn running on http://0.0.0.0:8000"

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add FastAPI main application with routers and WebSocket"
```

---

### Task 17: Docker Deployment

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m playwright install chromium --with-deps

COPY . .

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "run.py"]
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
version: "3.8"

services:
  auto-halo:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./app:/app/app
      - ./run.py:/app/run.py
      - ./requirements.txt:/app/requirements.txt
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/auto-halo.db
    restart: unless-stopped
```

- [ ] **Step 3: Create .env.example**

```
DATABASE_URL=sqlite+aiosqlite:///data/auto-halo.db
HOST=0.0.0.0
PORT=8000
SECRET_KEY=change-me-to-a-random-string
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add Docker deployment files"
```

---

### Task 18: Final Integration Test & Fixes

- [ ] **Step 1: Install dependencies and start the app**

Run: `pip install -r requirements.txt` then `python run.py`

- [ ] **Step 2: Verify all pages load**

Open in browser:
- `http://localhost:8000/` — Task Create page loads
- `http://localhost:8000/tasks` — Task List page loads
- `http://localhost:8000/settings` — Settings page loads

- [ ] **Step 3: Verify API endpoints**

Run: `curl http://localhost:8000/api/tasks` (or browser visit)
Expected: `{"tasks": []}`

Run: `curl http://localhost:8000/api/config`
Expected: `{"providers": [], "minio": null, "halo": null, "fetch_mode": "http"}`

- [ ] **Step 4: Fix any import errors or runtime issues found during startup**

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration test fixes"
```