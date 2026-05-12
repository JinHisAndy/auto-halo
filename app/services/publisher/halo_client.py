import json
import re

import httpx
from slugify import slugify

from app.models.system_config import SystemConfig
from sqlalchemy import select


class HaloClient:
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
        self, db_session, title: str, content_md: str, publish_time=None
    ) -> int:
        config = await self._load_config(db_session)
        site_url = config["site_url"].rstrip("/")
        api_token = config["api_token"]

        slug = slugify(title, max_length=80)
        publish = publish_time is None

        payload = {
            "post": {
                "spec": {
                    "title": title,
                    "slug": slug,
                    "publish": publish,
                    "publishTime": publish_time.isoformat() if publish_time else None,
                },
                "apiVersion": "content.halo.run/v1alpha1",
                "kind": "Post",
                "metadata": {"name": slug},
            },
            "content": {
                "raw": content_md,
                "content": content_md,
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{site_url}/apis/api.console.halo.run/v1alpha1/posts",
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["metadata"].get("name", slug)


halo_client = HaloClient()