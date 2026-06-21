# Reward Todo 登录功能完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Reward Todo 建立完整的应用内单用户登录体系，覆盖后端会话认证、前端登录态、修改密码、运维重置密码与关键测试。

**Architecture:** 后端新增 `users` 与 `sessions` 两张表，使用数据库持久化会话与 `HttpOnly` cookie。前端新增 `AuthProvider`、`/login` 页面、受保护路由和全局 `401` 处理；保留 `/api/public/*` 现有访问模型，只将 `/api/*` 纳入登录保护。

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, pytest, React 18, React Router, Vite, Vitest, Testing Library, bcrypt/passlib-compatible hashing

---

## File Map

### Backend

- Create: `backend/app/models/user.py`
- Create: `backend/app/models/session.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/security.py`
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/dependencies.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/task_reward.py`
- Create: `backend/alembic/versions/0002_add_auth_tables.py`
- Create: `backend/scripts/reset_password.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth_api.py`
- Modify: `backend/tests/test_public_api.py`

### Frontend

- Create: `frontend/src/auth/AuthContext.jsx`
- Create: `frontend/src/auth/ProtectedRoute.jsx`
- Create: `frontend/src/pages/Login.jsx`
- Create: `frontend/src/pages/Login.test.jsx`
- Create: `frontend/src/App.test.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/components/Layout.jsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/test/setup.js`

### Docs / Deploy

- Modify: `README.md`
- Modify: `docker-compose.yml`
- Modify: `proxy/nginx.conf`

## Task 1: 后端认证配置与数据模型

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/session.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`
- Create: `backend/alembic/versions/0002_add_auth_tables.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败测试，锁定启动配置与表结构的预期**

```python
from app.config import get_settings


def test_settings_require_initial_credentials_outside_test(monkeypatch):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.auth_initial_username == "reward"
    assert settings.auth_initial_password == "secret-pass"
    assert settings.auth_session_days == 7
    assert settings.auth_cookie_samesite == "lax"
```

```python
from app.models import SessionRecord, User


def test_auth_models_are_registered():
    assert User.__tablename__ == "users"
    assert SessionRecord.__tablename__ == "sessions"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py -k "settings_require_initial_credentials_outside_test or auth_models_are_registered" -v`

Expected: FAIL，提示 `SessionRecord` / `User` 不存在，且配置字段缺失。

- [ ] **Step 3: 最小实现配置、模型与迁移**

`backend/app/config.py`

```python
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Reward Todo API"
    database_url: str = "sqlite:///./reward_todo_dev.db"
    readonly_token: str = "readonly-dev-token"
    auth_initial_username: str | None = None
    auth_initial_password: str | None = None
    auth_session_cookie_name: str = "reward_todo_session"
    auth_session_days: int = 7
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    testing: bool = False

    @field_validator("auth_cookie_samesite")
    @classmethod
    def validate_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized != "lax":
            raise ValueError("AUTH_COOKIE_SAMESITE must be lax")
        return normalized

    @field_validator("auth_session_days")
    @classmethod
    def validate_session_days(cls, value: int) -> int:
        if value < 1:
            raise ValueError("AUTH_SESSION_DAYS must be positive")
        return value


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.testing and (
        not settings.auth_initial_username or not settings.auth_initial_password
    ):
        raise ValueError("AUTH_INITIAL_USERNAME and AUTH_INITIAL_PASSWORD are required")
    return settings
```

`backend/app/models/user.py`

```python
import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    password_changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sessions = relationship("SessionRecord", back_populates="user", cascade="all, delete-orphan")
```

`backend/app/models/session.py`

```python
import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user = relationship("User", back_populates="sessions")
```

`backend/app/models/__init__.py`

```python
from app.models.daily_task import DailyTask
from app.models.reward_ledger import RewardLedger
from app.models.session import SessionRecord
from app.models.task_project import TaskProject
from app.models.task_template import TaskTemplate
from app.models.user import User

