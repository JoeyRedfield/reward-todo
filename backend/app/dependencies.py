from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
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


def require_authenticated_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    service: AuthService = Depends(get_auth_service),
) -> tuple[User, str]:
    session_token = get_optional_session_token(request, settings)
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    authenticated = service.authenticate_session(session_token)
    if authenticated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user, _ = authenticated
    return user, session_token


def get_optional_session_token(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Optional[str]:
    return request.cookies.get(settings.auth_session_cookie_name)


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
