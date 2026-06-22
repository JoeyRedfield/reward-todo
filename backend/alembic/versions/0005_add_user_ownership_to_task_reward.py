"""add user ownership to task reward data

Revision ID: 0005_add_user_ownership_to_task_reward
Revises: 0004_add_user_profile_and_registration_flag
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_user_ownership_to_task_reward"
down_revision = "0004_add_user_profile_and_registration_flag"
branch_labels = None
depends_on = None


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
