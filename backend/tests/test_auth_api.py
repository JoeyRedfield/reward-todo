import importlib
import os
from pathlib import Path
import subprocess
import sys
from types import MethodType

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.models import SessionRecord, User
from app.security import verify_password
from app.services.auth_service import AuthService


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
    env = os.environ.copy()
    site_packages_dirs = sorted((backend_dir / ".venv" / "lib").glob("python*/site-packages"))
    if site_packages_dirs:
        existing_pythonpath = env.get("PYTHONPATH")
        pythonpath_parts = [str(path) for path in site_packages_dirs]
        if existing_pythonpath:
            pythonpath_parts.append(existing_pythonpath)
        env["REWARD_TODO_SITE_PACKAGES"] = os.pathsep.join(pythonpath_parts)

    command = [
        sys.executable,
        "-c",
        (
            "import os, sys; "
            "cwd = os.getcwd(); "
            "site_packages = os.environ.get('REWARD_TODO_SITE_PACKAGES', ''); "
            "sys.path = [p for p in sys.path if p not in ('', cwd)]; "
            "paths = [p for p in site_packages.split(os.pathsep) if p]; "
            "sys.path[:0] = paths; "
            "from alembic.config import CommandLine; "
            "sys.path.insert(0, cwd); "
            "CommandLine(prog='alembic').main(argv=['-c', 'alembic.ini', 'upgrade', 'head'])"
        ),
    ]
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


def test_bootstrap_user_is_created_once(db_session, monkeypatch):
    service = AuthService(db_session)

    first_user = service.ensure_initial_user("  Reward Admin  ", "secret-pass")
    second_user = service.ensure_initial_user("Reward Admin", "different-pass")

    users = db_session.scalars(select(User)).all()

    assert first_user.id == second_user.id
    assert len(users) == 1
    assert first_user.username == "reward admin"
    assert verify_password("secret-pass", first_user.password_hash) is True


def test_create_and_revoke_session(db_session, monkeypatch):
    service = AuthService(db_session)
    user = service.ensure_initial_user("reward", "secret-pass")

    session_token, session_record = service.create_session(user)
    authenticated = service.authenticate_session(session_token)
    persisted_session = db_session.scalar(select(SessionRecord))

    assert authenticated is not None
    authenticated_user, authenticated_record = authenticated
    assert authenticated_user.id == user.id
    assert session_record.id is not None
    assert authenticated_record.id == session_record.id
    assert persisted_session is not None
    assert persisted_session.id == session_record.id

    service.delete_session(session_token)
    after_delete_user = service.authenticate_session(session_token)

    assert after_delete_user is None
    assert db_session.scalar(select(SessionRecord)) is None


def test_bootstrap_user_recovers_from_unique_conflict(db_session, monkeypatch):
    existing_user = User(
        username="reward admin",
        password_hash="existing-hash",
    )
    db_session.add(existing_user)
    db_session.commit()
    db_session.refresh(existing_user)

    service = AuthService(db_session)
    original_commit = db_session.commit
    commit_calls = {"count": 0}
    lookup_calls = {"count": 0}

    def fake_get_user_by_username(self, username):
        lookup_calls["count"] += 1
        if lookup_calls["count"] == 1:
            return None
        return existing_user

    def flaky_commit():
        commit_calls["count"] += 1
        if commit_calls["count"] == 1:
            raise IntegrityError("insert", {}, Exception("duplicate"))
        original_commit()

    monkeypatch.setattr(service, "_get_user_by_username", MethodType(fake_get_user_by_username, service))
    monkeypatch.setattr(db_session, "commit", flaky_commit)

    fetched_user = service.ensure_initial_user("Reward Admin", "secret-pass")

    assert fetched_user.id == existing_user.id
    assert commit_calls["count"] == 1
    assert lookup_calls["count"] == 2


def test_change_password_commits_once_and_clears_sessions(db_session, monkeypatch):
    service = AuthService(db_session)
    user = service.ensure_initial_user("reward", "secret-pass")
    first_token, _ = service.create_session(user)
    second_token, _ = service.create_session(user)
    original_commit = db_session.commit
    commit_calls = {"count": 0}

    def tracking_commit():
        commit_calls["count"] += 1
        original_commit()

    monkeypatch.setattr(db_session, "commit", tracking_commit)

    service.change_password(user, "new-secret")

    assert commit_calls["count"] == 1
    assert verify_password("new-secret", user.password_hash) is True
    assert service.authenticate_session(first_token) is None
    assert service.authenticate_session(second_token) is None
