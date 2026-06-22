from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, Field, field_validator
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
    app_root_url: str = "http://localhost:8088"
    auth_initial_username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_INITIAL_USERNAME", "APP_BASIC_AUTH_USER"),
    )
    auth_initial_password: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_INITIAL_PASSWORD", "APP_BASIC_AUTH_PASSWORD"),
    )
    auth_session_cookie_name: str = "reward_todo_session"
    auth_session_days: int = 7
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_enable_registration: bool = True
    auth_enable_api_tokens: bool = True
    auth_enable_mcp: bool = True
    testing: bool = False

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
        raise ValueError("AUTH_INITIAL_USERNAME and AUTH_INITIAL_PASSWORD are required")
    return settings
