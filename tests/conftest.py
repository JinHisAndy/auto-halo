import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault(
    "app.config",
    types.SimpleNamespace(
        settings=types.SimpleNamespace(
            database_url="sqlite+aiosqlite:///:memory:",
            secret_key="test-secret-key",
        )
    ),
)


async def _ensure_logged_in(client):
    from app.db import init_db
    await init_db()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


def login_client():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=True)
    asyncio.run(_ensure_logged_in(client))
    return client