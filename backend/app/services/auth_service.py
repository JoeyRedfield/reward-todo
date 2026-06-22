import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AccessToken, SessionRecord, TaskProject, TaskTemplate, User
from app.schemas.auth import RegisterRequest
from app.security import (
    generate_access_token,
    generate_session_token,
    hash_access_token,
    hash_password,
    hash_session_token,
    normalize_username,
    session_expiry,
    utc_now,
    verify_password,
)


class AuthService:
    DEFAULT_WORKSPACE_PROJECTS = [
        (
            "学习",
            0,
            [
                ("背单词 20 分钟", 20, 8, ""),
                ("深度阅读 30 分钟", 30, 12, ""),
            ],
        ),
        (
            "运动",
            1,
            [
                ("力量训练 30 分钟", 30, 15, ""),
                ("拉伸 15 分钟", 15, 6, ""),
            ],
        ),
        (
            "生活",
            2,
            [
                ("整理房间 20 分钟", 20, 10, ""),
            ],
        ),
    ]

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    def ensure_initial_user(self, username: str, password: str) -> User:
        normalized_username = normalize_username(username)
        user = self._get_user_by_username(normalized_username)
        if user is not None:
            return user

        user = User(
            username=normalized_username,
            display_name=normalized_username,
            email=f"{normalized_username}@local.invalid",
            password_hash=hash_password(password),
            password_changed_at=utc_now(),
        )
        self.session.add(user)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing_user = self._get_user_by_username(normalized_username)
            if existing_user is not None:
                return existing_user
            raise
        self.session.refresh(user)
        return user

    def verify_credentials(self, username: str, password: str) -> Optional[User]:
        user = self._get_user_by_username(normalize_username(username))
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def register_user(self, payload: RegisterRequest) -> tuple[User, str, SessionRecord]:
        if not self.settings.auth_enable_registration:
            raise ValueError("Registration is disabled")
        if payload.password != payload.confirm_password:
            raise ValueError("Passwords do not match")

        normalized_username = normalize_username(payload.username)
        normalized_email = payload.email.strip().lower()

        if self._get_user_by_username(normalized_username) is not None:
            raise ValueError("用户名已存在")
        if self._get_user_by_email(normalized_email) is not None:
            raise ValueError("邮箱已存在")

        now = utc_now()
        user = User(
            username=normalized_username,
            display_name=payload.display_name.strip(),
            email=normalized_email,
            password_hash=hash_password(payload.password),
            password_changed_at=now,
            last_login_at=now,
        )
        self.session.add(user)
        try:
            self.session.flush()
            if payload.create_default_workspace:
                self._create_default_workspace(user)

            token = generate_session_token()
            record = SessionRecord(
                user_id=user.id,
                session_token_hash=hash_session_token(token),
                expires_at=session_expiry(self.settings.auth_session_days, now),
                last_seen_at=now,
            )
            self.session.add(record)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            if self._get_user_by_username(normalized_username) is not None:
                raise ValueError("用户名已存在")
            if self._get_user_by_email(normalized_email) is not None:
                raise ValueError("邮箱已存在")
            raise
        except Exception:
            self.session.rollback()
            raise

        self.session.refresh(user)
        self.session.refresh(record)
        return user, token, record

    def create_session(self, user: User) -> tuple[str, SessionRecord]:
        now = utc_now()
        token = generate_session_token()
        record = SessionRecord(
            user_id=user.id,
            session_token_hash=hash_session_token(token),
            expires_at=session_expiry(self.settings.auth_session_days, now),
            last_seen_at=now,
        )
        user.last_login_at = now
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return token, record

    def authenticate_session(self, raw_token: str) -> Optional[tuple[User, SessionRecord]]:
        token_hash = hash_session_token(raw_token)
        record = self.session.scalar(
            select(SessionRecord).where(SessionRecord.session_token_hash == token_hash)
        )
        if record is None:
            return None

        now = utc_now()
        if self._as_utc(record.expires_at) <= now:
            self.session.delete(record)
            self.session.commit()
            return None

        record.last_seen_at = now
        self.session.commit()
        user = self.session.get(User, record.user_id)
        if user is None:
            return None
        return user, record

    def delete_session(self, raw_token: str) -> None:
        token_hash = hash_session_token(raw_token)
        record = self.session.scalar(
            select(SessionRecord).where(SessionRecord.session_token_hash == token_hash)
        )
        if record is None:
            return
        self.session.delete(record)
        self.session.commit()

    def delete_session_best_effort(self, raw_token: str) -> None:
        try:
            self.delete_session(raw_token)
        except Exception:
            self.session.rollback()

    def delete_all_sessions_for_user(self, user_id: int) -> None:
        records = self.session.scalars(
            select(SessionRecord).where(SessionRecord.user_id == user_id)
        ).all()
        for record in records:
            self.session.delete(record)

    def change_password(self, user: User, new_password: str) -> User:
        user.password_hash = hash_password(new_password)
        user.password_changed_at = utc_now()
        self.delete_all_sessions_for_user(user.id)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def change_password_and_create_session(
        self,
        user: User,
        new_password: str,
    ) -> tuple[User, str, SessionRecord]:
        now = utc_now()
        token = generate_session_token()
        record = SessionRecord(
            user_id=user.id,
            session_token_hash=hash_session_token(token),
            expires_at=session_expiry(self.settings.auth_session_days, now),
            last_seen_at=now,
        )

        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.last_login_at = now
        self.delete_all_sessions_for_user(user.id)
        self.session.add(user)
        self.session.add(record)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(user)
        self.session.refresh(record)
        return user, token, record

    def list_sessions_for_user(
        self,
        user_id: int,
        current_session_token: Optional[str] = None,
    ) -> list[tuple[SessionRecord, bool]]:
        records = self.session.scalars(
            select(SessionRecord)
            .where(SessionRecord.user_id == user_id)
            .order_by(SessionRecord.created_at.desc(), SessionRecord.id.desc())
        ).all()
        current_hash = (
            hash_session_token(current_session_token) if current_session_token is not None else None
        )
        return [(record, record.session_token_hash == current_hash) for record in records]

    def revoke_session_for_user(self, user_id: int, session_id: int) -> bool:
        record = self.session.get(SessionRecord, session_id)
        if record is None or record.user_id != user_id:
            return False
        self.session.delete(record)
        self.session.commit()
        return True

    def revoke_other_sessions_for_user(
        self,
        user_id: int,
        current_session_token: Optional[str] = None,
    ) -> int:
        current_hash = (
            hash_session_token(current_session_token) if current_session_token is not None else None
        )
        records = self.session.scalars(
            select(SessionRecord).where(SessionRecord.user_id == user_id)
        ).all()

        revoked_count = 0
        for record in records:
            if current_hash is not None and record.session_token_hash == current_hash:
                continue
            self.session.delete(record)
            revoked_count += 1

        self.session.commit()
        return revoked_count

    def create_access_token(
        self,
        user: User,
        *,
        name: str,
        token_type: str,
        expires_in_seconds: Optional[int] = None,
        expires_in_days: Optional[int] = None,
    ) -> tuple[str, AccessToken]:
        raw_token = generate_access_token()
        now = utc_now()
        expires_at = self._resolve_access_token_expiry(
            now,
            expires_in_seconds=expires_in_seconds,
            expires_in_days=expires_in_days,
        )
        record = AccessToken(
            user_id=user.id,
            name=name,
            token_type=token_type,
            token_hash=hash_access_token(raw_token),
            expires_at=expires_at,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return raw_token, record

    def list_access_tokens_for_user(self, user_id: int) -> list[AccessToken]:
        return self.session.scalars(
            select(AccessToken)
            .where(AccessToken.user_id == user_id)
            .order_by(AccessToken.created_at.desc(), AccessToken.id.desc())
        ).all()

    def revoke_access_token_for_user(self, user_id: int, token_id: int) -> bool:
        record = self.session.get(AccessToken, token_id)
        if record is None or record.user_id != user_id:
            return False
        self.session.delete(record)
        self.session.commit()
        return True

    def authenticate_access_token(
        self,
        raw_token: str,
        *,
        accepted_token_types: Optional[set[str]] = None,
    ) -> Optional[tuple[User, AccessToken]]:
        token_hash = hash_access_token(raw_token)
        record = self.session.scalar(
            select(AccessToken).where(AccessToken.token_hash == token_hash)
        )
        if record is None:
            return None

        if accepted_token_types is not None and record.token_type not in accepted_token_types:
            return None

        now = utc_now()
        if record.expires_at is not None and self._as_utc(record.expires_at) <= now:
            self.session.delete(record)
            self.session.commit()
            return None

        record.last_seen_at = now
        self.session.commit()
        user = self.session.get(User, record.user_id)
        if user is None:
            return None
        return user, record

    def build_api_base_url(self) -> str:
        return f"{self._root_url().rstrip('/')}/api"

    def build_mcp_url(self) -> str:
        return f"{self._root_url().rstrip('/')}/mcp"

    def _get_user_by_username(self, username: str) -> Optional[User]:
        return self.session.scalar(select(User).where(User.username == username))

    def _get_user_by_email(self, email: str) -> Optional[User]:
        return self.session.scalar(select(User).where(User.email == email))

    def _create_default_workspace(self, user: User) -> None:
        for project_name, sort_order, templates in self.DEFAULT_WORKSPACE_PROJECTS:
            project = TaskProject(
                user_id=user.id,
                name=project_name,
                status="active",
                sort_order=sort_order,
            )
            self.session.add(project)
            self.session.flush()
            for template_name, duration_minutes, reward_amount, notes in templates:
                self.session.add(
                    TaskTemplate(
                        project_id=project.id,
                        name=template_name,
                        default_estimated_duration_minutes=duration_minutes,
                        default_reward_amount=reward_amount,
                        notes=notes,
                        is_active=True,
                    )
                )

    def _root_url(self) -> str:
        root_url = getattr(self.settings, "app_root_url", None)
        if root_url:
            return root_url
        return "http://localhost:8088"

    def _resolve_access_token_expiry(
        self,
        now: datetime.datetime,
        *,
        expires_in_seconds: Optional[int],
        expires_in_days: Optional[int],
    ) -> Optional[datetime.datetime]:
        if expires_in_seconds is not None:
            if expires_in_seconds == 0:
                return None
            return now + datetime.timedelta(seconds=expires_in_seconds)

        if expires_in_days is not None:
            return now + datetime.timedelta(days=expires_in_days)

        return now + datetime.timedelta(days=30)

    def _as_utc(self, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=utc_now().tzinfo)
        return value.astimezone(utc_now().tzinfo)
