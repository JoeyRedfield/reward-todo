from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.config import Settings, get_settings
from app.dependencies import (
    get_auth_service,
    get_optional_session_token,
    require_authenticated_user,
)
from app.models import User
from app.schemas.auth import AuthUserRead, ChangePasswordRequest, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(
    response: Response,
    *,
    settings: Settings,
    session_token: str,
) -> None:
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
        max_age=settings.auth_session_days * 24 * 60 * 60,
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


@router.post("/login", response_model=AuthUserRead)
def login(
    payload: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    user = service.verify_credentials(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_token, _ = service.create_session(user)
    _set_session_cookie(response, settings=settings, session_token=session_token)
    return user


@router.post("/register", response_model=AuthUserRead)
def register(
    payload: RegisterRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    try:
        user, session_token, _ = service.register_user(payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_403_FORBIDDEN if detail == "Registration is disabled" else 400
        raise HTTPException(status_code=status_code, detail=detail)

    _set_session_cookie(response, settings=settings, session_token=session_token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_token: Optional[str] = Depends(get_optional_session_token),
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    if session_token is not None:
        service.delete_session_best_effort(session_token)
    _clear_session_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthUserRead)
def me(authenticated: tuple[User, str] = Depends(require_authenticated_user)):
    user, _ = authenticated
    return user


@router.post("/change-password", response_model=AuthUserRead)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    user, _ = authenticated
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match",
        )

    verified_user = service.verify_credentials(user.username, payload.current_password)
    if verified_user is None or verified_user.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    updated_user, new_session_token, _ = service.change_password_and_create_session(
        user, payload.new_password
    )
    _set_session_cookie(response, settings=settings, session_token=new_session_token)
    return updated_user
