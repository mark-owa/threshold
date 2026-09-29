"""add organization invitations for SaaS team onboarding"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "8a2b4c6d8e0f"
down_revision = "7f8a9c1d2e3f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_invitations",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "email", name="uq_org_invitation_email"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_organization_invitations_email"),
        "organization_invitations",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_invitations_organization_id"),
        "organization_invitations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_invitations_token_hash"),
        "organization_invitations",
        ["token_hash"],
        unique=True,
    )


def downgrade():
    op.drop_index(op.f("ix_organization_invitations_token_hash"), table_name="organization_invitations")
    op.drop_index(op.f("ix_organization_invitations_organization_id"), table_name="organization_invitations")
    op.drop_index(op.f("ix_organization_invitations_email"), table_name="organization_invitations")
    op.drop_table("organization_invitations")
