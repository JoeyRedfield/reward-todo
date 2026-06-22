import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import MetaData, Table, create_engine, delete, func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.database import get_engine, get_session_factory, init_db
from app.models import DailyTask, RewardLedger, TaskProject, TaskTemplate, User
from app.security import normalize_username


TABLES = [
    "task_projects",
    "task_templates",
    "daily_tasks",
    "reward_ledger",
]


def normalize_sync_url(raw_url: str) -> str:
    from sqlalchemy.engine import make_url

    url = make_url(raw_url)
    if url.drivername == "postgresql+asyncpg":
        return str(url.set(drivername="postgresql+psycopg2"))
    return str(url)


def _load_source_table(source_engine: Engine, table_name: str) -> Table:
    return Table(table_name, MetaData(), autoload_with=source_engine)


def _read_source_rows(source_engine: Engine, table_name: str) -> list[dict[str, Any]]:
    source_table = _load_source_table(source_engine, table_name)
    with source_engine.connect() as connection:
        return [dict(row._mapping) for row in connection.execute(select(source_table)).all()]


def _resolve_target_user(session: Session, target_username: Optional[str]) -> User:
    if target_username:
        normalized_username = normalize_username(target_username)
        user = session.scalar(select(User).where(User.username == normalized_username))
        if user is None:
            raise ValueError(f"Target user '{normalized_username}' does not exist")
        return user

    settings = get_settings()
    if settings.auth_initial_username:
        normalized_username = normalize_username(settings.auth_initial_username)
        user = session.scalar(select(User).where(User.username == normalized_username))
        if user is not None:
            return user

    users = session.scalars(select(User).order_by(User.id.asc())).all()
    if len(users) == 1:
        return users[0]
    if not users:
        raise ValueError("No users found in target database; create the target account first")
    raise ValueError(
        "Target database has multiple users; pass --target-username to choose the import owner"
    )


def _clear_user_workspace(session: Session, user_id: int) -> None:
    session.execute(delete(RewardLedger).where(RewardLedger.user_id == user_id))
    session.execute(delete(DailyTask).where(DailyTask.user_id == user_id))

    project_ids = session.scalars(
        select(TaskProject.id).where(TaskProject.user_id == user_id).order_by(TaskProject.id.asc())
    ).all()
    if project_ids:
        session.execute(delete(TaskTemplate).where(TaskTemplate.project_id.in_(project_ids)))
    session.execute(delete(TaskProject).where(TaskProject.user_id == user_id))
    session.flush()


def _next_pk(connection: Connection, table_name: str) -> int:
    table = Table(table_name, MetaData(), autoload_with=connection)
    primary_key_column = next(iter(table.primary_key.columns))
    max_id = connection.execute(select(func.max(primary_key_column))).scalar_one()
    return int(max_id or 0) + 1


