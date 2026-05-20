from slugify import slugify


def _build_slug(title: str, slug_suffix: str | None = None, max_length: int = 80) -> str:
    base_slug = slugify(title)
    if not slug_suffix:
        return slugify(title, max_length=max_length)

    normalized_suffix = slugify(slug_suffix)
    suffix = f"-{normalized_suffix}"
    trimmed_base = base_slug[: max_length - len(suffix)].rstrip("-")
    return f"{trimmed_base}{suffix}"


def build_halo_payload(
    title: str,
    content_html: str,
    publish_time=None,
    slug_suffix: str | None = None,
    tags: list | None = None,
    publish: bool | None = None,
    cover: str = "",
) -> dict:
    slug = _build_slug(title, slug_suffix=slug_suffix)
    should_publish = publish_time is None if publish is None else publish

    payload = {
        "post": {
            "spec": {
                "title": title,
                "slug": slug,
                "template": "",
                "cover": cover,
                "deleted": False,
                "publish": should_publish,
                "pinned": False,
                "allowComment": True,
                "visible": "PUBLIC",
                "priority": 0,
                "excerpt": {"autoGenerate": True, "raw": ""},
                "categories": [],
                "tags": [],
                "htmlMetas": [],
            },
            "apiVersion": "content.halo.run/v1alpha1",
            "kind": "Post",
            "metadata": {"name": slug},
        },
        "content": {
            "raw": content_html,
            "content": content_html,
            "rawType": "HTML",
        },
    }

    if tags:
        first = tags[0] if tags else None
        if isinstance(first, dict):
            payload["post"]["spec"]["tags"] = [tag["name"] for tag in tags]
        else:
            payload["post"]["spec"]["tags"] = list(tags)
    return payload
