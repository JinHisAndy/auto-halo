from bs4 import BeautifulSoup


def _looks_like_html(content: str) -> bool:
    stripped = (content or "").strip()
    return stripped.startswith("<") and ">" in stripped


def _has_tag(content: str, tag_name: str) -> bool:
    soup = BeautifulSoup(content or "", "lxml")
    return soup.find(tag_name) is not None


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
        if _has_tag(original_html, tag_name) and not _has_tag(rewritten_html, tag_name):
            return False, message

    return True, "OK"