def _insert_projects(
    connection: Connection,
    user_id: int,
    source_rows: Sequence[Mapping[str, Any]],
) -> dict[int, int]:
    table = Table("task_projects", MetaData(), autoload_with=connection)
    next_id = _next_pk(connection, "task_projects")
    inserted_rows: list[dict[str, Any]] = []
    id_map: dict[int, int] = {}

    for row in source_rows:
        new_id = next_id
        next_id += 1
        id_map[int(row["id"])] = new_id
        inserted_rows.append(
            {
                "id": new_id,
                "user_id": user_id,
                "name": row["name"],
                "status": row["status"],
                "sort_order": row["sort_order"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    if inserted_rows:
        connection.execute(table.insert(), inserted_rows)
    return id_map


def _insert_task_templates(
    connection: Connection,
    project_id_map: Mapping[int, int],
    source_rows: Sequence[Mapping[str, Any]],
) -> dict[int, int]:
    table = Table("task_templates", MetaData(), autoload_with=connection)
    next_id = _next_pk(connection, "task_templates")
    inserted_rows: list[dict[str, Any]] = []
    id_map: dict[int, int] = {}

    for row in source_rows:
        source_project_id = int(row["project_id"])
        if source_project_id not in project_id_map:
            raise ValueError(f"Source task_template references missing project_id={source_project_id}")
        new_id = next_id
        next_id += 1
        id_map[int(row["id"])] = new_id
        inserted_rows.append(
            {
                "id": new_id,
                "project_id": project_id_map[source_project_id],
                "name": row["name"],
                "default_estimated_duration_minutes": row["default_estimated_duration_minutes"],
                "default_reward_amount": row["default_reward_amount"],
                "notes": row["notes"],
                "is_active": row["is_active"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    if inserted_rows:
        connection.execute(table.insert(), inserted_rows)
    return id_map


def _insert_daily_tasks(
    connection: Connection,
    user_id: int,
    project_id_map: Mapping[int, int],
    template_id_map: Mapping[int, int],
    source_rows: Sequence[Mapping[str, Any]],
) -> dict[int, int]:
    table = Table("daily_tasks", MetaData(), autoload_with=connection)
    next_id = _next_pk(connection, "daily_tasks")
    inserted_rows: list[dict[str, Any]] = []
    id_map: dict[int, int] = {}

    for row in source_rows:
        source_project_id = int(row["project_id"])
        source_template_id = int(row["task_template_id"])
        if source_project_id not in project_id_map:
            raise ValueError(f"Source daily_task references missing project_id={source_project_id}")
        if source_template_id not in template_id_map:
            raise ValueError(
                f"Source daily_task references missing task_template_id={source_template_id}"
            )
        new_id = next_id
        next_id += 1
        id_map[int(row["id"])] = new_id
        inserted_rows.append(
            {
                "id": new_id,
                "date": row["date"],
                "user_id": user_id,
                "project_id": project_id_map[source_project_id],
                "task_template_id": template_id_map[source_template_id],
                "name_snapshot": row["name_snapshot"],
                "estimated_duration_minutes_snapshot": row[
                    "estimated_duration_minutes_snapshot"
                ],
                "reward_amount_snapshot": row["reward_amount_snapshot"],
                "status": row["status"],
                "actual_duration_minutes": row["actual_duration_minutes"],
                "completed_at": row["completed_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    if inserted_rows:
        connection.execute(table.insert(), inserted_rows)
    return id_map


def _insert_reward_ledger(
    connection: Connection,
    user_id: int,
    daily_task_id_map: Mapping[int, int],
    source_rows: Sequence[Mapping[str, Any]],
) -> int:
    table = Table("reward_ledger", MetaData(), autoload_with=connection)
    next_id = _next_pk(connection, "reward_ledger")
    inserted_rows: list[dict[str, Any]] = []

    for row in source_rows:
        source_daily_task_id = row["daily_task_id"]
        new_daily_task_id = None
        if source_daily_task_id is not None:
            source_daily_task_id = int(source_daily_task_id)
            if source_daily_task_id not in daily_task_id_map:
                raise ValueError(
                    f"Source reward_ledger references missing daily_task_id={source_daily_task_id}"
                )
            new_daily_task_id = daily_task_id_map[source_daily_task_id]

        inserted_rows.append(
            {
                "id": next_id,
                "user_id": user_id,
                "entry_type": row["entry_type"],
                "amount": row["amount"],
                "reason": row["reason"],
                "daily_task_id": new_daily_task_id,
                "created_at": row["created_at"],
            }
        )
        next_id += 1

    if inserted_rows:
        connection.execute(table.insert(), inserted_rows)
    return len(inserted_rows)


def migrate_from_lifeboard(
    source_db_url: str,
    target_username: Optional[str] = None,
    target_engine: Optional[Engine] = None,
) -> dict[str, int]:
    source_engine = create_engine(normalize_sync_url(source_db_url), future=True)
    engine = target_engine or get_engine()
    session_factory = get_session_factory() if target_engine is None else None

    try:
        project_rows = _read_source_rows(source_engine, "task_projects")
        template_rows = _read_source_rows(source_engine, "task_templates")
        daily_task_rows = _read_source_rows(source_engine, "daily_tasks")
        reward_rows = _read_source_rows(source_engine, "reward_ledger")

        if target_engine is None:
            session = session_factory()
        else:
            session = Session(bind=engine, autoflush=False, autocommit=False, future=True)

        try:
            target_user = _resolve_target_user(session, target_username)
            _clear_user_workspace(session, target_user.id)
            session.commit()

            with engine.begin() as connection:
                project_id_map = _insert_projects(connection, target_user.id, project_rows)
                template_id_map = _insert_task_templates(connection, project_id_map, template_rows)
                daily_task_id_map = _insert_daily_tasks(
                    connection,
                    target_user.id,
                    project_id_map,
                    template_id_map,
                    daily_task_rows,
                )
                reward_count = _insert_reward_ledger(
                    connection,
                    target_user.id,
                    daily_task_id_map,
                    reward_rows,
                )
        finally:
            session.close()

        return {
            "task_projects": len(project_rows),
            "task_templates": len(template_rows),
            "daily_tasks": len(daily_task_rows),
            "reward_ledger": reward_count,
        }
    finally:
        source_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import task-reward data from a legacy lifeboard database into one local account"
    )
    parser.add_argument("--source-db-url", required=True, help="lifeboard database URL")
    parser.add_argument(
        "--target-username",
        help=(
            "target username in the current database; "
            "if omitted, uses AUTH_INITIAL_USERNAME when present, otherwise requires exactly one user"
        ),
    )
    args = parser.parse_args()

    init_db()
    migrated = migrate_from_lifeboard(
        source_db_url=args.source_db_url,
        target_username=args.target_username,
    )

    for table_name in TABLES:
        print(f"{table_name}: {migrated[table_name]}")


if __name__ == "__main__":
    main()
