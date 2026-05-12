from slugify import slugify


def build_halo_payload(title: str, content_html: str, publish_time=None) -> dict:
    slug = slugify(title, max_length=80)
    publish = publish_time is None
    return {
        "post": {
            "spec": {
                "title": title,
                "slug": slug,
                "template": "",
                "cover": "",
                "deleted": False,
                "publish": publish,
                "pinned": False,
                "allowComment": True,
                "visible": "PUBLIC",
                "priority": 0,
                "excerpt": {"autoGenerate": True, "raw": ""},
                "categories": [],
                "tags": [],
                "htmlMetas": []
            },
            "apiVersion": "content.halo.run/v1alpha1",
            "kind": "Post",
            "metadata": {"name": slug},
        },
        "content": {
            "raw": content_html,
            "content": content_html,
            "rawType": "HTML"
        },
    }
