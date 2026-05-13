def build_retry_title(title: str, attempt: int) -> str:
    if attempt == 1:
        return f"{title}（重发版）"
    return f"{title}（重发{attempt}）"
