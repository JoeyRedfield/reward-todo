import bcrypt
import datetime
import hashlib
import secrets
from typing import Optional

SESSION_TOKEN_BYTES = 32
ACCESS_TOKEN_BYTES = 32


def normalize_username(username: str) -> str:
    return " ".join(username.strip().split()).lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_access_token() -> str:
    return secrets.token_urlsafe(ACCESS_TOKEN_BYTES)


def hash_access_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def session_expiry(days: int, now: Optional[datetime.datetime] = None) -> datetime.datetime:
    reference = now or utc_now()
    return reference + datetime.timedelta(days=days)
