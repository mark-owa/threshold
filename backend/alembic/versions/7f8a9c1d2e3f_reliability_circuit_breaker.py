"""add integration circuit breaker state"""

from alembic import op
import sqlalchemy as sa

revision = "7f8a9c1d2e3f"
down_revision = "6cf140b88525"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("integration_configs", sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("integration_configs", sa.Column("failure_threshold", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("integration_configs", sa.Column("circuit_open_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("integration_configs", sa.Column("recovery_timeout_seconds", sa.Integer(), nullable=False, server_default="30"))
    op.alter_column("integration_configs", "consecutive_failures", server_default=None)
    op.alter_column("integration_configs", "failure_threshold", server_default=None)
    op.alter_column("integration_configs", "recovery_timeout_seconds", server_default=None)

def downgrade():
    op.drop_column("integration_configs", "recovery_timeout_seconds")
    op.drop_column("integration_configs", "circuit_open_until")
    op.drop_column("integration_configs", "failure_threshold")
    op.drop_column("integration_configs", "consecutive_failures")
