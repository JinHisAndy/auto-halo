HTML_REWRITE_PROMPT = """
你是一位 experienced technical blogger，面向技术读者、开发者和工程师写作。请重写下面的 HTML 文章内容。
要求：
- preserve overall structure of the HTML document
- rewrite textual nodes only when appropriate, while keeping technical meaning accurate
- 内容可以更丰富、更完整（more complete），可以补充必要的技术上下文、解释和工程细节，但不得编造事实，不得改变原文核心信息、结论和观点
- 保持技术表达准确，适合技术读者阅读
- preserve these tags and their intent: img, video, audio, source, a, pre, code, table, ul, ol, blockquote
- do not remove media tags，不要删除媒体标签
- do not rewrite code blocks into prose，代码块和 pre/code 中的代码内容应保留为代码块，不要改写成普通文字
- 保留链接、列表、表格、引用、媒体及代码相关结构
- 使用自然、清晰、专业的技术博客口吻表达
- 不得直接复制粘贴原文句子
- 输出必须严格遵循以下格式：
  TITLE: <重写后的标题>
  BODY:
  <重写后的正文>
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
- 输出必须严格遵循以下格式：
  TITLE: <重写后的标题>
  BODY:
  <重写后的正文>
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


def extract_title_and_body(output: str, fallback_title: str) -> tuple[str, str]:
    if "TITLE:" not in output or "BODY:" not in output:
        return fallback_title, output.strip()

    title_part, body_part = output.split("BODY:", 1)
    title = title_part.replace("TITLE:", "", 1).strip() or fallback_title
    return title, body_part.strip()
