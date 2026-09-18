"""add server timestamp defaults to billing tables

Revision ID: e8b0c234f6a8
Revises: d7a9b123e5f7
"""

from alembic import op
import sqlalchemy as sa

revision = "e8b0c234f6a8"
down_revision = "d7a9b123e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("billing_accounts", "usage_counters"):
        op.alter_column(
            table_name,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )
        op.alter_column(
            table_name,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )


def downgrade() -> None:
    for table_name in ("billing_accounts", "usage_counters"):
        op.alter_column(
            table_name,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=None,
        )
        op.alter_column(
            table_name,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=None,
        )
