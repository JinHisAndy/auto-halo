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