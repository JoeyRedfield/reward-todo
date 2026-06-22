"""add user profile fields

Revision ID: 0004_add_user_profile_and_registration_flag
Revises: 0003_make_access_token_expiry_nullable
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_user_profile_and_registration_flag"
down_revision = "0003_make_access_token_expiry_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))

    op.execute("UPDATE users SET display_name = username WHERE display_name IS NULL")
    op.execute("UPDATE users SET email = username || '@local.invalid' WHERE email IS NULL")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("display_name", existing_type=sa.String(length=200), nullable=False)
        batch_op.alter_column("email", existing_type=sa.String(length=255), nullable=False)
        batch_op.create_unique_constraint("uq_users_email", ["email"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")
        batch_op.drop_column("email")
        batch_op.drop_column("display_name")
