from dataclasses import dataclass, field


@dataclass
class FetchedContent:
    title: str
    html_raw: str
    text_content: str
    media_urls: list[str] = field(default_factory=list)