__all__ = [
    "DailyTask",
    "RewardLedger",
    "SessionRecord",
    "TaskProject",
    "TaskTemplate",
    "User",
]
```

`backend/requirements.txt`

```txt
fastapi>=0.115,<1
uvicorn>=0.30,<1
sqlalchemy>=2.0,<3
asyncpg>=0.30,<1
psycopg2-binary>=2.9,<3
pydantic-settings>=2.0,<3
httpx>=0.28,<1
pytest>=8.0,<9
alembic>=1.14,<2
bcrypt>=4.1,<5
```

`backend/alembic/versions/0002_add_auth_tables.py`

```python
"""add auth tables

Revision ID: 0002_add_auth_tables
Revises: 0001_init_task_reward
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_auth_tables"
down_revision = "0001_init_task_reward"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=200), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_token_hash", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_session_token_hash", "sessions", ["session_token_hash"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_session_token_hash", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py -k "settings_require_initial_credentials_outside_test or auth_models_are_registered" -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend/app/config.py backend/app/models/user.py backend/app/models/session.py backend/app/models/__init__.py backend/requirements.txt backend/alembic/versions/0002_add_auth_tables.py backend/tests/test_auth_api.py
git commit -m "feat: add auth data model and config"
```

## Task 2: 后端安全工具、初始化与认证服务

**Files:**
- Create: `backend/app/security.py`
- Create: `backend/app/services/auth_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败测试，覆盖初始化用户与核心服务能力**

```python
from app.services.auth_service import AuthService


def test_bootstrap_user_is_created_once(db_session):
    service = AuthService(db_session)

    created = service.ensure_initial_user("Reward", "super-secret")
    skipped = service.ensure_initial_user("Other", "ignored-pass")

    assert created.username == "reward"
    assert skipped.id == created.id
    assert service.verify_credentials("reward", "super-secret").id == created.id
```

```python
def test_create_and_revoke_session(db_session):
    service = AuthService(db_session)
    user = service.ensure_initial_user("reward", "secret-pass")

    raw_token, session = service.create_session(user)
    resolved_user, resolved_session = service.authenticate_session(raw_token)

    assert resolved_user.id == user.id
    assert resolved_session.id == session.id

    service.delete_session(raw_token)

    assert service.authenticate_session(raw_token) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py -k "bootstrap_user_is_created_once or create_and_revoke_session" -v`

Expected: FAIL，提示 `AuthService` 不存在或方法缺失。

- [ ] **Step 3: 最小实现认证工具与服务**

`backend/app/security.py`

```python
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt


def normalize_username(value: str) -> str:
    return value.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)


def session_expiry(days: int) -> datetime:
    return utc_now() + timedelta(days=days)
```

`backend/app/services/auth_service.py`

```python
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.session import SessionRecord
from app.models.user import User
from app.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    normalize_username,
    session_expiry,
    utc_now,
    verify_password,
)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    def ensure_initial_user(self, username: str, password: str) -> User:
        existing = self.session.scalar(select(User))
        if existing is not None:
            return existing

        user = User(
            username=normalize_username(username),
            password_hash=hash_password(password),
            password_changed_at=utc_now(),
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def verify_credentials(self, username: str, password: str) -> User | None:
        normalized = normalize_username(username)
        user = self.session.scalar(select(User).where(User.username == normalized))
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_session(self, user: User) -> tuple[str, SessionRecord]:
        raw_token = generate_session_token()
        record = SessionRecord(
            user_id=user.id,
            session_token_hash=hash_session_token(raw_token),
            expires_at=session_expiry(self.settings.auth_session_days),
            last_seen_at=utc_now(),
        )
        user.last_login_at = utc_now()
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return raw_token, record

    def authenticate_session(self, raw_token: str) -> tuple[User, SessionRecord] | None:
        token_hash = hash_session_token(raw_token)
        record = self.session.scalar(
            select(SessionRecord).where(SessionRecord.session_token_hash == token_hash)
        )
        if record is None:
            return None
        if record.expires_at <= utc_now():
            self.session.delete(record)
            self.session.commit()
            return None
        record.last_seen_at = utc_now()
        record.expires_at = session_expiry(self.settings.auth_session_days)
        self.session.commit()
        self.session.refresh(record)
        return record.user, record

    def delete_session(self, raw_token: str) -> None:
        token_hash = hash_session_token(raw_token)
        record = self.session.scalar(
            select(SessionRecord).where(SessionRecord.session_token_hash == token_hash)
        )
        if record is None:
            return
        self.session.delete(record)
        self.session.commit()

    def delete_all_sessions_for_user(self, user_id: int) -> None:
        for record in self.session.scalars(select(SessionRecord).where(SessionRecord.user_id == user_id)):
            self.session.delete(record)
        self.session.commit()

    def change_password(self, user: User, new_password: str) -> User:
        user.password_hash = hash_password(new_password)
        user.password_changed_at = utc_now()
        self.session.commit()
        self.session.refresh(user)
        return user
```

`backend/app/main.py`

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
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
    app.include_router(public_router)
    app.include_router(auth_router)
    app.include_router(task_reward_router)
    return app
```

`backend/tests/conftest.py`

```python
    os.environ["AUTH_INITIAL_USERNAME"] = "reward"
    os.environ["AUTH_INITIAL_PASSWORD"] = "super-secret"
    os.environ["AUTH_COOKIE_SECURE"] = "false"
    os.environ["TESTING"] = "true"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py -k "bootstrap_user_is_created_once or create_and_revoke_session" -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend/app/security.py backend/app/services/auth_service.py backend/app/main.py backend/tests/conftest.py backend/tests/test_auth_api.py
git commit -m "feat: add auth service bootstrap and session helpers"
```

## Task 3: 后端鉴权依赖与 auth API

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/dependencies.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败测试，覆盖 login/logout/me/change-password**

```python
def test_login_sets_cookie_and_returns_user(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "reward"
    assert "reward_todo_session" in response.headers["set-cookie"]
```

```python
def test_protected_me_requires_valid_cookie(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "未登录"
```

```python
def test_change_password_rotates_sessions(client):
    login = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    cookie = login.cookies

    changed = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "super-secret",
            "new_password": "new-secret1",
            "confirm_new_password": "new-secret1",
        },
        cookies=cookie,
    )

    assert changed.status_code == 200
    assert client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "new-secret1"},
    ).status_code == 200
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py -k "login_sets_cookie_and_returns_user or protected_me_requires_valid_cookie or change_password_rotates_sessions" -v`

Expected: FAIL，提示 `/api/auth/*` 不存在。

- [ ] **Step 3: 实现 schema、依赖和 auth 路由**

`backend/app/schemas/auth.py`

```python
from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class AuthUserRead(BaseModel):
    id: int
    username: str
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)
    confirm_new_password: str = Field(min_length=8, max_length=200)
```

`backend/app/dependencies.py`

```python
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.auth_service import AuthService
from app.services.task_reward_service import TaskRewardService


def get_db_session():
    yield from get_db()


def get_task_reward_service(session: Session = Depends(get_db_session)) -> TaskRewardService:
    return TaskRewardService(session)


def get_auth_service(session: Session = Depends(get_db_session)) -> AuthService:
    return AuthService(session)


def require_authenticated_user(
    session_token: Optional[str] = Cookie(default=None, alias="reward_todo_session"),
    auth_service: AuthService = Depends(get_auth_service),
):
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    authenticated = auth_service.authenticate_session(session_token)
    if authenticated is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    user, _ = authenticated
    return user
```

`backend/app/api/auth.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.config import get_settings
from app.dependencies import get_auth_service, require_authenticated_user
from app.schemas.auth import AuthUserRead, ChangePasswordRequest, LoginRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=token,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
        secure=settings.auth_cookie_secure,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        path="/",
    )


@router.post("/login", response_model=AuthUserRead)
def login(
    payload: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    user = auth_service.verify_credentials(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token, _ = auth_service.create_session(user)
    _set_session_cookie(response, token)
    return AuthUserRead.model_validate(user)


@router.post("/logout")
def logout(
    response: Response,
    user=Depends(require_authenticated_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    del user
    response.delete_cookie(get_settings().auth_session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=AuthUserRead)
def me(user=Depends(require_authenticated_user)):
    return AuthUserRead.model_validate(user)


@router.post("/change-password", response_model=AuthUserRead)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    user=Depends(require_authenticated_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="两次输入的新密码不一致")
    verified_user = auth_service.verify_credentials(user.username, payload.current_password)
    if verified_user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
    auth_service.change_password(user, payload.new_password)
    auth_service.delete_all_sessions_for_user(user.id)
    token, _ = auth_service.create_session(user)
    _set_session_cookie(response, token)
    return AuthUserRead.model_validate(user)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py -k "login_sets_cookie_and_returns_user or protected_me_requires_valid_cookie or change_password_rotates_sessions" -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend/app/schemas/auth.py backend/app/api/auth.py backend/app/dependencies.py backend/app/main.py backend/tests/test_auth_api.py
git commit -m "feat: add auth api and session dependency"
```

## Task 4: 将现有业务接口纳入登录保护

**Files:**
- Modify: `backend/app/api/task_reward.py`
- Modify: `backend/tests/test_auth_api.py`
- Modify: `backend/tests/test_public_api.py`

- [ ] **Step 1: 写失败测试，证明业务接口必须登录且 public 保持不变**

```python
def test_task_projects_requires_login(client):
    response = client.get("/api/task-projects")

    assert response.status_code == 401
    assert response.json()["detail"] == "未登录"
```

```python
def test_public_health_remains_open(client):
    response = client.get("/api/public/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py::test_task_projects_requires_login backend/tests/test_public_api.py::test_public_health_remains_open -v`

Expected: `test_task_projects_requires_login` FAIL，因为接口仍可匿名访问。

- [ ] **Step 3: 最小实现统一鉴权接入**

`backend/app/api/task_reward.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import (
    get_task_reward_service,
    require_authenticated_user,
)

router = APIRouter(
    prefix="/api",
    tags=["task-reward"],
    dependencies=[Depends(require_authenticated_user)],
)
```

其余 handler 保持不变，只通过 router 级依赖统一保护。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py::test_task_projects_requires_login backend/tests/test_public_api.py::test_public_health_remains_open -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend/app/api/task_reward.py backend/tests/test_auth_api.py backend/tests/test_public_api.py
git commit -m "feat: protect task reward api with auth"
```

## Task 5: 运维重置密码脚本与后端全量认证测试

**Files:**
- Create: `backend/scripts/reset_password.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败测试，覆盖密码重置脚本核心行为**

```python
from app.services.auth_service import AuthService


def test_reset_password_clears_existing_sessions(db_session):
    service = AuthService(db_session)
    user = service.ensure_initial_user("reward", "super-secret")
    raw_token, _ = service.create_session(user)

    from scripts.reset_password import reset_password

    reset_password(db_session, "brand-new-pass")

    assert service.authenticate_session(raw_token) is None
    assert service.verify_credentials("reward", "brand-new-pass") is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py::test_reset_password_clears_existing_sessions -v`

Expected: FAIL，提示 `scripts.reset_password` 不存在。

- [ ] **Step 3: 实现脚本**

`backend/scripts/reset_password.py`

```python
import argparse

from app.database import get_session_factory, init_db
from app.models.user import User
from app.services.auth_service import AuthService


def reset_password(session, new_password: str) -> None:
    service = AuthService(session)
    user = session.query(User).one()
    service.change_password(user, new_password)
    service.delete_all_sessions_for_user(user.id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    init_db()
    session = get_session_factory()()
    try:
        reset_password(session, args.password)
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过，并补跑后端认证套件**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_auth_api.py -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend/scripts/reset_password.py backend/tests/test_auth_api.py
git commit -m "feat: add password reset script"
```

## Task 6: 前端 API 客户端与认证上下文

**Files:**
- Create: `frontend/src/auth/AuthContext.jsx`
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/test/setup.js`
- Test: `frontend/src/App.test.jsx`

- [ ] **Step 1: 写失败测试，覆盖启动初始化登录态与 401 处理**

```jsx
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

test("redirects unauthenticated users to login", async () => {
  render(
    <MemoryRouter initialEntries={["/today"]}>
      <App />
    </MemoryRouter>
  );

  expect(await screen.findByRole("heading", { name: "登录" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run frontend/src/App.test.jsx`

Expected: FAIL，因为 `AuthProvider` / `/login` 不存在。

- [ ] **Step 3: 实现 API 客户端与 AuthProvider**

`frontend/src/api/client.js`

```javascript
let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

function getErrorMessage(error, fallback) {
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

async function request(path, options) {
  const response = await fetch(`/api${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });

  if (response.status === 401 && unauthorizedHandler) {
    unauthorizedHandler();
  }

  if (!response.ok) {
    let detail = "request failed";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {}
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export async function login(payload) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout() {
  return request("/auth/logout", { method: "POST" });
}

export async function fetchCurrentUser() {
  return request("/auth/me");
}

export async function changePassword(payload) {
  return request("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
```

`frontend/src/auth/AuthContext.jsx`

```jsx
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  changePassword as changePasswordRequest,
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  setUnauthorizedHandler,
} from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setSessionExpired(true);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    let mounted = true;
    fetchCurrentUser()
      .then((currentUser) => {
        if (mounted) {
          setUser(currentUser);
        }
      })
      .catch(() => {
        if (mounted) {
          setUser(null);
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      sessionExpired,
      clearSessionExpired() {
        setSessionExpired(false);
      },
      async login(payload) {
        const currentUser = await loginRequest(payload);
        setUser(currentUser);
        setSessionExpired(false);
        return currentUser;
      },
      async logout() {
        await logoutRequest();
        setUser(null);
      },
      async changePassword(payload) {
        const currentUser = await changePasswordRequest(payload);
        setUser(currentUser);
        return currentUser;
      },
    }),
    [loading, sessionExpired, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run frontend/src/App.test.jsx`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add frontend/src/api/client.js frontend/src/auth/AuthContext.jsx frontend/src/test/setup.js frontend/src/App.test.jsx
git commit -m "feat: add frontend auth context"
```

## Task 7: 前端受保护路由与登录页

**Files:**
- Create: `frontend/src/auth/ProtectedRoute.jsx`
- Create: `frontend/src/pages/Login.jsx`
- Modify: `frontend/src/App.jsx`
- Test: `frontend/src/App.test.jsx`
- Test: `frontend/src/pages/Login.test.jsx`

- [ ] **Step 1: 写失败测试，覆盖登录跳转与回跳**

```jsx
test("redirects back to requested page after login", async () => {
  render(<App />, { wrapper: createUnauthenticatedWrapper("/rewards") });

  await userEvent.type(screen.getByLabelText("用户名"), "reward");
  await userEvent.type(screen.getByLabelText("密码"), "super-secret");
  await userEvent.click(screen.getByRole("button", { name: "登录" }));

  await waitFor(() => {
    expect(screen.getByText("把奖励额度当作账本")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run frontend/src/App.test.jsx frontend/src/pages/Login.test.jsx`

Expected: FAIL，因为登录页和路由守卫尚未接入。

- [ ] **Step 3: 实现受保护路由与登录页**

`frontend/src/auth/ProtectedRoute.jsx`

```jsx
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { loading, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="loading-card">加载中...</div>;
  }

  if (!user) {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  return <Outlet />;
}
```

`frontend/src/pages/Login.jsx`

```jsx
import { useState } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { login, loading, sessionExpired, clearSessionExpired, user } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  if (!loading && user) {
    return <Navigate to={searchParams.get("redirect") || "/today"} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    clearSessionExpired();
    try {
      await login({ username, password });
      navigate(searchParams.get("redirect") || "/today", { replace: true });
    } catch (submitError) {
      setError(submitError.message || "用户名或密码错误");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="page-kicker">Login</div>
        <h1>登录</h1>
        {sessionExpired ? (
          <div className="error-banner">登录已失效，请重新登录</div>
        ) : null}
        {error ? <div className="error-banner">{error}</div> : null}
        <label>
          用户名
          <input value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          密码
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button className="primary-button" disabled={submitting}>
          {submitting ? "登录中..." : "登录"}
        </button>
      </form>
    </div>
  );
}
```

`frontend/src/App.jsx`

```jsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./components/Layout";
import LoginPage from "./pages/Login";
import TodayPage from "./pages/Today";
import ProjectsPage from "./pages/Projects";
import RewardsPage from "./pages/Rewards";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/today" replace />} />
              <Route path="/today" element={<TodayPage />} />
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/rewards" element={<RewardsPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run frontend/src/App.test.jsx frontend/src/pages/Login.test.jsx`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add frontend/src/auth/ProtectedRoute.jsx frontend/src/pages/Login.jsx frontend/src/App.jsx frontend/src/App.test.jsx frontend/src/pages/Login.test.jsx
git commit -m "feat: add login page and protected routing"
```

## Task 8: 侧边栏账户区与修改密码交互

**Files:**
- Modify: `frontend/src/components/Layout.jsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/App.test.jsx`

- [ ] **Step 1: 写失败测试，覆盖用户名显示、登出、改密码**

```jsx
test("shows account actions in sidebar", async () => {
  render(<App />, { wrapper: createAuthenticatedWrapper("/today") });

  expect(await screen.findByText("reward")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "修改密码" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "登出" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run frontend/src/App.test.jsx`

Expected: FAIL，因为侧边栏还没有账户区。

- [ ] **Step 3: 实现账户区和修改密码弹层**

`frontend/src/components/Layout.jsx`

```jsx
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { user, logout, changePassword } = useAuth();
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  async function handlePasswordSubmit(event) {
    event.preventDefault();
    setPasswordError("");
    setPasswordSuccess("");
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_new_password: confirmNewPassword,
      });
      setPasswordSuccess("密码已更新");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
      setShowPasswordForm(false);
    } catch (error) {
      setPasswordError(error.message || "修改密码失败");
    }
  }

  return (
    <div className="layout-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-kicker">Reward Todo</div>
          <h1 className="brand-title">个人任务板 + 奖励账本</h1>
          <p className="brand-copy">
            管理今天要做的事，完成后累计奖励额度，再决定怎么花掉它。
          </p>
        </div>
        <div className="account-panel">
          <div className="account-label">当前用户</div>
          <div className="account-name">{user?.username}</div>
          <div className="account-actions">
            <button className="ghost-button" onClick={() => setShowPasswordForm((value) => !value)}>
              修改密码
            </button>
            <button className="ghost-button" onClick={handleLogout}>
              登出
            </button>
          </div>
          {passwordError ? <div className="error-banner">{passwordError}</div> : null}
          {passwordSuccess ? <div className="success-banner">{passwordSuccess}</div> : null}
          {showPasswordForm ? (
            <form className="form-stack" onSubmit={handlePasswordSubmit}>
              <label>
                当前密码
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                />
              </label>
              <label>
                新密码
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
              </label>
              <label>
                确认新密码
                <input
                  type="password"
                  value={confirmNewPassword}
                  onChange={(event) => setConfirmNewPassword(event.target.value)}
                />
              </label>
              <button className="primary-button">确认修改</button>
            </form>
          ) : null}
        </div>
        <nav className="nav-links">
          <NavLink to="/today">今日</NavLink>
          <NavLink to="/projects">项目</NavLink>
          <NavLink to="/rewards">奖励</NavLink>
        </nav>
      </aside>
      <main className="page-shell">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run frontend/src/App.test.jsx`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add frontend/src/components/Layout.jsx frontend/src/styles.css frontend/src/App.test.jsx
git commit -m "feat: add sidebar account actions"
```

## Task 9: 部署入口与文档更新

**Files:**
- Modify: `docker-compose.yml`
- Modify: `proxy/nginx.conf`
- Modify: `README.md`

- [ ] **Step 1: 写变更前检查，确认 Basic Auth 仍被硬编码**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo && rg -n "auth_basic|replace-me|8088" README.md proxy/nginx.conf docker-compose.yml`

Expected: 输出显示 `proxy/nginx.conf` 中 `/` 与 `/api/` 位置的 `auth_basic` 仍硬编码启用，`README.md` 仍把 Basic Auth 当默认入口说明。

- [ ] **Step 2: 修改代理与部署说明**

`proxy/nginx.conf`

```nginx
server {
  listen 80;
  resolver 127.0.0.11 ipv6=off;

  location /api/public/ {
    set $backend_upstream http://backend:8000;
    proxy_pass $backend_upstream;
  }

  location /api/ {
    if ($http_x_basic_auth_enabled = "true") {
      auth_basic "Reward Todo";
      auth_basic_user_file /etc/nginx/.htpasswd;
    }
    set $backend_upstream http://backend:8000;
    proxy_pass $backend_upstream;
  }

  location / {
    if ($http_x_basic_auth_enabled = "true") {
      auth_basic "Reward Todo";
      auth_basic_user_file /etc/nginx/.htpasswd;
    }
    set $frontend_upstream http://frontend:5173;
    proxy_pass $frontend_upstream;
  }
}
```

`docker-compose.yml`

```yaml
  proxy:
    image: nginx:1.27-alpine
    ports:
      - "8088:80"
    environment:
      BASIC_AUTH_ENABLED: ${ENABLE_BASIC_AUTH:-true}
```

`README.md`

```md
- `http://localhost:8088/`：统一入口，默认启用应用内登录；如需额外保护，可开启 Basic Auth
- `http://localhost:8088/api/public/health`：无需认证的后端健康检查

新增环境变量：

- `AUTH_INITIAL_USERNAME`
- `AUTH_INITIAL_PASSWORD`
- `AUTH_SESSION_COOKIE_NAME`
- `AUTH_SESSION_DAYS`
- `AUTH_COOKIE_SECURE`
- `ENABLE_BASIC_AUTH`
```

- [ ] **Step 3: 运行基础验证**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo && rg -n "AUTH_INITIAL_USERNAME|ENABLE_BASIC_AUTH|应用内登录" README.md docker-compose.yml proxy/nginx.conf`

Expected: PASS，输出包含新的认证与 Basic Auth 可选说明。

- [ ] **Step 4: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add README.md docker-compose.yml proxy/nginx.conf
git commit -m "docs: document app auth and optional basic auth"
```

## Task 10: 端到端验证

**Files:**
- No code changes expected

- [ ] **Step 1: 运行后端测试**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest`

Expected: PASS

- [ ] **Step 2: 运行前端测试**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run`

Expected: PASS

- [ ] **Step 3: 构建前端**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm run build`

Expected: PASS，生成 `dist/`

- [ ] **Step 4: 验证工作区状态**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo && git status --short`

Expected: 工作区仅包含本轮预期变更，或为空。

- [ ] **Step 5: 最终提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend frontend README.md docker-compose.yml proxy/nginx.conf
git commit -m "feat: add application login flow"
```
