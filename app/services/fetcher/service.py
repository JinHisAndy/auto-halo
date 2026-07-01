import logging

from app.services.fetcher.base import FetchedContent
from app.services.fetcher.http_fetcher import fetch_http, _detect_anti_crawl
from app.services.fetcher.browser_fetcher import fetch_browser

logger = logging.getLogger(__name__)


class FetcherService:
    async def fetch(self, url: str, mode: str = "http") -> FetchedContent:
        if mode == "http":
            content = await fetch_http(url)
            if _detect_anti_crawl(content.html_raw or ""):
                logger.warning("HTTP fetch hit anti-crawl page for %s, falling back to browser", url)
                return await fetch_browser(url)
            if len(content.text_content.strip()) >= 50:
                return content
            logger.warning(
                "HTTP fetch returned insufficient content (%d chars) for %s, falling back to browser",
                len(content.text_content.strip()), url,
            )
            return await fetch_browser(url)
        else:
            return await fetch_browser(url)


fetcher_service = FetcherService()