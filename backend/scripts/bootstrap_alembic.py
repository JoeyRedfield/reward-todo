import subprocess
from typing import Optional

from sqlalchemy import create_engine, inspect, text

from app.config import get_settings


TASK_REWARD_TABLES = {
    "task_projects",
    "task_templates",
    "daily_tasks",
    "reward_ledger",
}
AUTH_TABLES = {
    "users",
    "sessions",
    "access_tokens",
}
HEAD_REVISION = "0005_add_user_ownership_to_task_reward"


def detect_legacy_revision(schema_inspector) -> Optional[str]:
    table_names = set(schema_inspector.get_table_names())
    if "alembic_version" in table_names:
        return None

    has_task_reward_tables = TASK_REWARD_TABLES.issubset(table_names)
    has_auth_tables = AUTH_TABLES.issubset(table_names)

    if has_task_reward_tables and not has_auth_tables:
        return "0001_init_task_reward"

    if not has_auth_tables:
        return None

    user_columns = {column["name"] for column in schema_inspector.get_columns("users")}
    if not {"display_name", "email"}.issubset(user_columns):
        return "0002_add_auth_tables"

    if not has_task_reward_tables:
        return "0004_add_user_profile_and_registration_flag"

    task_project_columns = {column["name"] for column in schema_inspector.get_columns("task_projects")}
    daily_task_columns = {column["name"] for column in schema_inspector.get_columns("daily_tasks")}
    reward_ledger_columns = {column["name"] for column in schema_inspector.get_columns("reward_ledger")}
    if not all(
        "user_id" in columns
        for columns in (task_project_columns, daily_task_columns, reward_ledger_columns)
    ):
        return "0004_add_user_profile_and_registration_flag"

    return HEAD_REVISION


def ensure_alembic_version_capacity(engine) -> None:
    with engine.begin() as connection:
        schema_inspector = inspect(connection)
        if "alembic_version" not in set(schema_inspector.get_table_names()):
            return

        version_column = next(
            (
                column
                for column in schema_inspector.get_columns("alembic_version")
                if column["name"] == "version_num"
            ),
            None,
        )
        column_type = None if version_column is None else version_column.get("type")
        length = None if column_type is None else getattr(column_type, "length", None)
        if engine.dialect.name == "postgresql" and length is not None and length < 128:
            connection.execute(
                text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
            )


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    try:
        with engine.connect() as connection:
            revision = detect_legacy_revision(inspect(connection))

        if revision is None:
            ensure_alembic_version_capacity(engine)
            return

        print(f"Stamping existing schema to {revision} before alembic upgrade head")
        subprocess.run(["alembic", "stamp", revision], check=True)
        ensure_alembic_version_capacity(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
