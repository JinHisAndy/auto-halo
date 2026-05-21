import io
import json
import os
import shutil
from pathlib import Path

from minio import Minio

from app.models.system_config import SystemConfig

LOCAL_HISTORY_DIR = os.path.join(os.getcwd(), "history")


class MinioStorage:
    def _clean_endpoint(self, endpoint: str) -> str:
        endpoint = endpoint.strip()
        if "://" in endpoint:
            endpoint = endpoint.split("://", 1)[1]
        if "/" in endpoint:
            endpoint = endpoint.split("/", 1)[0]
        return endpoint

    def _get_client(self, config: dict) -> Minio:
        endpoint = self._clean_endpoint(config["endpoint"])
        secure = config.get("secure", False)
        raw = config["endpoint"].strip()
        if raw.startswith("https://"):
            secure = True
        elif raw.startswith("http://"):
            secure = False
        return Minio(
            endpoint=endpoint,
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            secure=secure,
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
    ) -> tuple[str, dict[str, str]]:
        config = await self._load_config(db_session)
        folder = f"{article_title}/"
        url_mapping: dict[str, str] = {}

        if config is None:
            local_folder = os.path.join(LOCAL_HISTORY_DIR, article_title)
            os.makedirs(os.path.join(local_folder, "media"), exist_ok=True)
            os.makedirs(os.path.join(local_folder, "attachments"), exist_ok=True)

            with open(os.path.join(local_folder, "original.html"), "w", encoding="utf-8") as f:
                f.write(html_raw)

            for item in parsed_article.media_items:
                if item.local_path and os.path.exists(item.local_path):
                    dest = os.path.join(local_folder, "media", item.filename)
                    shutil.copy2(item.local_path, dest)
                    url_mapping[item.url] = item.url

            for item in parsed_article.attachment_items:
                if item.local_path and os.path.exists(item.local_path):
                    dest = os.path.join(local_folder, "attachments", item.filename)
                    shutil.copy2(item.local_path, dest)
                    url_mapping[item.url] = item.url

            return folder, url_mapping

        client = self._get_client(config)
        bucket = config["bucket"]

        client.put_object(
            bucket,
            f"{folder}original.html",
            io.BytesIO(html_raw.encode("utf-8")),
            len(html_raw.encode("utf-8")),
            content_type="text/html",
        )

        secure = config.get("secure", False)
        raw_endpoint = config["endpoint"].strip()
        if raw_endpoint.startswith("https://"):
            secure = True
        elif raw_endpoint.startswith("http://"):
            secure = False
        scheme = "https" if secure else "http"
        endpoint = self._clean_endpoint(config["endpoint"])

        def _build_minio_url(object_path: str) -> str:
            return f"{scheme}://{endpoint}/{bucket}/{object_path}"

        for item in parsed_article.media_items:
            if item.local_path:
                local = Path(item.local_path)
                if local.exists():
                    object_path = f"{folder}media/{item.filename}"
                    client.fput_object(
                        bucket,
                        object_path,
                        str(local),
                    )
                    url_mapping[item.url] = _build_minio_url(object_path)

        for item in parsed_article.attachment_items:
            if item.local_path:
                local = Path(item.local_path)
                if local.exists():
                    object_path = f"{folder}attachments/{item.filename}"
                    client.fput_object(
                        bucket,
                        object_path,
                        str(local),
                    )
                    url_mapping[item.url] = _build_minio_url(object_path)

        return folder, url_mapping

    async def save_rewritten(self, db_session, article_title: str, markdown_content: str) -> str:
        config = await self._load_config(db_session)
        folder = f"{article_title}/"

        if config is None:
            local_folder = os.path.join(LOCAL_HISTORY_DIR, article_title)
            os.makedirs(local_folder, exist_ok=True)
            path = os.path.join(local_folder, "rewritten.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            return os.path.join(folder, "rewritten.md")

        client = self._get_client(config)
        bucket = config["bucket"]

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