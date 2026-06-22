import importlib
import os
from pathlib import Path
import subprocess
import sys
from http.cookies import SimpleCookie
from types import MethodType

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import PendingRollbackError

from app.config import get_settings
from app.dependencies import get_auth_service
from app.main import create_app
from app.models import SessionRecord, TaskProject, TaskTemplate, User
from app.security import hash_password, verify_password
from app.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def isolated_settings_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("READONLY_TOKEN", raising=False)
    monkeypatch.delenv("AUTH_INITIAL_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_INITIAL_PASSWORD", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SAMESITE", raising=False)
    monkeypatch.delenv("AUTH_SESSION_DAYS", raising=False)
    monkeypatch.delenv("AUTH_ENABLE_REGISTRATION", raising=False)
    monkeypatch.delenv("AUTH_ENABLE_API_TOKENS", raising=False)
    monkeypatch.delenv("AUTH_ENABLE_MCP", raising=False)
    monkeypatch.delenv("APP_ROOT_URL", raising=False)
    monkeypatch.delenv("TESTING", raising=False)


def test_settings_raise_without_initial_credentials_outside_test(monkeypatch, isolated_settings_env):
    monkeypatch.delenv("AUTH_INITIAL_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_INITIAL_PASSWORD", raising=False)
    monkeypatch.setenv("TESTING", "false")

    with pytest.raises(ValueError, match="AUTH_INITIAL_USERNAME and AUTH_INITIAL_PASSWORD are required"):
        get_settings()


def test_settings_require_initial_credentials_outside_test(monkeypatch, isolated_settings_env):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("TESTING", "false")

    settings = get_settings()

    assert settings.auth_initial_username == "reward"
    assert settings.auth_initial_password == "secret-pass"
    assert settings.auth_session_days == 7
    assert settings.auth_cookie_samesite == "lax"


def test_settings_enable_registration_by_default(monkeypatch, isolated_settings_env):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("TESTING", "false")

    settings = get_settings()

    assert settings.auth_enable_registration is True


def test_settings_include_existing_route_contract_fields(monkeypatch, isolated_settings_env):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("TESTING", "false")

    settings = get_settings()

    assert settings.app_root_url == "http://localhost:8088"
    assert settings.auth_enable_api_tokens is True
    assert settings.auth_enable_mcp is True


def test_settings_require_lax_samesite(monkeypatch, isolated_settings_env):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "strict")
    monkeypatch.setenv("TESTING", "false")

    with pytest.raises(ValueError, match="AUTH_COOKIE_SAMESITE must be lax"):
        get_settings()


def test_settings_require_positive_session_days(monkeypatch, isolated_settings_env):
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


def _run_alembic(
    backend_dir: Path,
    env: dict[str, str],
    *args: str,
) -> None:
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
            f"CommandLine(prog='alembic').main(argv={['-c', 'alembic.ini', *args]!r})"
        ),
    ]
    subprocess.run(command, cwd=backend_dir, env=env, check=True)


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


def test_auth_migrations_include_task_reward_user_ownership_columns(tmp_path, monkeypatch):
    database_path = tmp_path / "task_reward_user_ownership.db"
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
        task_project_columns = {column["name"] for column in inspector.get_columns("task_projects")}
        daily_task_columns = {column["name"] for column in inspector.get_columns("daily_tasks")}
        reward_ledger_columns = {column["name"] for column in inspector.get_columns("reward_ledger")}

        assert "user_id" in task_project_columns
        assert "user_id" in daily_task_columns
        assert "user_id" in reward_ledger_columns
    finally:
        engine.dispose()


