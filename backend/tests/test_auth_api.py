import importlib
import datetime
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
from app.services.task_reward_service import TaskRewardService


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_task_reward_data(db_session):
    service = TaskRewardService(db_session)
    project = service.create_project(name="健身")
    template = service.create_task_template(
        project_id=project.id,
        name="拉伸 15 分钟",
        default_estimated_duration_minutes=15,
        default_reward_amount=800,
        notes="晨间拉伸",
        is_active=True,
    )
    task = service.create_daily_task(
        task_template_id=template.id,
        date=datetime.date(2026, 6, 20),
        estimated_duration_minutes=20,
        reward_amount=1000,
    )
    service.complete_daily_task(task.id, actual_duration_minutes=18)
    return service, project, template, task


def test_settings_raise_without_initial_credentials_outside_test(monkeypatch):
    monkeypatch.delenv("AUTH_INITIAL_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_INITIAL_PASSWORD", raising=False)
    monkeypatch.delenv("APP_BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("APP_BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.setenv("TESTING", "false")

    with pytest.raises(ValueError, match="AUTH_INITIAL_USERNAME and AUTH_INITIAL_PASSWORD are required"):
        get_settings()


def test_settings_fallback_to_legacy_basic_auth_credentials(monkeypatch):
    monkeypatch.delenv("AUTH_INITIAL_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_INITIAL_PASSWORD", raising=False)
    monkeypatch.setenv("APP_BASIC_AUTH_USER", "legacy-user")
    monkeypatch.setenv("APP_BASIC_AUTH_PASSWORD", "legacy-pass")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("TESTING", "false")

    settings = get_settings()

    assert settings.auth_initial_username == "legacy-user"
    assert settings.auth_initial_password == "legacy-pass"


def test_settings_prefer_new_auth_credentials_over_legacy(monkeypatch):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("APP_BASIC_AUTH_USER", "legacy-user")
    monkeypatch.setenv("APP_BASIC_AUTH_PASSWORD", "legacy-pass")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("TESTING", "false")

    settings = get_settings()

    assert settings.auth_initial_username == "reward"
    assert settings.auth_initial_password == "secret-pass"


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
    assert settings.auth_enable_api_tokens is True
    assert settings.auth_enable_mcp is True


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


def _login(client, username: str = "reward", password: str = "super-secret"):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response


def test_account_profile_sessions_and_api_tokens(client):
    _login(client)

    profile_response = client.get("/api/account/profile")

    assert profile_response.status_code == 200
    profile_payload = profile_response.json()
    assert profile_payload["id"] == 1
    assert profile_payload["username"] == "reward"
    assert profile_payload["created_at"] is not None
    assert profile_payload["password_changed_at"] is not None
    assert profile_payload["last_login_at"] is not None
    assert profile_payload["api_token_enabled"] is True
    assert profile_payload["mcp_enabled"] is True

    sessions_response = client.get("/api/account/sessions")

    assert sessions_response.status_code == 200
    sessions_payload = sessions_response.json()
    assert len(sessions_payload["items"]) == 1
    assert sessions_payload["items"][0]["is_current"] is True
    assert sessions_payload["items"][0]["expires_at"] is not None
    assert sessions_payload["items"][0]["last_seen_at"] is not None

    token_create_response = client.post(
        "/api/account/tokens",
        json={
            "name": "Codex API",
            "token_type": "api",
            "password": "super-secret",
            "expires_in_days": 30,
        },
    )

    assert token_create_response.status_code == 201
    token_payload = token_create_response.json()
    assert token_payload["name"] == "Codex API"
    assert token_payload["token_type"] == "api"
    assert token_payload["token"]
    assert token_payload["api_base_url"].endswith("/api")
    assert token_payload["expires_at"] is not None

    token_list_response = client.get("/api/account/tokens")

    assert token_list_response.status_code == 200
    token_list_payload = token_list_response.json()
    assert len(token_list_payload["items"]) == 1
    assert token_list_payload["items"][0]["id"] == token_payload["id"]
    assert token_list_payload["items"][0]["name"] == "Codex API"
    assert token_list_payload["items"][0]["token_type"] == "api"
    assert token_list_payload["items"][0]["last_seen_at"] is None

    bearer_client = client.__class__(client.app)
    bearer_response = bearer_client.get(
        "/api/task-projects",
        headers={"Authorization": f"Bearer {token_payload['token']}"},
    )

    assert bearer_response.status_code == 200
    assert bearer_response.json() == []

    refreshed_token_list_response = client.get("/api/account/tokens")
    refreshed_items = refreshed_token_list_response.json()["items"]
    assert refreshed_items[0]["last_seen_at"] is not None

    revoke_response = client.delete(f"/api/account/tokens/{token_payload['id']}")

    assert revoke_response.status_code == 204

    revoked_bearer_response = bearer_client.get(
        "/api/task-projects",
        headers={"Authorization": f"Bearer {token_payload['token']}"},
    )
    assert revoked_bearer_response.status_code == 401
    assert revoked_bearer_response.json() == {"detail": "Authentication required"}


def test_account_tokens_support_custom_seconds_and_no_expiration(client):
    _login(client)

    custom_expiry_response = client.post(
        "/api/account/tokens",
        json={
            "name": "Short API",
            "token_type": "api",
            "password": "super-secret",
            "expires_in_seconds": 3600,
        },
    )

    assert custom_expiry_response.status_code == 201
    custom_payload = custom_expiry_response.json()
    assert custom_payload["expires_at"] is not None

    created_at = datetime.datetime.fromisoformat(
        custom_payload["created_at"].replace("Z", "+00:00")
    )
    expires_at = datetime.datetime.fromisoformat(
        custom_payload["expires_at"].replace("Z", "+00:00")
    )
    assert int((expires_at - created_at).total_seconds()) in range(3599, 3602)

    no_expiry_response = client.post(
        "/api/account/tokens",
        json={
            "name": "Never Expire MCP",
            "token_type": "mcp",
            "password": "super-secret",
            "expires_in_seconds": 0,
        },
    )

    assert no_expiry_response.status_code == 201
    no_expiry_payload = no_expiry_response.json()
    assert no_expiry_payload["expires_at"] is None

    token_list_response = client.get("/api/account/tokens")
    assert token_list_response.status_code == 200
    items = token_list_response.json()["items"]
    assert items[0]["name"] == "Never Expire MCP"
    assert items[0]["expires_at"] is None
    assert items[1]["name"] == "Short API"
    assert items[1]["expires_at"] is not None


def test_account_profile_and_token_generation_respect_capability_flags(client, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLE_API_TOKENS", "false")
    monkeypatch.setenv("AUTH_ENABLE_MCP", "false")
    get_settings.cache_clear()

    _login(client)

    profile_response = client.get("/api/account/profile")

    assert profile_response.status_code == 200
    assert profile_response.json()["api_token_enabled"] is False
    assert profile_response.json()["mcp_enabled"] is False

    api_token_response = client.post(
        "/api/account/tokens",
        json={
            "name": "Disabled API",
            "token_type": "api",
            "password": "super-secret",
        },
    )

    assert api_token_response.status_code == 403
    assert api_token_response.json() == {"detail": "api token is not enabled"}

    mcp_token_response = client.post(
        "/api/account/tokens",
        json={
            "name": "Disabled MCP",
            "token_type": "mcp",
            "password": "super-secret",
        },
    )

    assert mcp_token_response.status_code == 400
    assert mcp_token_response.json() == {"detail": "mcp server is not enabled"}


def test_account_can_revoke_another_session(client):
    _login(client)

    other_client = client.__class__(client.app)
    _login(other_client)

    sessions_response = client.get("/api/account/sessions")

    assert sessions_response.status_code == 200
    sessions_payload = sessions_response.json()["items"]
    assert len(sessions_payload) == 2

    other_session = next(item for item in sessions_payload if not item["is_current"])

    revoke_response = client.delete(f"/api/account/sessions/{other_session['id']}")

    assert revoke_response.status_code == 204

    revoked_session_response = other_client.get("/api/auth/me")
    assert revoked_session_response.status_code == 401
    assert revoked_session_response.json() == {"detail": "Authentication required"}


def test_account_can_revoke_all_other_sessions(client):
    _login(client)

    other_client = client.__class__(client.app)
    _login(other_client)

    third_client = client.__class__(client.app)
    _login(third_client)

    sessions_response = client.get("/api/account/sessions")
    assert sessions_response.status_code == 200
    assert len(sessions_response.json()["items"]) == 3

    revoke_response = client.delete("/api/account/sessions")

    assert revoke_response.status_code == 204

    current_session_response = client.get("/api/auth/me")
    assert current_session_response.status_code == 200

    revoked_other_response = other_client.get("/api/auth/me")
    assert revoked_other_response.status_code == 401
    assert revoked_other_response.json() == {"detail": "Authentication required"}

    revoked_third_response = third_client.get("/api/auth/me")
    assert revoked_third_response.status_code == 401
    assert revoked_third_response.json() == {"detail": "Authentication required"}


def test_mcp_endpoint_respects_disabled_capability(client, monkeypatch):
    _login(client)

    token_create_response = client.post(
        "/api/account/tokens",
        json={
            "name": "Claude Desktop",
            "token_type": "mcp",
            "password": "super-secret",
        },
    )

    assert token_create_response.status_code == 201
    token_payload = token_create_response.json()

    monkeypatch.setenv("AUTH_ENABLE_MCP", "false")
    get_settings.cache_clear()

    mcp_response = client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {token_payload['token']}",
            "MCP-Protocol-Version": "2025-06-18",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "test", "version": "1.0.0"},
            },
        },
    )

    assert mcp_response.status_code == 400
    assert mcp_response.json() == {"detail": "mcp server is not enabled"}


