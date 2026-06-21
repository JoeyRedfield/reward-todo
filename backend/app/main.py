from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.public import router as public_router
from app.api.task_reward import router as task_reward_router
from app.config import get_settings
from app.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(public_router)
    app.include_router(task_reward_router)

    return app


app = create_app()
