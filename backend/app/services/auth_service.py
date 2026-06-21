from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SessionRecord, User
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
        normalized_username = normalize_username(username)
        user = self._get_user_by_username(normalized_username)
        if user is not None:
            return user

        user = User(
            username=normalized_username,
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

    def _get_user_by_username(self, username: str) -> Optional[User]:
        return self.session.scalar(select(User).where(User.username == username))

    def _as_utc(self, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=utc_now().tzinfo)
        return value.astimezone(utc_now().tzinfo)
