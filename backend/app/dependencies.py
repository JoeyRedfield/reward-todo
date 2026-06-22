from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import User
from app.services.auth_service import AuthService
from app.services.task_reward_service import TaskRewardService


def get_db_session():
    yield from get_db()


def get_task_reward_service(session: Session = Depends(get_db_session)) -> TaskRewardService:
    return TaskRewardService(session)


def get_auth_service(session: Session = Depends(get_db_session)) -> AuthService:
    return AuthService(session)


def get_bootstrap_user(
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> User:
    username = settings.auth_initial_username
    if not username:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bootstrap user is not configured",
        )

    normalized_username = username.strip().lower()
    candidate = service.session.scalar(select(User).where(User.username == normalized_username))
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bootstrap user not found",
        )
    return candidate


def require_authenticated_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    service: AuthService = Depends(get_auth_service),
) -> tuple[User, str]:
    session_token = get_optional_session_token(request, settings)
    if session_token is not None:
        authenticated = service.authenticate_session(session_token)
        if authenticated is not None:
            user, _ = authenticated
            return user, session_token

    bearer_token = get_optional_bearer_token(request)
    if bearer_token is not None:
        authenticated_token = service.authenticate_access_token(
            bearer_token,
            accepted_token_types={"api", "mcp"},
        )
        if authenticated_token is not None:
            user, _ = authenticated_token
            return user, bearer_token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def get_optional_session_token(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Optional[str]:
    return request.cookies.get(settings.auth_session_cookie_name)


def get_optional_bearer_token(request: Request) -> Optional[str]:
    authorization = request.headers.get("Authorization")
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def require_mcp_access_token(
    request: Request,
    settings: Settings = Depends(get_settings),
    service: AuthService = Depends(get_auth_service),
) -> tuple[User, str]:
    if not settings.auth_enable_mcp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mcp server is not enabled",
        )

    bearer_token = get_optional_bearer_token(request)
    if bearer_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    authenticated = service.authenticate_access_token(
        bearer_token,
        accepted_token_types={"mcp"},
    )
    if authenticated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user, _ = authenticated
    return user, bearer_token


def require_readonly_token(
    authorization: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    if token != settings.readonly_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    return token
