import random
import re

from bs4 import BeautifulSoup

ALLOWED_TAG_COLORS = ["blue", "indigo", "teal", "emerald", "amber", "rose"]

GENERIC_STOP_WORDS = {
    "rewritten",
    "guide",
    "article",
    "blog",
    "post",
    "tutorial",
    "introduction",
    "overview",
    "deep",
    "tuning",
    "best",
    "practices",
    "文章",
    "博客",
    "经验分享",
    "分享",
    "教程",
    "指南",
}

TECHNICAL_ENGLISH_TOKENS = {
    "api", "aws", "azure", "cache", "cdn", "ci", "cicd", "cli", "cloud", "cpu", "css",
    "devops", "docker", "fastapi", "flask", "git", "github", "gitlab", "go", "grafana",
    "grpc", "halo", "html", "http", "https", "java", "javascript", "jenkins", "jwt",
    "k8s", "kafka", "kubernetes", "linux", "llm", "mysql", "nginx", "node", "nodejs",
    "oauth", "postgres", "postgresql", "prometheus", "python", "rabbitmq", "react", "redis",
    "rest", "rust", "sdk", "ssh", "sql", "sqlite", "sqlalchemy", "tcp", "tls", "typescript",
    "udp", "vue", "websocket",
}

TECHNICAL_CHINESE_TOKENS = {
    "云原生", "容器", "编排", "运维", "后端", "前端", "数据库", "缓存", "集群", "部署", "监控",
    "日志", "自动化", "测试", "微服务", "接口", "协议", "脚本", "安全", "网络安全", "性能优化",
    "并发", "架构", "网关", "代理", "爬虫",
}


def _normalize_tag_key(value: str) -> str:
    return value.lower() if value.isascii() else value


def _extract_candidate_names(title: str, html_body: str) -> list[str]:
    text = BeautifulSoup(html_body or "", "html.parser").get_text(" ", strip=True)
    source = f"{title or ''} {text}".strip()
    if not source:
        return []

    pattern = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]{1,}|[\u4e00-\u9fff]{2,8}")
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for index, match in enumerate(pattern.finditer(source)):
        token = match.group(0).strip("._-")
        if len(token) < 2:
            continue

        lowered = token.lower()
        if lowered in GENERIC_STOP_WORDS or token in GENERIC_STOP_WORDS:
            continue

        score = 0
        if lowered in TECHNICAL_ENGLISH_TOKENS:
            score += 5
        if token in TECHNICAL_CHINESE_TOKENS:
            score += 5
        if token[:1].isupper() and token[1:].isalnum():
            score += 2
        if token.isupper():
            score += 2
        if match.start() < len(title or ""):
            score += 2

        if score <= 0:
            continue

        key = _normalize_tag_key(token)
        if key in seen:
            continue
        seen.add(key)
        scored.append((score, index, token))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [token for _, _, token in scored[:6]]


def generate_tags_from_rewritten_content(title: str, html_body: str) -> list[dict]:
    return build_tag_records(_extract_candidate_names(title, html_body))


def build_tag_records(names: list[str]) -> list[dict]:
    cleaned = []
    for name in names:
        value = (name or "").strip()
        if value and value not in cleaned:
            cleaned.append(value)
    cleaned = cleaned[:6]
    if len(cleaned) < 3:
        cleaned = (cleaned + ["技术", "开发", "实践"])[:3]
    return [{"name": name, "color": random.choice(ALLOWED_TAG_COLORS)} for name in cleaned]
