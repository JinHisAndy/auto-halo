from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def page_task_create(request: Request):
    return templates.TemplateResponse("task_create.html", {"request": request})


@router.get("/tasks", response_class=HTMLResponse)
async def page_task_list(request: Request):
    return templates.TemplateResponse("task_list.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/open-api/docs", response_class=HTMLResponse)
async def page_open_api_docs(request: Request):
    return templates.TemplateResponse("open_api_docs.html", {"request": request})
