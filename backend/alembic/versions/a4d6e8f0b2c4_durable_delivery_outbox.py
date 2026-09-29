"""durable event delivery, webhook ingress, and outbox"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a4d6e8f0b2c4"
down_revision = "9b3c5d7e9f1a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incoming_events", sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("incoming_events", sa.Column("max_processing_attempts", sa.Integer(), server_default="5", nullable=False))
    op.add_column("incoming_events", sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incoming_events", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incoming_events", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incoming_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_index(op.f("ix_incoming_events_next_retry_at"), "incoming_events", ["next_retry_at"], unique=False)

    op.add_column("action_executions", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("action_executions", sa.Column("locked_by", sa.String(length=255), nullable=True))

    op.create_table(
        "outbox_messages",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outbox_messages_organization_id"), "outbox_messages", ["organization_id"], unique=False)
    op.create_index(op.f("ix_outbox_messages_topic"), "outbox_messages", ["topic"], unique=False)
    op.create_index(op.f("ix_outbox_messages_aggregate_id"), "outbox_messages", ["aggregate_id"], unique=False)
    op.create_index(op.f("ix_outbox_messages_status"), "outbox_messages", ["status"], unique=False)
    op.create_index(op.f("ix_outbox_messages_available_at"), "outbox_messages", ["available_at"], unique=False)

    op.create_table(
        "webhook_endpoints",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("endpoint_key", sa.String(length=100), nullable=False),
        sa.Column("signing_secret_ref", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("allowed_clock_skew_seconds", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_key", name="uq_webhook_endpoint_key"),
        sa.UniqueConstraint("organization_id", "name", name="uq_webhook_org_name"),
    )
    op.create_index(op.f("ix_webhook_endpoints_organization_id"), "webhook_endpoints", ["organization_id"], unique=False)
    op.create_index(op.f("ix_webhook_endpoints_endpoint_key"), "webhook_endpoints", ["endpoint_key"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_webhook_endpoints_endpoint_key"), table_name="webhook_endpoints")
    op.drop_index(op.f("ix_webhook_endpoints_organization_id"), table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")

    op.drop_index(op.f("ix_outbox_messages_available_at"), table_name="outbox_messages")
    op.drop_index(op.f("ix_outbox_messages_status"), table_name="outbox_messages")
    op.drop_index(op.f("ix_outbox_messages_aggregate_id"), table_name="outbox_messages")
    op.drop_index(op.f("ix_outbox_messages_topic"), table_name="outbox_messages")
    op.drop_index(op.f("ix_outbox_messages_organization_id"), table_name="outbox_messages")
    op.drop_table("outbox_messages")

    op.drop_column("action_executions", "locked_by")
    op.drop_column("action_executions", "locked_at")

    op.drop_index(op.f("ix_incoming_events_next_retry_at"), table_name="incoming_events")
    op.drop_column("incoming_events", "last_error")
    op.drop_column("incoming_events", "completed_at")
    op.drop_column("incoming_events", "next_retry_at")
    op.drop_column("incoming_events", "processing_started_at")
    op.drop_column("incoming_events", "max_processing_attempts")
    op.drop_column("incoming_events", "processing_attempts")
