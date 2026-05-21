import mimetypes
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
    rich_html: str
    media_items: list[MediaItem] = field(default_factory=list)
    attachment_items: list[MediaItem] = field(default_factory=list)


class ParserService:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}
    VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}
    ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar", ".7z"}

    CONTENT_TYPE_MAP = {
        "image/jpeg": ("image", ".jpg"),
        "image/jpg": ("image", ".jpg"),
        "image/png": ("image", ".png"),
        "image/gif": ("image", ".gif"),
        "image/webp": ("image", ".webp"),
        "image/svg+xml": ("image", ".svg"),
        "image/bmp": ("image", ".bmp"),
        "image/tiff": ("image", ".tiff"),
        "video/mp4": ("video", ".mp4"),
        "video/webm": ("video", ".webm"),
        "video/quicktime": ("video", ".mov"),
        "video/x-msvideo": ("video", ".avi"),
        "audio/mpeg": ("audio", ".mp3"),
        "audio/wav": ("audio", ".wav"),
        "audio/ogg": ("audio", ".ogg"),
        "audio/mp4": ("audio", ".m4a"),
        "audio/x-m4a": ("audio", ".m4a"),
    }

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

    def _classify_content_type(self, content_type: str) -> tuple[str, str]:
        content_type = content_type.split(";")[0].strip().lower()
        if content_type in self.CONTENT_TYPE_MAP:
            return self.CONTENT_TYPE_MAP[content_type]
        if content_type.startswith("image/"):
            ext = mimetypes.guess_extension(content_type) or ".bin"
            return ("image", ext)
        if content_type.startswith("video/"):
            ext = mimetypes.guess_extension(content_type) or ".bin"
            return ("video", ext)
        if content_type.startswith("audio/"):
            ext = mimetypes.guess_extension(content_type) or ".bin"
            return ("audio", ext)
        return ("attachment", ".bin")

    async def parse(self, content: FetchedContent) -> ParsedArticle:
        sanitized_title = re.sub(r'[<>:"/\\|?*]', "_", content.title or "untitled")[:200]
        rich_html = content.rich_html or self._clean_html(content.html_raw)

        media_items = []
        attachment_items = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://mp.weixin.qq.com/",
        }
        async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=headers) as client:
            for idx, url in enumerate(content.media_urls):
                try:
                    req_headers = dict(headers)
                    if "mmbiz.qpic.cn" in url or "mp.weixin.qq.com" in url:
                        req_headers["Referer"] = "https://mp.weixin.qq.com/"
                    resp = await client.get(url, headers=req_headers)
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "")
                    file_type, ext = self._classify_content_type(content_type)
                    if ext == ".bin":
                        file_type = self._classify_url(url)
                        ext = os.path.splitext(urlparse(url).path.lower().split("?")[0])[1] or ".bin"
                    filename = f"{file_type}_{idx:03d}{ext}"
                    tmp_path = os.path.join(tempfile.gettempdir(), f"auto_halo_{filename}")
                    with open(tmp_path, "wb") as f:
                        f.write(resp.content)
                    item = MediaItem(url=url, file_type=file_type, filename=filename, local_path=tmp_path)
                except Exception:
                    file_type = self._classify_url(url)
                    ext = os.path.splitext(urlparse(url).path.lower().split("?")[0])[1] or ".bin"
                    filename = f"{file_type}_{idx:03d}{ext}"
                    item = MediaItem(url=url, file_type=file_type, filename=filename, local_path="")

                if file_type in ("image", "video", "audio"):
                    media_items.append(item)
                else:
                    attachment_items.append(item)

        clean_text = self._post_process_text(content.text_content)

        return ParsedArticle(
            title=sanitized_title,
            clean_text=clean_text,
            rich_html=rich_html,
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
