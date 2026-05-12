HTML_REWRITE_PROMPT = """
你是一位资深博客作者。请重写下面的 HTML 文章内容。
要求：
- preserve overall structure of the HTML document
- preserve image/audio/video placeholders or tags exactly as they appear
- rewrite textual nodes only
- 保持原文核心信息和观点不变
- 使用轻松自然的博客口吻表达
- 不得直接复制粘贴原文句子
{extra}

原文内容（HTML）：
{content}
"""

TEXT_REWRITE_PROMPT = """
你是一位资深博客作者。请将以下文章内容用你自己的话重写一遍。
要求：
- 保持原文的核心信息和观点不变
- 用博客的轻松自然口吻表达
- 不得直接复制粘贴原文的句子
- 可以调整文章结构和段落顺序
{extra}

原文内容：
{content}
"""

CITATION_EXTRA = "保留以下原文引用内容（blockquote中的内容需要保留原样）：\n"


def infer_content_format(content: str) -> str:
    stripped = (content or "").strip()
    if stripped.startswith("<") and ">" in stripped:
        return "html"
    return "text"


def build_rewrite_prompt(content: str, keep_citations: bool = False, content_format: str | None = None) -> str:
    extra = CITATION_EXTRA if keep_citations else ""
    actual_format = content_format or infer_content_format(content)
    template = HTML_REWRITE_PROMPT if actual_format == "html" else TEXT_REWRITE_PROMPT
    return template.format(extra=extra, content=content)
