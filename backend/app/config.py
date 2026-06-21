from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
