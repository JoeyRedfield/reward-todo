"""allow direct daily tasks

Revision ID: 0006_allow_direct_daily_tasks
Revises: 0005_add_user_ownership_to_task_reward
Create Date: 2026-06-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_allow_direct_daily_tasks"
down_revision = "0005_add_user_ownership_to_task_reward"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("daily_tasks") as batch_op:
        batch_op.drop_constraint("uq_daily_task_template_date", type_="unique")
        batch_op.alter_column("project_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("task_template_id", existing_type=sa.Integer(), nullable=True)

    op.create_index(
        "uq_daily_task_template_date",
        "daily_tasks",
        ["date", "task_template_id"],
        unique=True,
        sqlite_where=sa.text("task_template_id IS NOT NULL"),
        postgresql_where=sa.text("task_template_id IS NOT NULL"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    direct_task_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(1)
            FROM daily_tasks
            WHERE project_id IS NULL OR task_template_id IS NULL
            """
        )
    ).scalar()
    if int(direct_task_count or 0) > 0:
        raise RuntimeError("cannot downgrade with direct daily tasks present")

    op.drop_index("uq_daily_task_template_date", table_name="daily_tasks")

    with op.batch_alter_table("daily_tasks") as batch_op:
        batch_op.alter_column("task_template_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("project_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint(
            "uq_daily_task_template_date",
            ["date", "task_template_id"],
        )
