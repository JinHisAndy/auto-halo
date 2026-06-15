import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.models.user import _load_users, _save_users, require_admin, get_current_user

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


def _sanitize_user(user: dict) -> dict:
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/api/auth/login")
async def login(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的请求体")

    username = (body.get("username") or "").strip()
    password = (body.get("password") or "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    users = await _load_users()
    for u in users:
        if u["username"] == username and u["password"] == password:
            request.session["user_id"] = u["id"]
            request.session["username"] = u["username"]
            request.session["role"] = u["role"]
            return {"ok": True, "role": u["role"]}

    raise HTTPException(status_code=401, detail="用户名或密码错误")


@router.post("/api/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/api/auth/me")
async def me(request: Request):
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    return user


@router.get("/api/users")
async def list_users(request: Request):
    require_admin(request)
    users = await _load_users()
    return [_sanitize_user(u) for u in users]


@router.post("/api/users")
async def create_user(request: Request):
    require_admin(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的请求体")

    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少2个字符")

    users = await _load_users()
    if any(u["username"] == username for u in users):
        raise HTTPException(status_code=409, detail="用户名已存在")

    new_user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "password": password,
        "role": "user",
    }
    users.append(new_user)
    await _save_users(users)
    return _sanitize_user(new_user)


@router.put("/api/users/{user_id}")
async def update_user(request: Request, user_id: str):
    require_admin(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的请求体")

    users = await _load_users()
    for u in users:
        if u["id"] == user_id:
            if "password" in body and body["password"]:
                u["password"] = body["password"].strip()
            await _save_users(users)
            return _sanitize_user(u)

    raise HTTPException(status_code=404, detail="用户不存在")


@router.delete("/api/users/{user_id}")
async def delete_user(request: Request, user_id: str):
    require_admin(request)
    if user_id == request.session.get("user_id"):
        raise HTTPException(status_code=400, detail="不能删除自己")

    users = await _load_users()
    admins = [u for u in users if u["role"] == "admin"]
    target = next((u for u in users if u["id"] == user_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target["role"] == "admin" and len(admins) <= 1:
        raise HTTPException(status_code=400, detail="不能删除最后一个管理员")

    users = [u for u in users if u["id"] != user_id]
    await _save_users(users)
    return {"ok": True}