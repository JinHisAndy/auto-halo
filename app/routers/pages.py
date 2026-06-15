from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.models.user import get_current_user, require_admin

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(tags=["pages"])


def _redirect_if_not_logged_in(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return None


@router.get("/", response_class=HTMLResponse)
async def page_task_create(request: Request):
    if redirect := _redirect_if_not_logged_in(request):
        return redirect
    return templates.TemplateResponse("task_create.html", {"request": request})


@router.get("/tasks", response_class=HTMLResponse)
async def page_task_list(request: Request):
    if redirect := _redirect_if_not_logged_in(request):
        return redirect
    return templates.TemplateResponse("task_list.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    if redirect := _redirect_if_not_logged_in(request):
        return redirect
    require_admin(request)
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/open-api/docs", response_class=HTMLResponse)
async def page_open_api_docs(request: Request):
    if redirect := _redirect_if_not_logged_in(request):
        return redirect
    return templates.TemplateResponse("open_api_docs.html", {"request": request})
