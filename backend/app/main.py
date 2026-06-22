from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.account import router as account_router
from app.api.auth import router as auth_router
from app.api.mcp import router as mcp_router
from app.api.public import router as public_router
from app.api.task_reward import router as task_reward_router
from app.config import get_settings
from app.database import get_session_factory, init_db
from app.services.auth_service import AuthService


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    session = get_session_factory()()
    try:
        settings = get_settings()
        AuthService(session).ensure_initial_user(
            settings.auth_initial_username,
            settings.auth_initial_password,
        )
    finally:
        session.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(account_router)
    app.include_router(mcp_router)
    app.include_router(public_router)
    app.include_router(task_reward_router)

    return app


app = create_app()
