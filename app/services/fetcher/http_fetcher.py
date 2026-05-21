import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from readability import Document

from app.services.fetcher.base import FetchedContent


def _process_summary_html(summary_html: str, base_url: str) -> str:
    soup = BeautifulSoup(summary_html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    allowed = {"img": ["src", "data-src", "data-original", "data-type", "alt", "width", "height", "class", "style"],
               "a": ["href"], "blockquote": [], "pre": [], "code": [], "table": [], "tr": [], "td": [], "th": [],
               "ul": [], "ol": [], "li": [], "h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": [],
               "p": [], "br": [], "b": [], "strong": [], "i": [], "em": [], "u": [], "span": [], "div": [],
               "section": [], "figure": [], "figcaption": [],
               "video": ["src", "controls"], "audio": ["src", "controls"], "source": ["src"]}
    for tag in soup.find_all(True):
        if tag.name not in allowed:
            tag.unwrap()
        else:
            for attr in list(tag.attrs):
                if attr not in allowed.get(tag.name, []):
                    del tag[attr]

    body = soup.find("body") or soup
    for img in body.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if src:
            img["src"] = urljoin(base_url, src)
    return str(body)


async def fetch_http(url: str) -> FetchedContent:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": url,
    }
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    doc = Document(html)
    title = doc.title()
    summary_html = doc.summary()

    rich_html = _process_summary_html(summary_html, url)
    soup = BeautifulSoup(summary_html, "lxml")
    plain_text = soup.get_text(separator="\n", strip=True)

    media_urls = _extract_media_urls(html, url)

    return FetchedContent(
        title=title,
        html_raw=html,
        text_content=plain_text,
        rich_html=rich_html,
        media_urls=media_urls,
    )


def _extract_media_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls = set()

    for tag in soup.find_all("img"):
        src = tag.get("data-src") or tag.get("data-original") or tag.get("data-url") or tag.get("data-lazy-src") or tag.get("src")
        if src:
            full = urljoin(base_url, src.split("#")[0])
            if not full.startswith("data:"):
                urls.add(full)

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