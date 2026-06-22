import importlib
import os
from pathlib import Path
import subprocess
import sys
from http.cookies import SimpleCookie
from types import MethodType

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import PendingRollbackError

from app.config import get_settings
from app.dependencies import get_auth_service
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


def test_settings_enable_registration_by_default(monkeypatch):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("TESTING", "false")

    settings = get_settings()

    assert settings.auth_enable_registration is True


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


def test_auth_migrations_include_profile_columns(tmp_path, monkeypatch):
    database_path = tmp_path / "auth_profile_columns.db"
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
        columns = {column["name"]: column for column in inspector.get_columns("users")}
        assert "display_name" in columns
        assert columns["display_name"]["nullable"] is False
        assert "email" in columns
        assert columns["email"]["nullable"] is False

        unique_constraints = {
            constraint["name"]: constraint
            for constraint in inspector.get_unique_constraints("users")
            if constraint["name"]
        }
        assert "uq_users_email" in unique_constraints
        assert unique_constraints["uq_users_email"]["column_names"] == ["email"]
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


def test_login_sets_cookie_and_returns_user(client):
    cookie_name = get_settings().auth_session_cookie_name
    response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["username"] == "reward"
    assert payload["display_name"] == "reward"
    assert payload["email"] == "reward@local.invalid"
    assert payload["last_login_at"] is not None
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    cookie = SimpleCookie()
    cookie.load(set_cookie)
    morsel = cookie[cookie_name]
    assert morsel.value
    assert morsel["httponly"]
    assert morsel["path"] == "/"
    assert morsel["samesite"].lower() == "lax"


def test_task_projects_requires_login(client):
    response = client.get("/api/task-projects")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_protected_me_requires_valid_cookie(client):
    unauthenticated = client.get("/api/auth/me")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {"detail": "Authentication required"}

    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )

    assert login_response.status_code == 200

    authenticated = client.get("/api/auth/me")

    assert authenticated.status_code == 200
    payload = authenticated.json()
    assert payload["id"] == 1
    assert payload["username"] == "reward"
    assert payload["display_name"] == "reward"
    assert payload["email"] == "reward@local.invalid"
    assert payload["last_login_at"] is not None


def test_change_password_rotates_sessions(client):
    cookie_name = get_settings().auth_session_cookie_name
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )

    assert login_response.status_code == 200
    original_cookie_value = client.cookies.get(cookie_name)
    assert original_cookie_value

    invalid_change_response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "super-secret",
            "new_password": "short",
            "confirm_new_password": "short",
        },
    )

    assert invalid_change_response.status_code == 422

    mismatch_change_response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "super-secret",
            "new_password": "new-secret-pass",
            "confirm_new_password": "different-pass",
        },
    )

    assert mismatch_change_response.status_code == 400
    assert mismatch_change_response.json() == {"detail": "New passwords do not match"}

    change_response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "super-secret",
            "new_password": "new-secret-pass",
            "confirm_new_password": "new-secret-pass",
        },
    )

    assert change_response.status_code == 200
    payload = change_response.json()
    assert payload["id"] == 1
    assert payload["username"] == "reward"
    assert payload["last_login_at"] is not None
    set_cookie = change_response.headers.get("set-cookie")
    assert set_cookie is not None
    cookie = SimpleCookie()
    cookie.load(set_cookie)
    rotated_cookie = cookie[cookie_name].value
    assert rotated_cookie
    assert rotated_cookie != original_cookie_value

    stale_cookie_client = client.__class__(client.app)
    stale_cookie_client.cookies.set(cookie_name, original_cookie_value)
    stale_session_response = stale_cookie_client.get("/api/auth/me")
    assert stale_session_response.status_code == 401
    assert stale_session_response.json() == {"detail": "Authentication required"}

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["id"] == 1
    assert me_payload["username"] == "reward"
    assert me_payload["last_login_at"] is not None

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 204
    logout_set_cookie = logout_response.headers.get("set-cookie")
    assert logout_set_cookie is not None
    cleared_cookie = SimpleCookie()
    cleared_cookie.load(logout_set_cookie)
    assert cleared_cookie[cookie_name].value == ""

    stale_session_response = client.get("/api/auth/me")
    assert stale_session_response.status_code == 401
    assert stale_session_response.json() == {"detail": "Authentication required"}

    old_password_login = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert old_password_login.status_code == 401
    assert old_password_login.json() == {"detail": "Invalid username or password"}

    new_password_login = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "new-secret-pass"},
    )
    assert new_password_login.status_code == 200
    new_login_payload = new_password_login.json()
    assert new_login_payload["id"] == 1
    assert new_login_payload["username"] == "reward"
    assert new_login_payload["last_login_at"] is not None


