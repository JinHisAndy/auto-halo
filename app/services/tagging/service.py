import random

ALLOWED_TAG_COLORS = ["blue", "indigo", "teal", "emerald", "amber", "rose"]


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
