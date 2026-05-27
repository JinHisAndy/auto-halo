import logging
import re
from urllib.parse import urljoin

import httpx
import trafilatura
from bs4 import BeautifulSoup
from readability import Document

from app.services.fetcher.base import FetchedContent

logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 50


def _is_wechat_url(url: str) -> bool:
    return "mp.weixin.qq.com" in url


def _preprocess_html(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for img in soup.find_all("img"):
        ds = img.get("data-src") or img.get("data-original") or img.get("data-lazy-src") or img.get("data-url")
        if ds:
            img["src"] = urljoin(base_url, ds)
    return str(soup)


def _extract_body_html(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if _is_wechat_url(url):
        js_content = soup.find(id="js_content")
        if js_content:
            style = js_content.get("style", "")
            js_content["style"] = style.replace("visibility: hidden", "visibility: visible")
            return _preprocess_html(str(js_content), url)
    body = soup.find("body") or soup
    return _preprocess_html(str(body), url)


def _process_summary_html(summary_html: str, base_url: str) -> str:
    soup = BeautifulSoup(summary_html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    allowed = {
        "img": ["src", "data-src", "data-original", "data-type", "alt", "width", "height", "class", "style"],
        "a": ["href"],
        "blockquote": [], "pre": [], "code": [], "table": [], "tr": [], "td": [], "th": [],
        "ul": [], "ol": [], "li": [], "h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": [],
        "p": [], "br": [], "b": [], "strong": [], "i": [], "em": [], "u": [], "span": [], "div": [],
        "section": [], "figure": [], "figcaption": [],
        "video": ["src", "controls", "width", "height", "poster", "class", "style"],
        "audio": ["src", "controls", "class", "style"],
        "source": ["src", "srcset", "data-src", "data-srcset", "type", "media"],
        "iframe": ["data-src", "src", "width", "height", "frameborder", "allowfullscreen", "class", "style"],
        "mp-common-videosnap": ["data-src", "data-type", "class", "style"],
        "mpvoice": ["voice_encode_fileid", "name", "play_length", "class", "style"],
        "picture": [],
    }
    for tag in soup.find_all(True):
        if tag.name not in allowed:
            tag.unwrap()
        else:
            for attr in list(tag.attrs):
                if attr not in allowed.get(tag.name, []):
                    del tag[attr]

    body = soup.find("body") or soup
    for img in body.find_all("img"):
        if _is_wechat_url(base_url):
            src = img.get("data-src") or img.get("data-original") or img.get("src")
        else:
            src = img.get("src") or img.get("data-src") or img.get("data-original")
        if src:
            img["src"] = urljoin(base_url, src)

    for iframe in body.find_all("iframe"):
        data_src = iframe.get("data-src")
        if data_src and not iframe.get("src"):
            iframe["src"] = urljoin(base_url, data_src)

    for mp_video in body.find_all("mp-common-videosnap"):
        data_src = mp_video.get("data-src")
        if data_src:
            video_url = urljoin(base_url, data_src)
            container = soup.new_tag("figure")
            link = soup.new_tag("a", href=video_url)
            link.string = "[微信视频]"
            container.append(link)
            mp_video.replace_with(container)

    for mp_voice in body.find_all("mpvoice"):
        fileid = mp_voice.get("voice_encode_fileid")
        name = mp_voice.get("name", "")
        if fileid:
            audio_url = f"https://res.wx.qq.com/voice/getvoice?mediaid={fileid}"
            new_tag = soup.new_tag("audio")
            new_tag["src"] = audio_url
            new_tag["controls"] = ""
            if name:
                new_tag["data-name"] = name
            mp_voice.replace_with(new_tag)

    for picture in body.find_all("picture"):
        img_tag = picture.find("img")
        if img_tag:
            src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-original")
            if src:
                new_img = soup.new_tag("img", src=urljoin(base_url, src))
                if img_tag.get("alt"):
                    new_img["alt"] = img_tag["alt"]
                if img_tag.get("width"):
                    new_img["width"] = img_tag["width"]
                if img_tag.get("height"):
                    new_img["height"] = img_tag["height"]
                picture.replace_with(new_img)

    return str(body)


def _extract_wechat_rich_html(html: str, url: str) -> str:
    body_html = _extract_body_html(html, url)
    return _process_summary_html(body_html, url)


def _has_meaningful_wechat_content(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    js_content = soup.find(id="js_content")
    if js_content is None:
        return False
    return bool(js_content.get_text(strip=True) or js_content.find("img"))


def _extract_with_wechat_dom_priority(html: str, url: str) -> tuple[str, str] | None:
    if not _is_wechat_url(url) or not _has_meaningful_wechat_content(html):
        return None
    rich_html = _extract_wechat_rich_html(html, url)
    soup = BeautifulSoup(rich_html, "lxml")
    text = soup.get_text(separator="\n", strip=True)
    if not rich_html.strip() or (not text and not soup.find("img")):
        return None
    return text, rich_html


def _extract_with_trafilatura(html: str, url: str) -> tuple[str, str] | None:
    preprocessed = _preprocess_html(html, url)
    text = trafilatura.extract(
        preprocessed,
        output_format="txt",
        include_comments=False,
        include_tables=True,
        include_images=True,
        include_formatting=True,
        deduplicate=True,
    )
    if not text or len(text.strip()) < MIN_CONTENT_LENGTH:
        return None
    clean_html = trafilatura.extract(
        preprocessed,
        output_format="html",
        include_comments=False,
        include_tables=True,
        include_images=True,
        include_formatting=True,
    ) or text
    return text, clean_html


def _extract_with_readability(html: str, url: str) -> tuple[str, str, str]:
    doc = Document(html)
    title = doc.title()
    summary_html = doc.summary()
    preprocessed = _preprocess_html(summary_html, url)
    soup = BeautifulSoup(preprocessed, "lxml")
    plain_text = soup.get_text(separator="\n", strip=True)
    return title, plain_text, summary_html


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

    text_content = ""
    rich_html = ""
    wechat_dom_result = _extract_with_wechat_dom_priority(html, url) if _is_wechat_url(url) else None
    traf_result = None
    if wechat_dom_result:
        text_content, rich_html = wechat_dom_result
        logger.debug("Extracted with WeChat DOM priority: %d chars", len(text_content))
    else:
        traf_result = _extract_with_trafilatura(html, url)

    if not wechat_dom_result and traf_result:
        text_content, clean_html = traf_result
        if _is_wechat_url(url):
            wechat_body = _extract_body_html(html, url)
            wechat_traf = _extract_with_trafilatura(wechat_body, url)
            if wechat_traf and len(wechat_traf[0]) > len(text_content):
                text_content, clean_html = wechat_traf
        rich_html = _process_summary_html(clean_html, url)
        logger.debug("Extracted with trafilatura: %d chars", len(text_content))
    else:
        logger.debug("trafilatura returned insufficient content, falling back to readability")
        title_fb, text_content, summary_html = _extract_with_readability(html, url)
        title = title_fb or title
        if _is_wechat_url(url) and len(text_content) < 100:
            wechat_body = _extract_body_html(html, url)
            wechat_title, wc_text, wc_summary = _extract_with_readability(wechat_body, url)
            title = wechat_title or title
            text_content = wc_text or text_content
            summary_html = wc_summary or summary_html
        rich_html = _process_summary_html(summary_html, url)

    media_urls = _extract_media_urls(html, url)

    return FetchedContent(
        title=title,
        html_raw=html,
        text_content=text_content,
        rich_html=rich_html,
        media_urls=media_urls,
    )


def _extract_media_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls = set()

    image_scope = soup
    if _is_wechat_url(base_url):
        js_content = soup.find(id="js_content")
        if js_content:
            image_scope = BeautifulSoup(str(js_content), "lxml")

    for tag in image_scope.find_all("img"):
        src = tag.get("data-src") or tag.get("data-original") or tag.get("data-url") or tag.get("data-lazy-src") or tag.get("src")
        if src:
            full = urljoin(base_url, src.split("#")[0])
            if not full.startswith("data:"):
                urls.add(full)

    if _is_wechat_url(base_url):
        script_text = "\n".join(tag.get_text("\n", strip=False) for tag in soup.find_all("script"))
        for cdn_url in re.findall(r'cdn_url\s*[:=]\s*["\'](https://mmbiz\.qpic\.cn/[^"\']+)["\']', script_text, re.IGNORECASE):
            urls.add(cdn_url.split("#")[0])

    background_re = re.compile(r"url\(\s*['\"]?\s*(.*?)\s*['\"]?\s*\)", re.IGNORECASE)
    for tag in soup.find_all(style=True):
        match = background_re.search(tag["style"])
        if match:
            bg_url = match.group(1)
            full = urljoin(base_url, bg_url.split("#")[0])
            if not full.startswith("data:"):
                urls.add(full)

    for tag in soup.find_all("video"):
        src = tag.get("src") or tag.get("data-src")
        if src:
            urls.add(urljoin(base_url, src))
        poster = tag.get("poster")
        if poster:
            urls.add(urljoin(base_url, poster))
        for source in tag.find_all("source"):
            src = source.get("src") or source.get("data-src")
            if src:
                urls.add(urljoin(base_url, src))

    for tag in soup.find_all("audio"):
        src = tag.get("src") or tag.get("data-src")
        if src:
            urls.add(urljoin(base_url, src))
        for source in tag.find_all("source"):
            src = source.get("src") or source.get("data-src")
            if src:
                urls.add(urljoin(base_url, src))

    for tag in soup.find_all("picture"):
        for source in tag.find_all("source"):
            srcset = source.get("srcset") or source.get("data-srcset") or source.get("data-src") or source.get("src")
            if srcset:
                for candidate in srcset.split(","):
                    url_part = candidate.strip().split(" ")[0]
                    full = urljoin(base_url, url_part.split("#")[0])
                    if not full.startswith("data:"):
                        urls.add(full)
        img = tag.find("img")
        if img:
            src = img.get("data-src") or img.get("data-original") or img.get("data-lazy-src") or img.get("src")
            if src:
                full = urljoin(base_url, src.split("#")[0])
                if not full.startswith("data:"):
                    urls.add(full)

    for tag in soup.find_all("mp-common-videosnap"):
        data_src = tag.get("data-src")
        if data_src:
            urls.add(urljoin(base_url, data_src))

    for tag in soup.find_all("mpvoice"):
        fileid = tag.get("voice_encode_fileid")
        if fileid:
            urls.add(f"https://res.wx.qq.com/voice/getvoice?mediaid={fileid}")

    for tag in soup.find_all("iframe"):
        src = tag.get("data-src") or tag.get("src")
        if src:
            urls.add(urljoin(base_url, src))

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if re.search(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z)$", href, re.IGNORECASE):
            urls.add(urljoin(base_url, href))

    return list(urls)
