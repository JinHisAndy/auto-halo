HTML_REWRITE_PROMPT = """
作为一个常年写技术博客的人，请帮我重写下面这篇 HTML 格式的技术文章，面向开发者和工程师读者。

基本要求：
- 保留 HTML 文档的整体结构，不要大改 DOM 层级的布局
- 只对文字节点做适当润色重写，不要改变原文的核心信息、事实、结论和观点
- 内容可以更充实，适当补充必要的技术背景、工程细节和个人经验视角，但不能凭空编造
- 技术表达的准确性放在第一位，语言风格要像真实的技术博主——自信但不浮夸，有干货有态度
- 不要直接复制粘贴原文的句子，必须用自己的话重新表达

必须保留的标签和结构：
- img、video、audio、source、a、pre、code、table、ul、ol、blockquote
- 不要删除任何媒体标签（图片、视频、音频等），这是硬性要求
- pre 和 code 中的代码块必须原样保留为代码块，绝对不要改写成普通文字
- 保留超链接、列表、表格、引用块等结构

输出格式（必须严格遵守）：
  TITLE: <重写后的标题>
  BODY:
  <重写后的正文>
{extra}

原文内容（HTML）：
{content}
"""

TEXT_REWRITE_PROMPT = """
作为一个常年写技术博客的人，请帮我把下面的文章用你自己的话重新写一遍。

要求：
- 保持原文的核心信息、事实和观点不变
- 用真实技术博主的口吻来写——自信、有干货、不啰嗦，像在跟同行交流
- 可以适当调整文章结构和段落顺序，让阅读节奏更舒服
- 可以补充必要的技术上下文，但不能凭空编造内容
- 绝对不要直接复制粘贴原文的句子

输出格式（必须严格遵守）：
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
