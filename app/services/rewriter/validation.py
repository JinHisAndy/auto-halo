from bs4 import BeautifulSoup


def _looks_like_html(content: str) -> bool:
    stripped = (content or "").strip()
    if not stripped:
        return False

    soup = BeautifulSoup(stripped, "html.parser")
    return soup.find() is not None


def _has_tag(content: str, tag_name: str) -> bool:
    soup = BeautifulSoup(content or "", "lxml")
    return soup.find(tag_name) is not None


def _count_tag(content: str, tag_name: str) -> int:
    soup = BeautifulSoup(content or "", "lxml")
    return len(soup.find_all(tag_name))


def validate_rewritten_html(original_html: str, rewritten_html: str) -> tuple[bool, str]:
    if not _looks_like_html(rewritten_html):
        return False, "Rewritten body must be HTML."

    checks = (
        ("img", "Image content must be preserved."),
        ("pre", "Code block content must be preserved."),
        ("video", "Video content must be preserved."),
        ("audio", "Audio content must be preserved."),
    )

    for tag_name, message in checks:
        original_count = _count_tag(original_html, tag_name)
        rewritten_count = _count_tag(rewritten_html, tag_name)

        if original_count and rewritten_count == 0:
            return False, message

        if original_count > 1 and rewritten_count < (original_count / 2):
            return False, message

    return True, "OK"
