import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect

from app.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_raise_without_initial_credentials_outside_test(monkeypatch):
    monkeypatch.delenv("AUTH_INITIAL_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_INITIAL_PASSWORD", raising=False)
    monkeypatch.setenv("TESTING", "false")

    with pytest.raises(ValueError, match="AUTH_INITIAL_USERNAME and AUTH_INITIAL_PASSWORD are required"):
        get_settings()


def test_settings_require_initial_credentials_outside_test(monkeypatch):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("TESTING", "false")

    settings = get_settings()

    assert settings.auth_initial_username == "reward"
    assert settings.auth_initial_password == "secret-pass"
    assert settings.auth_session_days == 7
    assert settings.auth_cookie_samesite == "lax"


def test_settings_require_lax_samesite(monkeypatch):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "strict")
    monkeypatch.setenv("TESTING", "false")

    with pytest.raises(ValueError, match="AUTH_COOKIE_SAMESITE must be lax"):
        get_settings()


def test_settings_require_positive_session_days(monkeypatch):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_SESSION_DAYS", "0")
    monkeypatch.setenv("TESTING", "false")

    with pytest.raises(ValueError, match="AUTH_SESSION_DAYS must be positive"):
        get_settings()


def test_auth_models_are_registered():
    models = importlib.import_module("app.models")

    assert models.User.__tablename__ == "users"
    assert models.SessionRecord.__tablename__ == "sessions"


def _build_alembic_subprocess(backend_dir: Path) -> tuple[list[str], dict[str, str]]:
    command = [sys.executable, "-m", "alembic"]
    env = os.environ.copy()

    alembic_command_spec = importlib.util.find_spec("alembic.command")
    if alembic_command_spec is not None:
        return command, env

    site_packages_dirs = sorted((backend_dir / ".venv" / "lib").glob("python*/site-packages"))
    if not site_packages_dirs:
        raise AssertionError("Could not locate project site-packages for Alembic")

    existing_pythonpath = env.get("PYTHONPATH")
    pythonpath_parts = [str(site_packages_dirs[0])]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return command, env


def test_auth_migrations_create_tables_and_indexes(tmp_path, monkeypatch):
    database_path = tmp_path / "auth_migration.db"
    database_url = f"sqlite:///{database_path}"
    backend_dir = Path(__file__).resolve().parents[1]

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("TESTING", "true")
    alembic_command, env = _build_alembic_subprocess(backend_dir)
    env["DATABASE_URL"] = database_url
    env["AUTH_INITIAL_USERNAME"] = "reward"
    env["AUTH_INITIAL_PASSWORD"] = "secret-pass"
    env["TESTING"] = "true"

    subprocess.run(
        [*alembic_command, "-c", "alembic.ini", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
    )

    engine = create_engine(database_url, future=True)
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert "users" in table_names
        assert "sessions" in table_names

        indexes = {index["name"]: index for index in inspector.get_indexes("sessions")}
        assert "ix_sessions_user_id" in indexes
        assert indexes["ix_sessions_user_id"]["column_names"] == ["user_id"]
        assert "ix_sessions_session_token_hash" in indexes
        assert indexes["ix_sessions_session_token_hash"]["column_names"] == ["session_token_hash"]
        assert bool(indexes["ix_sessions_session_token_hash"]["unique"]) is True
        assert "ix_sessions_expires_at" in indexes
        assert indexes["ix_sessions_expires_at"]["column_names"] == ["expires_at"]
    finally:
        engine.dispose()
