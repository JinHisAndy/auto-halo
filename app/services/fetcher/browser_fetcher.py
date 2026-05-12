from urllib.parse import urljoin

from bs4 import BeautifulSoup
from readability import Document

from app.services.fetcher.base import FetchedContent
from app.services.fetcher.http_fetcher import _extract_media_urls, _process_summary_html


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

    rich_html = _process_summary_html(summary_html, url)
    soup = BeautifulSoup(summary_html, "lxml")
    text_content = soup.get_text(separator="\n", strip=True)

    media_urls = _extract_media_urls(html, url)

    return FetchedContent(
        title=title,
        html_raw=html,
        text_content=text_content,
        rich_html=rich_html,
        media_urls=media_urls,
    )