def test_logout_clears_cookie_even_when_session_cookie_is_invalid(client):
    cookie_name = get_settings().auth_session_cookie_name
    client.cookies.set(cookie_name, "invalid-session-token")

    logout_response = client.post("/api/auth/logout")

    assert logout_response.status_code == 204
    logout_set_cookie = logout_response.headers.get("set-cookie")
    assert logout_set_cookie is not None
    cleared_cookie = SimpleCookie()
    cleared_cookie.load(logout_set_cookie)
    assert cleared_cookie[cookie_name].value == ""
    assert cleared_cookie[cookie_name]["path"] == "/"


def test_logout_clears_cookie_even_when_session_delete_errors(client, db_session, monkeypatch):
    cookie_name = get_settings().auth_session_cookie_name

    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200

    test_service = AuthService(db_session)
    client.app.dependency_overrides[get_auth_service] = lambda: test_service

    original_commit = db_session.commit
    original_rollback = db_session.rollback
    rollback_calls = {"count": 0}
    commit_calls = {"count": 0}
    session_failed = {"value": False}

    def failing_commit():
        commit_calls["count"] += 1
        if session_failed["value"]:
            raise PendingRollbackError("session is in failed state")
        if commit_calls["count"] == 1:
            session_failed["value"] = True
            raise RuntimeError("delete failed")
        original_commit()

    def tracking_rollback():
        rollback_calls["count"] += 1
        session_failed["value"] = False
        original_rollback()

    monkeypatch.setattr(db_session, "commit", failing_commit)
    monkeypatch.setattr(db_session, "rollback", tracking_rollback)

    logout_response = client.post("/api/auth/logout")

    assert logout_response.status_code == 204
    assert commit_calls["count"] == 1
    assert rollback_calls["count"] == 1
    logout_set_cookie = logout_response.headers.get("set-cookie")
    assert logout_set_cookie is not None
    cleared_cookie = SimpleCookie()
    cleared_cookie.load(logout_set_cookie)
    assert cleared_cookie[cookie_name].value == ""
    assert cleared_cookie[cookie_name]["path"] == "/"

    relogin_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert relogin_response.status_code == 200

    client.app.dependency_overrides.pop(get_auth_service, None)

    relogin_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert relogin_response.status_code == 200


def test_change_password_is_atomic_when_new_session_creation_fails(client, db_session, monkeypatch):
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200

    original_commit = db_session.commit
    original_rollback = db_session.rollback
    commit_calls = {"count": 0}
    rollback_calls = {"count": 0}

    def failing_commit():
        commit_calls["count"] += 1
        if commit_calls["count"] == 2:
            raise RuntimeError("commit failed")
        original_commit()

    def tracking_rollback():
        rollback_calls["count"] += 1
        original_rollback()

    monkeypatch.setattr(db_session, "commit", failing_commit)
    monkeypatch.setattr(db_session, "rollback", tracking_rollback)

    with client.__class__(client.app, raise_server_exceptions=False) as failing_client:
        failing_client.cookies.update(client.cookies)
        change_response = failing_client.post(
            "/api/auth/change-password",
            json={
                "current_password": "super-secret",
                "new_password": "new-secret-pass",
                "confirm_new_password": "new-secret-pass",
            },
        )

    assert change_response.status_code == 500
    assert commit_calls["count"] >= 2
    assert rollback_calls["count"] == 1

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200

    old_password_login = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert old_password_login.status_code == 200

    new_password_login = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "new-secret-pass"},
    )
    assert new_password_login.status_code == 401


def test_reset_password_clears_existing_sessions(db_session):
    service = AuthService(db_session)
    user = service.ensure_initial_user("reward", "super-secret")
    raw_token, _ = service.create_session(user)

    from scripts.reset_password import reset_password

    reset_password(db_session, "brand-new-pass")

    assert service.authenticate_session(raw_token) is None
    assert service.verify_credentials("reward", "brand-new-pass") is not None


def test_reset_password_rejects_short_password(db_session):
    service = AuthService(db_session)
    service.ensure_initial_user("reward", "super-secret")

    from scripts.reset_password import reset_password

    with pytest.raises(ValueError, match="at least 8 characters"):
        reset_password(db_session, "short")


def test_reset_password_requires_exactly_one_user(db_session):
    service = AuthService(db_session)
    service.ensure_initial_user("reward", "super-secret")
    db_session.add(User(username="second-user", password_hash="hash"))
    db_session.commit()

    from scripts.reset_password import reset_password

    with pytest.raises(ValueError, match="exactly one local user"):
        reset_password(db_session, "brand-new-pass")