def test_mcp_token_supports_initialize_list_and_call(client, db_session):
    _seed_task_reward_data(db_session)
    _login(client)

    token_create_response = client.post(
        "/api/account/tokens",
        json={
            "name": "Claude Desktop",
            "token_type": "mcp",
            "password": "super-secret",
        },
    )

    assert token_create_response.status_code == 201
    token_payload = token_create_response.json()
    assert token_payload["token_type"] == "mcp"
    assert token_payload["mcp_url"].endswith("/mcp")

    headers = {
        "Authorization": f"Bearer {token_payload['token']}",
        "MCP-Protocol-Version": "2025-06-18",
    }

    initialize_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "pytest", "version": "1.0.0"},
            },
        },
    )

    assert initialize_response.status_code == 200
    initialize_payload = initialize_response.json()
    assert initialize_payload["jsonrpc"] == "2.0"
    assert initialize_payload["id"] == 1
    assert initialize_payload["result"]["protocolVersion"] == "2025-06-18"
    assert initialize_payload["result"]["serverInfo"]["name"] == "reward-todo-mcp"

    tools_response = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )

    assert tools_response.status_code == 200
    tools_payload = tools_response.json()
    tool_names = {tool["name"] for tool in tools_payload["result"]["tools"]}
    assert "get_reward_summary" in tool_names
    assert "list_task_projects" in tool_names
    assert "list_task_templates" in tool_names
    assert "list_daily_tasks" in tool_names
    assert "list_reward_ledger" in tool_names
    assert "create_project" in tool_names
    assert "update_project" in tool_names
    assert "create_task_template" in tool_names
    assert "update_task_template" in tool_names
    assert "create_daily_task" in tool_names
    assert "complete_daily_task" in tool_names
    assert "reopen_daily_task" in tool_names
    assert "spend_reward" in tool_names

    call_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_reward_summary",
                "arguments": {"date": "2026-06-20"},
            },
        },
    )

    assert call_response.status_code == 200
    call_payload = call_response.json()
    assert call_payload["result"]["structuredContent"] == {
        "current_balance": 1000,
        "today_earned": 1000,
    }
    assert call_payload["result"]["content"][0]["type"] == "text"

    create_project_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "create_project",
                "arguments": {"name": "写作"},
            },
        },
    )

    assert create_project_response.status_code == 200
    create_project_payload = create_project_response.json()
    assert create_project_payload["result"]["structuredContent"]["name"] == "写作"
    project_id = create_project_payload["result"]["structuredContent"]["id"]

    update_project_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 41,
            "method": "tools/call",
            "params": {
                "name": "update_project",
                "arguments": {"project_id": project_id, "name": "深度写作", "sort_order": 3},
            },
        },
    )

    assert update_project_response.status_code == 200
    update_project_payload = update_project_response.json()
    assert update_project_payload["result"]["structuredContent"]["name"] == "深度写作"
    assert update_project_payload["result"]["structuredContent"]["sort_order"] == 3

    list_templates_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "list_task_templates",
                "arguments": {"project_id": 1},
            },
        },
    )

    assert list_templates_response.status_code == 200
    list_templates_payload = list_templates_response.json()
    assert list_templates_payload["result"]["structuredContent"][0]["name"] == "拉伸 15 分钟"

    create_template_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "create_task_template",
                "arguments": {
                    "project_id": project_id,
                    "name": "写作 45 分钟",
                    "default_estimated_duration_minutes": 45,
                    "default_reward_amount": 1600,
                    "notes": "深度写作",
                    "is_active": True,
                },
            },
        },
    )

    assert create_template_response.status_code == 200
    create_template_payload = create_template_response.json()
    created_template_id = create_template_payload["result"]["structuredContent"]["id"]
    assert create_template_payload["result"]["structuredContent"]["name"] == "写作 45 分钟"

    update_template_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 61,
            "method": "tools/call",
            "params": {
                "name": "update_task_template",
                "arguments": {
                    "template_id": created_template_id,
                    "name": "深度写作 50 分钟",
                    "default_estimated_duration_minutes": 50,
                    "default_reward_amount": 1800,
                    "notes": "长时段专注",
                    "is_active": True,
                },
            },
        },
    )

    assert update_template_response.status_code == 200
    update_template_payload = update_template_response.json()
    assert update_template_payload["result"]["structuredContent"]["name"] == "深度写作 50 分钟"
    assert (
        update_template_payload["result"]["structuredContent"]["default_estimated_duration_minutes"]
        == 50
    )
    assert update_template_payload["result"]["structuredContent"]["is_active"] is True

    create_task_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "create_daily_task",
                "arguments": {
                    "task_template_id": created_template_id,
                    "date": "2026-06-21",
                    "estimated_duration_minutes": 45,
                    "reward_amount": 1200,
                },
            },
        },
    )

    assert create_task_response.status_code == 200
    create_task_payload = create_task_response.json()
    assert create_task_payload["result"]["structuredContent"]["date"] == "2026-06-21"
    assert create_task_payload["result"]["structuredContent"]["reward_amount_snapshot"] == 1200
    created_task_id = create_task_payload["result"]["structuredContent"]["id"]

    complete_task_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "complete_daily_task",
                "arguments": {
                    "task_id": created_task_id,
                    "actual_duration_minutes": 40,
                },
            },
        },
    )

    assert complete_task_response.status_code == 200
    complete_task_payload = complete_task_response.json()
    assert complete_task_payload["result"]["structuredContent"]["status"] == "completed"
    assert complete_task_payload["result"]["structuredContent"]["actual_duration_minutes"] == 40

    reopen_task_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 81,
            "method": "tools/call",
            "params": {
                "name": "reopen_daily_task",
                "arguments": {"task_id": created_task_id},
            },
        },
    )

    assert reopen_task_response.status_code == 200
    reopen_task_payload = reopen_task_response.json()
    assert reopen_task_payload["result"]["structuredContent"]["status"] == "pending"
    assert reopen_task_payload["result"]["structuredContent"]["actual_duration_minutes"] is None

    deactivate_template_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 82,
            "method": "tools/call",
            "params": {
                "name": "update_task_template",
                "arguments": {"template_id": created_template_id, "is_active": False},
            },
        },
    )

    assert deactivate_template_response.status_code == 200
    deactivate_template_payload = deactivate_template_response.json()
    assert deactivate_template_payload["result"]["structuredContent"]["is_active"] is False

    reward_ledger_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "list_reward_ledger",
                "arguments": {"limit": 5},
            },
        },
    )

    assert reward_ledger_response.status_code == 200
    ledger_payload = reward_ledger_response.json()
    ledger_entry_types = {
        item["entry_type"] for item in ledger_payload["result"]["structuredContent"]
    }
    assert "adjust" in ledger_entry_types
    assert "earn" in ledger_entry_types

    spend_reward_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "spend_reward",
                "arguments": {"amount": 500, "reason": "咖啡奖励"},
            },
        },
    )

    assert spend_reward_response.status_code == 200
    spend_reward_payload = spend_reward_response.json()
    assert spend_reward_payload["result"]["structuredContent"]["entry_type"] == "spend"
    assert spend_reward_payload["result"]["structuredContent"]["amount"] == -500

    list_projects_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "list_task_projects",
                "arguments": {},
            },
        },
    )

    assert list_projects_response.status_code == 200
    projects_payload = list_projects_response.json()
    project_names = {item["name"] for item in projects_payload["result"]["structuredContent"]}
    assert "健身" in project_names
    assert "深度写作" in project_names
    assert project_id in {item["id"] for item in projects_payload["result"]["structuredContent"]}


