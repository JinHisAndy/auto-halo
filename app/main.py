import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import init_db
from app.routers import tasks, config, pages, ws, open_api, auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield
    from app.services.scheduler import scheduler_service
    scheduler_service.shutdown()
    logger.info("Scheduler shut down")


app = FastAPI(title="Auto-Halo", version="0.1.0", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(config.router)
app.include_router(open_api.router)
app.include_router(pages.router)
app.add_websocket_route("/ws/tasks", ws.websocket_endpoint)

try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception:
    pass
