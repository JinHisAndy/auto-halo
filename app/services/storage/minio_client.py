import io
import json
from pathlib import Path

from minio import Minio

from app.models.system_config import SystemConfig


class MinioStorage:
    def _get_client(self, config: dict) -> Minio:
        return Minio(
            endpoint=config["endpoint"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            secure=config.get("secure", False),
        )

    async def _load_config(self, db_session) -> dict | None:
        from sqlalchemy import select

        result = await db_session.execute(
            select(SystemConfig).where(SystemConfig.key == "minio")
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return json.loads(row.value)

    async def test_connection(self, db_session) -> tuple[bool, str]:
        config = await self._load_config(db_session)
        if not config:
            return False, "MinIO 配置未设置"
        try:
            client = self._get_client(config)
            client.list_buckets()
            return True, "MinIO 连接成功"
        except Exception as e:
            return False, f"MinIO 连接失败: {str(e)}"

    async def save_original(
        self, db_session, article_title: str, html_raw: str, parsed_article
    ) -> str:
        config = await self._load_config(db_session)
        client = self._get_client(config)
        bucket = config["bucket"]

        folder = f"{article_title}/"

        client.put_object(
            bucket,
            f"{folder}original.html",
            io.BytesIO(html_raw.encode("utf-8")),
            len(html_raw.encode("utf-8")),
            content_type="text/html",
        )

        for item in parsed_article.media_items:
            if item.local_path:
                local = Path(item.local_path)
                if local.exists():
                    client.fput_object(
                        bucket,
                        f"{folder}media/{item.filename}",
                        str(local),
                    )

        for item in parsed_article.attachment_items:
            if item.local_path:
                local = Path(item.local_path)
                if local.exists():
                    client.fput_object(
                        bucket,
                        f"{folder}attachments/{item.filename}",
                        str(local),
                    )

        return folder

    async def save_rewritten(self, db_session, article_title: str, markdown_content: str) -> str:
        config = await self._load_config(db_session)
        client = self._get_client(config)
        bucket = config["bucket"]

        folder = f"{article_title}/"
        path = f"{folder}rewritten.md"
        data = markdown_content.encode("utf-8")
        client.put_object(
            bucket,
            path,
            io.BytesIO(data),
            len(data),
            content_type="text/markdown",
        )
        return path


minio_storage = MinioStorage()