def test_auth_migration_0005_backfills_existing_task_reward_data_to_bootstrap_user(tmp_path, monkeypatch):
    database_path = tmp_path / "task_reward_user_backfill.db"
    database_url = f"sqlite:///{database_path}"
    backend_dir = Path(__file__).resolve().parents[1]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("TESTING", "true")
    _, env = _build_alembic_subprocess(backend_dir)
    env["DATABASE_URL"] = database_url
    env["AUTH_INITIAL_USERNAME"] = "reward"
    env["AUTH_INITIAL_PASSWORD"] = "secret-pass"
    env["TESTING"] = "true"

    _run_alembic(backend_dir, env, "upgrade", "0004_add_user_profile_and_registration_flag")

    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                INSERT INTO users
                    (username, display_name, email, password_hash, created_at, updated_at, password_changed_at)
                VALUES
                    (:username, :display_name, :email, :password_hash, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
                ,
                {
                    "username": "reward",
                    "display_name": "reward",
                    "email": "reward@local.invalid",
                    "password_hash": hash_password("secret-pass"),
                },
            )
            connection.exec_driver_sql(
                """
                INSERT INTO task_projects
                    (id, name, status, sort_order, created_at, updated_at)
                VALUES
                    (1, 'Legacy Project', 'active', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO task_templates
                    (id, project_id, name, default_estimated_duration_minutes, default_reward_amount, notes, is_active, created_at, updated_at)
                VALUES
                    (1, 1, 'Legacy Template', 30, 12, '', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO daily_tasks
                    (id, date, project_id, task_template_id, name_snapshot, estimated_duration_minutes_snapshot,
                     reward_amount_snapshot, status, actual_duration_minutes, completed_at, created_at, updated_at)
                VALUES
                    (1, '2026-06-20', 1, 1, 'Legacy Template', 30, 12, 'completed', 28, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO reward_ledger
                    (id, entry_type, amount, reason, daily_task_id, created_at)
                VALUES
                    (1, 'earn', 12, 'Legacy Template', 1, CURRENT_TIMESTAMP)
                """
            )
    finally:
        engine.dispose()

    _run_alembic(backend_dir, env, "upgrade", "head")

    engine = create_engine(database_url, future=True)
    try:
        inspector = inspect(engine)
        task_project_user = next(
            column for column in inspector.get_columns("task_projects") if column["name"] == "user_id"
        )
        daily_task_user = next(
            column for column in inspector.get_columns("daily_tasks") if column["name"] == "user_id"
        )
        reward_ledger_user = next(
            column for column in inspector.get_columns("reward_ledger") if column["name"] == "user_id"
        )
        assert task_project_user["nullable"] is False
        assert daily_task_user["nullable"] is False
        assert reward_ledger_user["nullable"] is False

        with engine.connect() as connection:
            row = connection.exec_driver_sql(
                """
                SELECT
                    task_projects.user_id AS project_user_id,
                    daily_tasks.user_id AS task_user_id,
                    reward_ledger.user_id AS ledger_user_id
                FROM task_projects
                JOIN daily_tasks ON daily_tasks.project_id = task_projects.id
                JOIN reward_ledger ON reward_ledger.daily_task_id = daily_tasks.id
                WHERE task_projects.id = 1
                """
            ).mappings().one()

        assert row["project_user_id"] == 1
        assert row["task_user_id"] == 1
        assert row["ledger_user_id"] == 1
    finally:
        engine.dispose()

    monkeypatch.setenv("READONLY_TOKEN", "readonly-test-token")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "reward", "password": "secret-pass"},
        )
        assert login_response.status_code == 200

        private_projects = client.get("/api/task-projects")
        assert private_projects.status_code == 200
        assert private_projects.json() == [
            {
                "id": 1,
                "name": "Legacy Project",
                "status": "active",
                "sort_order": 0,
            }
        ]

        public_projects = client.get(
            "/api/public/projects",
            headers={"Authorization": "Bearer readonly-test-token"},
        )
        assert public_projects.status_code == 200
        assert public_projects.json()["items"] == [
            {
                "id": 1,
                "name": "Legacy Project",
                "status": "active",
                "sort_order": 0,
            }
        ]

        public_summary = client.get(
            "/api/public/summary",
            params={"date": "2026-06-20"},
            headers={"Authorization": "Bearer readonly-test-token"},
        )
        assert public_summary.status_code == 200
        assert public_summary.json() == {
            "readOnly": True,
            "current_balance": 12,
            "today_earned": 12,
        }

    get_settings.cache_clear()


