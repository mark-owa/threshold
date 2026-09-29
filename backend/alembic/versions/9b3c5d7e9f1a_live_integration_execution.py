"""add live integration credential refs and action attempts"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9b3c5d7e9f1a"
down_revision = "8a2b4c6d8e0f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("integration_configs", sa.Column("credential_ref", sa.String(length=255), nullable=True))
    op.create_table(
        "action_attempts",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_operation_id", sa.String(length=255), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["action_execution_id"], ["action_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_action_attempts_organization_id"), "action_attempts", ["organization_id"], unique=False)
    op.create_index(op.f("ix_action_attempts_action_execution_id"), "action_attempts", ["action_execution_id"], unique=False)
    op.create_index(op.f("ix_action_attempts_provider_operation_id"), "action_attempts", ["provider_operation_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_action_attempts_provider_operation_id"), table_name="action_attempts")
    op.drop_index(op.f("ix_action_attempts_action_execution_id"), table_name="action_attempts")
    op.drop_index(op.f("ix_action_attempts_organization_id"), table_name="action_attempts")
    op.drop_table("action_attempts")
    op.drop_column("integration_configs", "credential_ref")
