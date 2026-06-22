from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import Boolean, Column, Date, DateTime, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DailyTask, RewardLedger, TaskProject, User
from app.services.auth_service import AuthService
from app.services.task_reward_service import TaskRewardService


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _create_legacy_source_database(database_path: Path) -> str:
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url, future=True)
    metadata = MetaData()

    task_projects = Table(
        "task_projects",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("name", String(200), nullable=False),
        Column("status", String(20), nullable=False),
        Column("sort_order", Integer, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    task_templates = Table(
        "task_templates",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("project_id", Integer, nullable=False),
        Column("name", String(200), nullable=False),
        Column("default_estimated_duration_minutes", Integer, nullable=False),
        Column("default_reward_amount", Integer, nullable=False),
        Column("notes", Text, nullable=False),
        Column("is_active", Boolean, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    daily_tasks = Table(
        "daily_tasks",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("date", Date, nullable=False),
        Column("project_id", Integer, nullable=False),
        Column("task_template_id", Integer, nullable=False),
        Column("name_snapshot", String(200), nullable=False),
        Column("estimated_duration_minutes_snapshot", Integer, nullable=False),
        Column("reward_amount_snapshot", Integer, nullable=False),
        Column("status", String(20), nullable=False),
        Column("actual_duration_minutes", Integer, nullable=True),
        Column("completed_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    reward_ledger = Table(
        "reward_ledger",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("entry_type", String(20), nullable=False),
        Column("amount", Integer, nullable=False),
        Column("reason", Text, nullable=False),
        Column("daily_task_id", Integer, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    created_at = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
    task_created_at = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)
    task_completed_at = datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)

    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            connection.execute(
                task_projects.insert(),
                [
                    {
                        "id": 1,
                        "name": "Legacy Work",
                        "status": "active",
                        "sort_order": 7,
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                ],
            )
            connection.execute(
                task_templates.insert(),
                [
                    {
                        "id": 1,
                        "project_id": 1,
                        "name": "Legacy Template",
                        "default_estimated_duration_minutes": 45,
                        "default_reward_amount": 18,
                        "notes": "migrated from lifeboard",
                        "is_active": True,
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                ],
            )
            connection.execute(
                daily_tasks.insert(),
                [
                    {
                        "id": 1,
                        "date": date(2026, 6, 2),
                        "project_id": 1,
                        "task_template_id": 1,
                        "name_snapshot": "Legacy Template",
                        "estimated_duration_minutes_snapshot": 50,
                        "reward_amount_snapshot": 20,
                        "status": "completed",
                        "actual_duration_minutes": 48,
                        "completed_at": task_completed_at,
                        "created_at": task_created_at,
                        "updated_at": task_completed_at,
                    }
                ],
            )
            connection.execute(
                reward_ledger.insert(),
                [
                    {
                        "id": 1,
                        "entry_type": "earn",
                        "amount": 20,
                        "reason": "Legacy Template",
                        "daily_task_id": 1,
                        "created_at": task_completed_at,
                    }
                ],
            )
    finally:
        engine.dispose()

    return database_url


def _seed_user_workspace(session: Session, user: User, project_name: str) -> None:
    service = TaskRewardService(session)
    project = service.create_project(name=project_name, user=user)
    template = service.create_task_template(
        user=user,
        project_id=project.id,
        name=f"{project_name} Template",
        default_estimated_duration_minutes=30,
        default_reward_amount=10,
        notes="existing data",
        is_active=True,
    )
    task = service.create_daily_task(
        user=user,
        task_template_id=template.id,
        date=date(2026, 6, 10),
        estimated_duration_minutes=30,
        reward_amount=10,
    )
    service.complete_daily_task(user=user, task_id=task.id, actual_duration_minutes=25)


def test_migrate_from_lifeboard_imports_into_explicit_target_user_without_touching_others(
    db_session,
    tmp_path,
) -> None:
    source_db_url = _create_legacy_source_database(tmp_path / "lifeboard_explicit.db")
    auth_service = AuthService(db_session)
    reward_user = auth_service.ensure_initial_user("reward", "super-secret")
    alice_user = auth_service.ensure_initial_user("alice", "alice-pass123")

    _seed_user_workspace(db_session, reward_user, "Reward Existing")
    _seed_user_workspace(db_session, alice_user, "Alice Existing")

    from scripts.migrate_from_lifeboard import migrate_from_lifeboard

    migrated = migrate_from_lifeboard(
        source_db_url=source_db_url,
        target_username="alice",
        target_engine=db_session.get_bind(),
    )

    assert migrated == {
        "task_projects": 1,
        "task_templates": 1,
        "daily_tasks": 1,
        "reward_ledger": 1,
    }

    db_session.expire_all()

    reward_projects = db_session.query(TaskProject).filter(TaskProject.user_id == reward_user.id).all()
    alice_projects = db_session.query(TaskProject).filter(TaskProject.user_id == alice_user.id).all()
    alice_tasks = db_session.query(DailyTask).filter(DailyTask.user_id == alice_user.id).all()
    alice_ledger = db_session.query(RewardLedger).filter(RewardLedger.user_id == alice_user.id).all()

    assert [project.name for project in reward_projects] == ["Reward Existing"]
    assert [project.name for project in alice_projects] == ["Legacy Work"]
    assert [task.name_snapshot for task in alice_tasks] == ["Legacy Template"]
    assert [entry.reason for entry in alice_ledger] == ["Legacy Template"]
    assert all(project.user_id == alice_user.id for project in alice_projects)
    assert all(task.user_id == alice_user.id for task in alice_tasks)
    assert all(entry.user_id == alice_user.id for entry in alice_ledger)


def test_migrate_from_lifeboard_defaults_to_bootstrap_user_when_target_is_omitted(
    db_session,
    tmp_path,
) -> None:
    source_db_url = _create_legacy_source_database(tmp_path / "lifeboard_default.db")
    auth_service = AuthService(db_session)
    reward_user = auth_service.ensure_initial_user("reward", "super-secret")
    bob_user = auth_service.ensure_initial_user("bob", "bob-pass123")

    _seed_user_workspace(db_session, reward_user, "Reward Existing")
    _seed_user_workspace(db_session, bob_user, "Bob Existing")

    from scripts.migrate_from_lifeboard import migrate_from_lifeboard

    migrated = migrate_from_lifeboard(
        source_db_url=source_db_url,
        target_engine=db_session.get_bind(),
    )

    assert migrated["task_projects"] == 1

    db_session.expire_all()

    reward_projects = db_session.query(TaskProject).filter(TaskProject.user_id == reward_user.id).all()
    bob_projects = db_session.query(TaskProject).filter(TaskProject.user_id == bob_user.id).all()
    reward_tasks = db_session.query(DailyTask).filter(DailyTask.user_id == reward_user.id).all()

    assert [project.name for project in reward_projects] == ["Legacy Work"]
    assert [project.name for project in bob_projects] == ["Bob Existing"]
    assert [task.name_snapshot for task in reward_tasks] == ["Legacy Template"]


def test_migrate_from_lifeboard_requires_target_username_for_non_bootstrap_multi_user_db(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    source_db_url = _create_legacy_source_database(tmp_path / "lifeboard_ambiguous.db")
    auth_service = AuthService(db_session)
    auth_service.ensure_initial_user("alice", "alice-pass123")
    auth_service.ensure_initial_user("bob", "bob-pass123")
    monkeypatch.delenv("AUTH_INITIAL_USERNAME", raising=False)

    from scripts.migrate_from_lifeboard import migrate_from_lifeboard

    with pytest.raises(ValueError, match="multiple users; pass --target-username"):
        migrate_from_lifeboard(
            source_db_url=source_db_url,
            target_engine=db_session.get_bind(),
        )