def test_auth_migration_0003_downgrade_backfills_null_expiry(tmp_path, monkeypatch):
    database_path = tmp_path / "auth_access_tokens.db"
    database_url = f"sqlite:///{database_path}"
    backend_dir = Path(__file__).resolve().parents[1]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("TESTING", "true")
    _, env = _build_alembic_subprocess(backend_dir)
    env["DATABASE_URL"] = database_url
    env["AUTH_INITIAL_USERNAME"] = "reward"
    env["AUTH_INITIAL_PASSWORD"] = "secret-pass"
    env["TESTING"] = "true"

    _run_alembic(backend_dir, env, "upgrade", "0003_make_access_token_expiry_nullable")

    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                INSERT INTO users (username, password_hash, created_at, updated_at, password_changed_at)
                VALUES ('reward', 'hash', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO access_tokens
                    (user_id, name, token_type, token_hash, created_at, updated_at, expires_at, last_seen_at)
                VALUES
                    (1, 'No Expiry', 'api', 'token-hash', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, NULL)
                """
            )
    finally:
        engine.dispose()

    _run_alembic(backend_dir, env, "downgrade", "0002_add_auth_tables")

    engine = create_engine(database_url, future=True)
    try:
        inspector = inspect(engine)
        expires_at_column = next(
            column for column in inspector.get_columns("access_tokens") if column["name"] == "expires_at"
        )
        assert expires_at_column["nullable"] is False
    finally:
        engine.dispose()


def test_auth_migration_0004_backfills_existing_users(tmp_path, monkeypatch):
    database_path = tmp_path / "auth_profile_backfill.db"
    database_url = f"sqlite:///{database_path}"
    backend_dir = Path(__file__).resolve().parents[1]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("TESTING", "true")
    _, env = _build_alembic_subprocess(backend_dir)
    env["DATABASE_URL"] = database_url
    env["AUTH_INITIAL_USERNAME"] = "reward"
    env["AUTH_INITIAL_PASSWORD"] = "secret-pass"
    env["TESTING"] = "true"

    _run_alembic(backend_dir, env, "upgrade", "0002_add_auth_tables")

    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                INSERT INTO users (username, password_hash, created_at, updated_at, password_changed_at)
                VALUES ('legacy-user', 'hash', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
    finally:
        engine.dispose()

    _run_alembic(backend_dir, env, "upgrade", "head")

    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT username, display_name, email FROM users WHERE username = 'legacy-user'"
            ).mappings().one()
        assert row["display_name"] == "legacy-user"
        assert row["email"] == "legacy-user@local.invalid"
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
    assert first_user.display_name == "reward admin"
    assert first_user.email == "reward admin@local.invalid"
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
        display_name="reward admin",
        email="reward admin@local.invalid",
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


def test_register_succeeds_and_auto_logs_in(client, db_session):
    cookie_name = get_settings().auth_session_cookie_name

    response = client.post(
        "/api/auth/register",
        json={
            "username": "new-user",
            "display_name": "New User",
            "email": "new-user@example.com",
            "password": "new-secret1",
            "confirm_password": "new-secret1",
            "create_default_workspace": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "new-user"
    assert payload["display_name"] == "New User"
    assert payload["email"] == "new-user@example.com"
    user = db_session.scalar(select(User).where(User.username == "new-user"))
    assert user is not None
    assert verify_password("new-secret1", user.password_hash) is True

    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    cookie = SimpleCookie()
    cookie.load(set_cookie)
    assert cookie[cookie_name].value

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "new-user"


def test_register_rejects_duplicate_username(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "reward",
            "display_name": "Duplicate User",
            "email": "other@example.com",
            "password": "new-secret1",
            "confirm_password": "new-secret1",
            "create_default_workspace": False,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "用户名已存在"}


def test_register_rejects_duplicate_email(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "different-user",
            "display_name": "Duplicate Email",
            "email": "reward@local.invalid",
            "password": "new-secret1",
            "confirm_password": "new-secret1",
            "create_default_workspace": False,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "邮箱已存在"}


def test_register_rejects_when_registration_disabled(client, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLE_REGISTRATION", "false")
    get_settings.cache_clear()

    response = client.post(
        "/api/auth/register",
        json={
            "username": "blocked-user",
            "display_name": "Blocked User",
            "email": "blocked@example.com",
            "password": "blocked123",
            "confirm_password": "blocked123",
            "create_default_workspace": False,
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Registration is disabled"}


@pytest.mark.parametrize(
    "email",
    [
        "missing-at.example.com",
        "double@@example.com",
        "space @example.com",
        "name@example .com",
        "name@\nexample.com",
        "@example.com",
        "name@",
    ],
)
def test_register_rejects_invalid_email_addresses(client, email):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "bad-email-user",
            "display_name": "Bad Email User",
            "email": email,
            "password": "good-pass1",
            "confirm_password": "good-pass1",
            "create_default_workspace": False,
        },
    )

    assert response.status_code == 422


def test_register_creates_default_workspace_only_for_new_user(client, db_session):
    first_response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "display_name": "Alice",
            "email": "alice@example.com",
            "password": "alice-pass1",
            "confirm_password": "alice-pass1",
            "create_default_workspace": True,
        },
    )
    assert first_response.status_code == 200

    first_user = db_session.scalar(select(User).where(User.username == "alice"))
    assert first_user is not None
    first_projects = db_session.scalars(
        select(TaskProject)
        .where(TaskProject.user_id == first_user.id)
        .order_by(TaskProject.sort_order.asc(), TaskProject.id.asc())
    ).all()
    assert [(project.name, project.sort_order) for project in first_projects] == [
        ("学习", 0),
        ("运动", 1),
        ("生活", 2),
    ]

    first_templates = db_session.scalars(
        select(TaskTemplate)
        .join(TaskProject, TaskTemplate.project_id == TaskProject.id)
        .where(TaskProject.user_id == first_user.id)
        .order_by(TaskProject.sort_order.asc(), TaskTemplate.id.asc())
    ).all()
    assert [(template.name, template.default_reward_amount) for template in first_templates] == [
        ("背单词 20 分钟", 8),
        ("深度阅读 30 分钟", 12),
        ("力量训练 30 分钟", 15),
        ("拉伸 15 分钟", 6),
        ("整理房间 20 分钟", 10),
    ]

    second_response = client.post(
        "/api/auth/register",
        json={
            "username": "bob",
            "display_name": "Bob",
            "email": "bob@example.com",
            "password": "bob-pass123",
            "confirm_password": "bob-pass123",
            "create_default_workspace": True,
        },
    )
    assert second_response.status_code == 200

    second_user = db_session.scalar(select(User).where(User.username == "bob"))
    assert second_user is not None
    second_projects = db_session.scalars(
        select(TaskProject)
        .where(TaskProject.user_id == second_user.id)
        .order_by(TaskProject.sort_order.asc(), TaskProject.id.asc())
    ).all()
    assert [(project.name, project.sort_order) for project in second_projects] == [
        ("学习", 0),
        ("运动", 1),
        ("生活", 2),
    ]

    assert {project.user_id for project in first_projects} == {first_user.id}
    assert {project.user_id for project in second_projects} == {second_user.id}
    assert db_session.scalar(
        select(TaskProject)
        .where(TaskProject.user_id == first_user.id, TaskProject.name == "学习")
    ) is not None
    assert db_session.scalar(
        select(TaskProject)
        .where(TaskProject.user_id == second_user.id, TaskProject.name == "学习")
    ) is not None


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
    db_session.add(
        User(
            username="second-user",
            display_name="second-user",
            email="second-user@local.invalid",
            password_hash="hash",
        )
    )
    db_session.commit()

    from scripts.reset_password import reset_password

    with pytest.raises(ValueError, match="exactly one local user"):
        reset_password(db_session, "brand-new-pass")
