from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.config import Settings, get_settings
from app.dependencies import require_authenticated_user
from app.models import User
from app.schemas.auth import (
    AccessTokenCreateRead,
    AccessTokenCreateRequest,
    AccessTokenInfoRead,
    AccessTokenListRead,
    AccountProfileRead,
    SessionInfoRead,
    SessionListRead,
)
from app.services.auth_service import AuthService
from app.dependencies import get_auth_service

router = APIRouter(
    prefix="/api/account",
    tags=["account"],
    dependencies=[],
)


@router.get("/profile", response_model=AccountProfileRead)
def profile(
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    settings: Settings = Depends(get_settings),
):
    user, _ = authenticated
    return AccountProfileRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        created_at=user.created_at,
        password_changed_at=user.password_changed_at,
        last_login_at=user.last_login_at,
        api_token_enabled=settings.auth_enable_api_tokens,
        mcp_enabled=settings.auth_enable_mcp,
    )


@router.get("/sessions", response_model=SessionListRead)
def list_sessions(
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: AuthService = Depends(get_auth_service),
):
    user, credential = authenticated
    items = [
        SessionInfoRead(
            id=record.id,
            created_at=record.created_at,
            expires_at=record.expires_at,
            last_seen_at=record.last_seen_at,
            is_current=is_current,
        )
        for record, is_current in service.list_sessions_for_user(user.id, credential)
    ]
    return SessionListRead(items=items)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
def revoke_other_sessions(
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: AuthService = Depends(get_auth_service),
):
    user, credential = authenticated
    service.revoke_other_sessions_for_user(user.id, credential)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: int,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: AuthService = Depends(get_auth_service),
):
    user, _ = authenticated
    deleted = service.revoke_session_for_user(user.id, session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tokens", response_model=AccessTokenListRead)
def list_tokens(
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: AuthService = Depends(get_auth_service),
):
    user, _ = authenticated
    items = [
        AccessTokenInfoRead(
            id=record.id,
            name=record.name,
            token_type=record.token_type,
            created_at=record.created_at,
            expires_at=record.expires_at,
            last_seen_at=record.last_seen_at,
        )
        for record in service.list_access_tokens_for_user(user.id)
    ]
    return AccessTokenListRead(items=items)


@router.post("/tokens", response_model=AccessTokenCreateRead, status_code=status.HTTP_201_CREATED)
def create_token(
    payload: AccessTokenCreateRequest,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    user, _ = authenticated
    if payload.token_type == "api" and not settings.auth_enable_api_tokens:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="api token is not enabled",
        )
    if payload.token_type == "mcp" and not settings.auth_enable_mcp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mcp server is not enabled",
        )

    verified_user = service.verify_credentials(user.username, payload.password)
    if verified_user is None or verified_user.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    raw_token, record = service.create_access_token(
        user,
        name=payload.name,
        token_type=payload.token_type,
        expires_in_seconds=payload.expires_in_seconds,
        expires_in_days=payload.expires_in_days,
    )
    return AccessTokenCreateRead(
        id=record.id,
        name=record.name,
        token_type=record.token_type,
        token=raw_token,
        created_at=record.created_at,
        expires_at=record.expires_at,
        api_base_url=service.build_api_base_url() if record.token_type == "api" else None,
        mcp_url=service.build_mcp_url() if record.token_type == "mcp" else None,
    )


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: int,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: AuthService = Depends(get_auth_service),
):
    user, _ = authenticated
    deleted = service.revoke_access_token_for_user(user.id, token_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
