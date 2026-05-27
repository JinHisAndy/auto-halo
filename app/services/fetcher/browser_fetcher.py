from bs4 import BeautifulSoup
from readability import Document

from app.services.fetcher.base import FetchedContent
from app.services.fetcher.http_fetcher import (
    _extract_media_urls,
    _extract_body_html,
    _extract_with_readability,
    _extract_with_trafilatura,
    _extract_with_wechat_dom_priority,
    _is_wechat_url,
    _process_summary_html,
)


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
    title = title or doc.title()

    text_content = ""
    rich_html = ""

    if _is_wechat_url(url):
        wechat_dom_result = _extract_with_wechat_dom_priority(html, url)
        if wechat_dom_result:
            text_content, rich_html = wechat_dom_result
        else:
            traf_result = _extract_with_trafilatura(html, url)
            if traf_result:
                text_content, clean_html = traf_result
                wechat_body = _extract_body_html(html, url)
                wechat_traf = _extract_with_trafilatura(wechat_body, url)
                if wechat_traf and len(wechat_traf[0]) > len(text_content):
                    text_content, clean_html = wechat_traf
                rich_html = _process_summary_html(clean_html, url)
            else:
                title_fb, text_content, summary_html = _extract_with_readability(html, url)
                title = title_fb or title
                if len(text_content) < 100:
                    wechat_body = _extract_body_html(html, url)
                    wechat_title, wc_text, wc_summary = _extract_with_readability(wechat_body, url)
                    title = wechat_title or title
                    text_content = wc_text or text_content
                    summary_html = wc_summary or summary_html
                rich_html = _process_summary_html(summary_html, url)
    else:
        title_fb, text_content, summary_html = _extract_with_readability(html, url)
        title = title_fb or title
        rich_html = _process_summary_html(summary_html, url)

    media_urls = _extract_media_urls(html, url)

    return FetchedContent(
        title=title,
        html_raw=html,
        text_content=text_content,
        rich_html=rich_html,
        media_urls=media_urls,
    )