def test_mcp_token_supports_resources_list_and_read(client, db_session):
    _seed_task_reward_data(db_session)
    _login(client)

    token_create_response = client.post(
        "/api/account/tokens",
        json={
            "name": "Claude Desktop",
            "token_type": "mcp",
            "password": "super-secret",
        },
    )

    assert token_create_response.status_code == 201
    token_payload = token_create_response.json()

    headers = {
        "Authorization": f"Bearer {token_payload['token']}",
        "MCP-Protocol-Version": "2025-06-18",
    }

    resources_response = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 8, "method": "resources/list", "params": {}},
    )

    assert resources_response.status_code == 200
    resources_payload = resources_response.json()
    resource_uris = {resource["uri"] for resource in resources_payload["result"]["resources"]}
    assert "reward-todo://projects" in resource_uris
    assert "reward-todo://daily-tasks/today" in resource_uris
    assert "reward-todo://reward-summary/today" in resource_uris
    assert "reward-todo://reward-ledger/recent" in resource_uris
    assert "reward-todo://account/profile" in resource_uris

    read_projects_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 9,
            "method": "resources/read",
            "params": {"uri": "reward-todo://projects"},
        },
    )

    assert read_projects_response.status_code == 200
    read_projects_payload = read_projects_response.json()
    assert read_projects_payload["result"]["contents"][0]["uri"] == "reward-todo://projects"
    assert '"name": "健身"' in read_projects_payload["result"]["contents"][0]["text"]

    read_summary_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "resources/read",
            "params": {"uri": "reward-todo://reward-summary/today"},
        },
    )

    assert read_summary_response.status_code == 200
    read_summary_payload = read_summary_response.json()
    assert '"current_balance": 1000' in read_summary_payload["result"]["contents"][0]["text"]

    read_unknown_response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "resources/read",
            "params": {"uri": "reward-todo://unknown"},
        },
    )

    assert read_unknown_response.status_code == 200
    assert read_unknown_response.json()["error"]["code"] == -32601
