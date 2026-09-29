"""security hardening receipts and oauth replay protection

Revision ID: d7a9b123e5f7
Revises: c6f8a012d4e6
"""
from alembic import op
import sqlalchemy as sa

revision = "d7a9b123e5f7"
down_revision = "c6f8a012d4e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_webhook_receipts",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=255), nullable=True),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_id", name="uq_external_webhook_provider_event"),
    )
    op.create_index("ix_external_webhook_receipts_provider", "external_webhook_receipts", ["provider"])
    op.create_index("ix_external_webhook_receipts_event_id", "external_webhook_receipts", ["event_id"])
    op.create_index("ix_external_webhook_receipts_organization_id", "external_webhook_receipts", ["organization_id"])

    op.create_table(
        "oauth_state_nonces",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("initiated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("nonce_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nonce_hash", name="uq_oauth_state_nonce_hash"),
    )
    op.create_index("ix_oauth_state_nonces_organization_id", "oauth_state_nonces", ["organization_id"])
    op.create_index("ix_oauth_state_nonces_initiated_by_user_id", "oauth_state_nonces", ["initiated_by_user_id"])
    op.create_index("ix_oauth_state_nonces_provider", "oauth_state_nonces", ["provider"])
    op.create_index("ix_oauth_state_nonces_expires_at", "oauth_state_nonces", ["expires_at"])


def downgrade() -> None:
    op.drop_table("oauth_state_nonces")
    op.drop_table("external_webhook_receipts")
