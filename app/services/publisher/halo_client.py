import json

import httpx
from sqlalchemy import select

from app.models.system_config import SystemConfig
from app.services.publisher.conflict_resolution import build_retry_title
from app.services.publisher.payloads import build_halo_payload


class HaloClient:
    def _build_payload(
        self,
        title: str,
        content_html: str,
        publish_time=None,
        slug_suffix: str | None = None,
        tags: list[dict] | None = None,
    ) -> dict:
        return build_halo_payload(
            title,
            content_html,
            publish_time,
            slug_suffix=slug_suffix,
            tags=tags,
        )

    async def _load_config(self, db_session) -> dict | None:
        result = await db_session.execute(
            select(SystemConfig).where(SystemConfig.key == "halo")
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return json.loads(row.value)

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
            for attempt in range(0, 6):
                slug_suffix = None if attempt == 0 else f"retry-{attempt}"
                payload = self._build_payload(
                    current_title,
                    content_html,
                    publish_time,
                    slug_suffix=slug_suffix,
                    tags=tags,
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
                    return data.get("metadata", {}).get("name", slug)
                if "名称重复" in resp.text or "重复的名称" in resp.text:
                    if attempt == 5:
                        break
                    current_title = build_retry_title(base_title, attempt + 1)
                    continue
                raise Exception(f"Halo 发布失败 (HTTP {resp.status_code}): {resp.text}")

        raise Exception("Halo 名称重复，自动重试 5 次后仍失败")


halo_client = HaloClient()
