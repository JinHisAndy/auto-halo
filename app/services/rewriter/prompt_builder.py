import re

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
{extra}
输出格式（必须严格遵守）：
  TITLE: <重写后的标题>
  BODY:
  <重写后的正文>

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
{extra}
输出格式（必须严格遵守）：
  TITLE: <重写后的标题>
  BODY:
  <重写后的正文>

原文内容：
{content}
"""

CITATION_KEEP_PROMPT = """

引用处理：
- 请在文章末尾添加"参考链接"小节，列出以下原文来源URL：
{url_list}
"""

CITATION_BLOCK_PROMPT = """

重要约束——禁止原文痕迹：
- 重写后的内容中禁止出现任何原文的URL链接地址
- 禁止出现原文来源（如"根据XX报道""转自XX""来源：XX"等文字描述）
- 禁止复制原文中指向特定网站或域名的外链
- 文章读起来应该像你原创的技术博客，而不是转载或引用的内容
"""


def _format_url_list(urls: list[str]) -> str:
    return "\n".join(f"- {url}" for url in urls)


def infer_content_format(content: str) -> str:
    stripped = (content or "").strip()
    if not stripped:
        return "text"

    html_indicators = (
        "<article",
        "<section",
        "<div",
        "<p",
        "<img",
        "<h1",
        "<h2",
        "<h3",
        "<ul",
        "<ol",
        "<table",
        "<pre",
        "<code",
        "<blockquote",
        "<video",
        "<audio",
    )

    lowered = stripped.lower()
    if stripped.startswith("<") and ">" in stripped:
        return "html"
    if any(indicator in lowered for indicator in html_indicators):
        return "html"
    return "text"


def build_rewrite_prompt(content: str, keep_citations: bool = False, content_format: str | None = None, urls: list[str] | None = None) -> str:
    if keep_citations and urls:
        extra = CITATION_KEEP_PROMPT.format(url_list=_format_url_list(urls))
    elif not keep_citations:
        extra = CITATION_BLOCK_PROMPT
    else:
        extra = ""

    actual_format = content_format or infer_content_format(content)
    template = HTML_REWRITE_PROMPT if actual_format == "html" else TEXT_REWRITE_PROMPT
    return template.format(extra=extra, content=content)


def extract_title_and_body(output: str, fallback_title: str) -> tuple[str, str]:
    if "TITLE:" not in output or "BODY:" not in output:
        return fallback_title, output.strip()

    title_part, body_part = output.split("BODY:", 1)
    title = title_part.replace("TITLE:", "", 1).strip() or fallback_title
    title = title.split("\n")[0][:200].strip()
    title = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", title).strip("_")
    return title, body_part.strip()


TAG_SUGGESTION_PROMPT = """
你是一位博客标签专家。请根据文章内容，从给定标签列表中选出最贴切的标签，并补充必要的新标签。

要求：
- 优先复用已有标签中与文章内容真正相关的标签
- 不要为了凑数而选择不相关的标签
- 如果已有标签不够贴切，生成具有实际含义的新标签
- 标签要从博客读者的角度出发，便于读者快速索引和检索文章
- 标签要简洁、有实际含义（例如"Kubernetes"而不是"技术"）
- 数量控制在 3~6 个
- 只输出标签名，一行一个，不要加序号或解释

已有标签列表：
{existing_tags}

文章标题：{title}
文章正文摘要：
{body_text}

请输出选中的标签（每行一个）：
"""
