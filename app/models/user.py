import uuid
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy import select

from app.db import async_session
from app.models.system_config import SystemConfig

CONFIG_KEY = "users"

DEFAULT_ADMIN = {
    "id": str(uuid.uuid4()),
    "username": "admin",
    "password": "admin123",
    "role": "admin",
}


async def _load_users() -> list[dict]:
    async with async_session() as db:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == CONFIG_KEY)
        )
        row = result.scalar_one_or_none()
        if row is None:
            import json
            users = [DEFAULT_ADMIN]
            db.add(SystemConfig(key=CONFIG_KEY, value=json.dumps(users, ensure_ascii=False)))
            await db.commit()
            return users
        import json
        return json.loads(row.value)


async def _save_users(users: list[dict]):
    import json
    async with async_session() as db:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == CONFIG_KEY)
        )
        row = result.scalar_one_or_none()
        if row is None:
            db.add(SystemConfig(key=CONFIG_KEY, value=json.dumps(users, ensure_ascii=False)))
        else:
            row.value = json.dumps(users, ensure_ascii=False)
        await db.commit()


def get_current_user(request: Request) -> Optional[dict]:
    session = request.session
    user_id = session.get("user_id")
    role = session.get("role")
    username = session.get("username")
    if not user_id or not role:
        return None
    return {"id": user_id, "username": username, "role": role}


def require_user(request: Request):
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def require_admin(request: Request):
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user