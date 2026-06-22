"""make access token expiry nullable

Revision ID: 0003_make_access_token_expiry_nullable
Revises: 0002_add_auth_tables
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_make_access_token_expiry_nullable"
down_revision = "0002_add_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("access_tokens") as batch_op:
        batch_op.alter_column("expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("access_tokens") as batch_op:
        batch_op.alter_column("expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
