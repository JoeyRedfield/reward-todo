import argparse
import sys
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.database import get_engine


TABLES = [
    "task_projects",
    "task_templates",
    "daily_tasks",
    "reward_ledger",
]


def normalize_sync_url(raw_url: str) -> str:
    url = make_url(raw_url)
    if url.drivername == "postgresql+asyncpg":
        return str(url.set(drivername="postgresql+psycopg2"))
    return str(url)


def copy_table(source_engine, target_engine, table_name: str) -> int:
    source_metadata = MetaData()
    target_metadata = MetaData()
    source_table = Table(table_name, source_metadata, autoload_with=source_engine)
    target_table = Table(table_name, target_metadata, autoload_with=target_engine)

    with source_engine.connect() as source_conn:
      rows = [dict(row._mapping) for row in source_conn.execute(select(source_table)).all()]

    if not rows:
        return 0

    with target_engine.begin() as target_conn:
        target_conn.execute(target_table.delete())
        target_conn.execute(target_table.insert(), rows)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate task-reward tables from lifeboard")
    parser.add_argument("--source-db-url", required=True, help="lifeboard database URL")
    args = parser.parse_args()

    source_engine = create_engine(normalize_sync_url(args.source_db_url), future=True)
    target_engine = get_engine()

    migrated: dict[str, int] = {}
    for table_name in TABLES:
        migrated[table_name] = copy_table(source_engine, target_engine, table_name)

    for table_name, count in migrated.items():
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
