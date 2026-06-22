"""add user ownership to task reward data

Revision ID: 0005_add_user_ownership_to_task_reward
Revises: 0004_add_user_profile_and_registration_flag
Create Date: 2026-06-22
"""

import os
from typing import Optional

from alembic import op
import sqlalchemy as sa

from app.security import hash_password, normalize_username


revision = "0005_add_user_ownership_to_task_reward"
down_revision = "0004_add_user_profile_and_registration_flag"
branch_labels = None
depends_on = None


def _resolve_bootstrap_user_id(connection) -> Optional[int]:
    initial_username = os.environ.get("AUTH_INITIAL_USERNAME", "")
    normalized_username = normalize_username(initial_username) if initial_username else ""
    if normalized_username:
        bootstrap_user_id = connection.execute(
            sa.text(
                """
                SELECT id
                FROM users
                WHERE username = :username
                LIMIT 1
                """
            ),
            {"username": normalized_username},
        ).scalar()
        if bootstrap_user_id is not None:
            return int(bootstrap_user_id)

    bootstrap_user_id = connection.execute(
        sa.text(
            """
            SELECT id
            FROM users
            ORDER BY id ASC
            LIMIT 1
            """
        )
    ).scalar()
    if bootstrap_user_id is not None:
        return int(bootstrap_user_id)

    initial_password = os.environ.get("AUTH_INITIAL_PASSWORD", "")
    if not normalized_username or not initial_password:
        raise RuntimeError(
            "0005 migration requires AUTH_INITIAL_USERNAME and AUTH_INITIAL_PASSWORD "
            "when legacy task/reward data exists without any users"
        )

    email = f"{normalized_username}@local.invalid"
    password_hash = hash_password(initial_password)
    result = connection.execute(
        sa.text(
            """
            INSERT INTO users (
                username,
                display_name,
                email,
                password_hash,
                created_at,
                updated_at,
                password_changed_at
            ) VALUES (
                :username,
                :display_name,
                :email,
                :password_hash,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "username": normalized_username,
            "display_name": normalized_username,
            "email": email,
            "password_hash": password_hash,
        },
    )
    if result.lastrowid is not None:
        return int(result.lastrowid)

    bootstrap_user_id = connection.execute(
        sa.text(
            """
            SELECT id
            FROM users
            WHERE username = :username
            LIMIT 1
            """
        ),
        {"username": normalized_username},
    ).scalar()
    if bootstrap_user_id is None:
        raise RuntimeError("0005 migration failed to create bootstrap user for legacy task/reward data")
    return int(bootstrap_user_id)


def upgrade() -> None:
    with op.batch_alter_table("task_projects") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_task_projects_user_id", ["user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_task_projects_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )

    with op.batch_alter_table("daily_tasks") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_daily_tasks_user_id", ["user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_daily_tasks_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )

    with op.batch_alter_table("reward_ledger") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_reward_ledger_user_id", ["user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_reward_ledger_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )

    connection = op.get_bind()
    legacy_rows_exist = any(
        bool(
            connection.execute(
                sa.text(f"SELECT 1 FROM {table_name} LIMIT 1")
            ).scalar()
        )
        for table_name in ("task_projects", "daily_tasks", "reward_ledger")
    )
    bootstrap_user_id = _resolve_bootstrap_user_id(connection) if legacy_rows_exist else None

    if bootstrap_user_id is not None:
        connection.execute(
            sa.text(
                """
                UPDATE task_projects
                SET user_id = :user_id
                WHERE user_id IS NULL
                """
            ),
            {"user_id": bootstrap_user_id},
        )
        connection.execute(
            sa.text(
                """
                UPDATE daily_tasks
                SET user_id = COALESCE(
                    (
                        SELECT task_projects.user_id
                        FROM task_projects
                        WHERE task_projects.id = daily_tasks.project_id
                    ),
                    :user_id
                )
                WHERE user_id IS NULL
                """
            ),
            {"user_id": bootstrap_user_id},
        )
        connection.execute(
            sa.text(
                """
                UPDATE reward_ledger
                SET user_id = COALESCE(
                    (
                        SELECT daily_tasks.user_id
                        FROM daily_tasks
                        WHERE daily_tasks.id = reward_ledger.daily_task_id
                    ),
                    :user_id
                )
                WHERE user_id IS NULL
                """
            ),
            {"user_id": bootstrap_user_id},
        )

    with op.batch_alter_table("task_projects") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("daily_tasks") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("reward_ledger") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("reward_ledger") as batch_op:
        batch_op.drop_constraint("fk_reward_ledger_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_reward_ledger_user_id")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("daily_tasks") as batch_op:
        batch_op.drop_constraint("fk_daily_tasks_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_daily_tasks_user_id")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("task_projects") as batch_op:
        batch_op.drop_constraint("fk_task_projects_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_task_projects_user_id")
        batch_op.drop_column("user_id")
