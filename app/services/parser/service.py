import logging
import mimetypes
import os
import re
import tempfile
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.fetcher.base import FetchedContent

logger = logging.getLogger(__name__)


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
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff", ".tif", ".ico", ".avif"}
    VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".wmv"}
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".wma"}
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
        "image/x-icon": ("image", ".ico"),
        "image/avif": ("image", ".avif"),
        "video/mp4": ("video", ".mp4"),
        "video/webm": ("video", ".webm"),
        "video/quicktime": ("video", ".mov"),
        "video/x-msvideo": ("video", ".avi"),
        "video/x-matroska": ("video", ".mkv"),
        "audio/mpeg": ("audio", ".mp3"),
        "audio/mp3": ("audio", ".mp3"),
        "audio/wav": ("audio", ".wav"),
        "audio/wave": ("audio", ".wav"),
        "audio/ogg": ("audio", ".ogg"),
        "audio/mp4": ("audio", ".m4a"),
        "audio/x-m4a": ("audio", ".m4a"),
        "audio/aac": ("audio", ".aac"),
        "audio/flac": ("audio", ".flac"),
    }

    @staticmethod
    def _normalise_ext(ext: str) -> str:
        canon = {".jpeg": ".jpg", ".tiff": ".tif"}
        return canon.get(ext, ext)

    @staticmethod
    def _extension_from_url(url: str) -> str:
        bare = urlparse(url).path.lower().split("?")[0].split("#")[0].rstrip("/")
        last = bare.rsplit("/", 1)[-1]
        if "." in last:
            ext = "." + last.rsplit(".", 1)[-1]
            return ext
        return ""

    def _classify_url(self, url: str) -> str:
        path = urlparse(url).path.lower().split("?")[0]
        ext = os.path.splitext(path)[1]
        if ext in self.IMAGE_EXTENSIONS:
            return "image"
        if ext in self.VIDEO_EXTENSIONS:
            return "video"
        if ext in self.AUDIO_EXTENSIONS:
            return "audio"
        if self._looks_like_wechat_image_cdn(url):
            return "image"
        if "voice/getvoice" in url:
            return "audio"
        direct_media_type = self._looks_like_direct_media(url)
        if direct_media_type:
            return direct_media_type
        return "attachment"

    @staticmethod
    def _looks_like_wechat_image_cdn(url: str) -> bool:
        return "mmbiz.qpic.cn" in url

    @staticmethod
    def _looks_like_direct_media(url: str) -> str | None:
        if re.search(r"\.(jpg|jpeg|png|gif|webp)\b", url, re.IGNORECASE):
            return "image"
        if re.search(r"\.(mp4|webm|mov|avi|mkv)\b", url, re.IGNORECASE):
            return "video"
        if re.search(r"\.(mp3|wav|ogg|m4a|aac|flac)\b", url, re.IGNORECASE):
            return "audio"
        return None

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
        article_referer = content.source_url or headers["Referer"]
        async with httpx.AsyncClient(timeout=120, follow_redirects=True, headers=headers) as client:
            for idx, url in enumerate(content.media_urls):
                try:
                    req_headers = dict(headers)
                    if self._looks_like_wechat_image_cdn(url):
                        req_headers["Referer"] = article_referer
                        req_headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                    elif "mp.weixin.qq.com" in url:
                        req_headers["Referer"] = article_referer
                    elif "res.wx.qq.com" in url:
                        req_headers["Referer"] = article_referer
                    resp = await client.get(url, headers=req_headers)
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "")
                    file_type, ext = self._classify_content_type(content_type)
                    if ext == ".bin":
                        file_type = self._classify_url(url)
                        ext = self._extension_from_url(url) or ".bin"
                        ext = self._normalise_ext(ext)
                    if ext == ".bin" and file_type == "image":
                        ext = ".jpg"
                    filename = f"{file_type}_{idx:03d}{ext}"
                    tmp_path = os.path.join(tempfile.gettempdir(), f"auto_halo_{filename}")
                    with open(tmp_path, "wb") as f:
                        f.write(resp.content)
                    item = MediaItem(url=url, file_type=file_type, filename=filename, local_path=tmp_path)
                except Exception as exc:
                    file_type = self._classify_url(url)
                    ext = self._extension_from_url(url) or ".bin"
                    ext = self._normalise_ext(ext)
                    if ext == ".bin" and file_type == "image":
                        ext = ".jpg"
                    filename = f"{file_type}_{idx:03d}{ext}"
                    item = MediaItem(url=url, file_type=file_type, filename=filename, local_path="")
                    logger.debug("Failed to download media %s: %s", url, exc)

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
        media_attrs = {"href", "src", "alt", "data-src", "data-original", "data-type",
                       "data-lazy-src", "srcset", "poster", "controls", "width", "height"}
        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                if attr not in media_attrs:
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
