import os
from functools import lru_cache
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_compat_env(primary_key: str, legacy_key: str) -> Optional[str]:
    return os.environ.get(primary_key) or os.environ.get(legacy_key)


def resolve_initial_auth_credentials_from_env() -> tuple[Optional[str], Optional[str]]:
    return (
        _resolve_compat_env("AUTH_INITIAL_USERNAME", "APP_BASIC_AUTH_USER"),
        _resolve_compat_env("AUTH_INITIAL_PASSWORD", "APP_BASIC_AUTH_PASSWORD"),
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Reward Todo API"
    database_url: str = "sqlite:///./reward_todo_dev.db"
    readonly_token: str = "readonly-dev-token"
    app_root_url: str = "http://localhost:8088"
    auth_initial_username: Optional[str] = None
    auth_initial_password: Optional[str] = None
    auth_session_cookie_name: str = "reward_todo_session"
    auth_session_days: int = 7
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_enable_registration: bool = True
    auth_enable_api_tokens: bool = True
    auth_enable_mcp: bool = True
    testing: bool = False

    @model_validator(mode="before")
    @classmethod
    def apply_legacy_initial_auth_env(cls, data):
        values = dict(data or {})
        username, password = resolve_initial_auth_credentials_from_env()
        if not values.get("auth_initial_username") and username:
            values["auth_initial_username"] = username
        if not values.get("auth_initial_password") and password:
            values["auth_initial_password"] = password
        return values

    @field_validator("auth_cookie_samesite")
    @classmethod
    def validate_auth_cookie_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized != "lax":
            raise ValueError("AUTH_COOKIE_SAMESITE must be lax")
        return normalized

    @field_validator("auth_session_days")
    @classmethod
    def validate_auth_session_days(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("AUTH_SESSION_DAYS must be positive")
        return value


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.testing and (
        not settings.auth_initial_username or not settings.auth_initial_password
    ):
        raise ValueError(
            "AUTH_INITIAL_USERNAME and AUTH_INITIAL_PASSWORD are required "
            "(legacy APP_BASIC_AUTH_USER and APP_BASIC_AUTH_PASSWORD are also supported)"
        )
    return settings
