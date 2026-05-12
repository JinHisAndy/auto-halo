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