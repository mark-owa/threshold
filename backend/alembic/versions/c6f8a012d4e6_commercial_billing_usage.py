"""commercial billing usage

Revision ID: c6f8a012d4e6
Revises: b5e7f901c3d5
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c6f8a012d4e6"
down_revision = "b5e7f901c3d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_accounts",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=255), nullable=True),
        sa.Column("subscription_id", sa.String(length=255), nullable=True),
        sa.Column("subscription_status", sa.String(length=50), nullable=False),
        sa.Column("price_id", sa.String(length=255), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_billing_org"),
    )
    op.create_index("ix_billing_accounts_organization_id", "billing_accounts", ["organization_id"])
    op.create_index("ix_billing_accounts_customer_id", "billing_accounts", ["customer_id"])
    op.create_index("ix_billing_accounts_subscription_id", "billing_accounts", ["subscription_id"])
    op.create_table(
        "usage_counters",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("period_key", sa.String(length=20), nullable=False),
        sa.Column("metric", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "period_key", "metric", name="uq_usage_org_period_metric"),
    )
    op.create_index("ix_usage_counters_organization_id", "usage_counters", ["organization_id"])
    op.create_index("ix_usage_counters_period_key", "usage_counters", ["period_key"])
    op.create_index("ix_usage_counters_metric", "usage_counters", ["metric"])


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("billing_accounts")
