import json
import logging

import httpx
from slugify import slugify
from sqlalchemy import select

from app.models.system_config import SystemConfig
from app.services.publisher.conflict_resolution import build_retry_title
from app.services.publisher.payloads import build_halo_payload

logger = logging.getLogger(__name__)
HALO_CONTENT_API_VERSION = "content.halo.run/v1alpha1"


class HaloClient:
    def _build_payload(
        self,
        title: str,
        content_html: str,
        publish_time=None,
        slug_suffix: str | None = None,
        tags: list[dict] | None = None,
        publish: bool | None = None,
    ) -> dict:
        return build_halo_payload(
            title,
            content_html,
            publish_time,
            slug_suffix=slug_suffix,
            tags=tags,
            publish=publish,
        )

    async def _load_config(self, db_session) -> dict | None:
        result = await db_session.execute(
            select(SystemConfig).where(SystemConfig.key == "halo")
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return json.loads(row.value)

    async def _ensure_tags_exist(self, client, site_url: str, api_token: str, tags: list) -> list[str]:
        tag_slugs = []
        all_existing = {}

        list_resp = await client.get(
            f"{site_url}/apis/{HALO_CONTENT_API_VERSION}/tags",
            headers={"Authorization": f"Bearer {api_token}"},
        )
        if list_resp.is_success:
            for item in list_resp.json().get("items", []):
                spec = item.get("spec", {})
                meta = item.get("metadata", {})
                display = spec.get("displayName", "")
                name_meta = meta.get("name", "")
                if display:
                    all_existing[display] = name_meta
                if name_meta:
                    all_existing[name_meta] = name_meta

        for tag_info in tags:
            if isinstance(tag_info, dict):
                name = tag_info.get("name", str(tag_info))
            else:
                name = str(tag_info)
            slug = slugify(name)

            if name in all_existing:
                tag_slugs.append(all_existing[name])
                logger.info(f"Halo tag already exists: {name} -> {all_existing[name]}")
                continue
            if slug in all_existing:
                tag_slugs.append(all_existing[slug])
                logger.info(f"Halo tag already exists (by slug): {slug}")
                continue

            color = tag_info.get("color", "blue") if isinstance(tag_info, dict) else "blue"
            color_map = {
                "blue": "#3B82F6", "indigo": "#6366F1", "teal": "#14B8A6",
                "emerald": "#10B981", "amber": "#F59E0B", "rose": "#F43F5E",
            }
            halo_color = color_map.get(color, "#3B82F6")

            tag_payload = {
                "tag": {
                    "spec": {
                        "displayName": name,
                        "slug": slug,
                        "color": halo_color,
                        "cover": "",
                    },
                    "apiVersion": HALO_CONTENT_API_VERSION,
                    "kind": "Tag",
                    "metadata": {"name": slug},
                }
            }
            create_resp = await client.post(
                f"{site_url}/apis/{HALO_CONTENT_API_VERSION}/tags",
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                },
                json=tag_payload,
            )
            if create_resp.is_success:
                tag_slugs.append(slug)
                logger.info(f"Created Halo tag: {name} (slug: {slug})")
            else:
                logger.warning(f"Failed to create tag '{name}': HTTP {create_resp.status_code} {create_resp.text}")

        return tag_slugs

    async def test_connection(self, db_session) -> tuple[bool, str]:
        config = await self._load_config(db_session)
        if not config:
            return False, "Halo 配置未设置"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{config['site_url'].rstrip('/')}/actuator/health",
                    headers={"Authorization": f"Bearer {config['api_token']}"},
                )
                if resp.status_code == 200:
                    return True, "Halo 连接成功"
                return False, f"Halo 响应异常: HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Halo 连接失败: {str(e)}"

    async def publish(
        self,
        db_session,
        title: str,
        content_html: str,
        publish_time=None,
        tags: list[dict] | None = None,
    ) -> str:
        config = await self._load_config(db_session)
        site_url = config["site_url"].rstrip("/")
        api_token = config["api_token"]

        base_title = title
        current_title = title

        async with httpx.AsyncClient(timeout=30) as client:
            tag_slugs = tags
            if tags:
                tag_slugs = await self._ensure_tags_exist(client, site_url, api_token, tags)

            for attempt in range(0, 6):
                slug_suffix = None if attempt == 0 else f"retry-{attempt}"
                payload = self._build_payload(
                    current_title,
                    content_html,
                    publish_time,
                    slug_suffix=slug_suffix,
                    tags=tag_slugs,
                    publish=True if publish_time is None else None,
                )
                slug = payload["post"]["metadata"]["name"]

                resp = await client.post(
                    f"{site_url}/apis/api.console.halo.run/v1alpha1/posts",
                    headers={
                        "Authorization": f"Bearer {api_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.is_success:
                    data = resp.json()
                    post_name = data.get("metadata", {}).get("name", slug)
                    return post_name
                if "名称重复" in resp.text or "重复的名称" in resp.text:
                    if attempt == 5:
                        break
                    current_title = build_retry_title(base_title, attempt + 1)
                    continue
                raise Exception(f"Halo 发布失败 (HTTP {resp.status_code}): {resp.text}")

        raise Exception("Halo 名称重复，自动重试 5 次后仍失败")


halo_client = HaloClient()
