"""ecommerce shopify stripe

Revision ID: b5e7f901c3d5
Revises: a4d6e8f0b2c4
"""
from alembic import op
import sqlalchemy as sa

revision = "b5e7f901c3d5"
down_revision = "a4d6e8f0b2c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("external_customer_id", sa.String(length=255), nullable=True))
    op.create_index("ix_customers_external_customer_id", "customers", ["external_customer_id"], unique=False)
    op.add_column("orders", sa.Column("external_order_id", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("payment_reference", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("payment_gateway", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"))
    op.add_column("orders", sa.Column("refunded_amount_usd", sa.Numeric(10, 2), nullable=False, server_default="0.00"))
    op.create_index("ix_orders_external_order_id", "orders", ["external_order_id"], unique=False)
    op.create_index("ix_orders_payment_reference", "orders", ["payment_reference"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_payment_reference", table_name="orders")
    op.drop_index("ix_orders_external_order_id", table_name="orders")
    op.drop_column("orders", "refunded_amount_usd")
    op.drop_column("orders", "currency")
    op.drop_column("orders", "payment_gateway")
    op.drop_column("orders", "payment_reference")
    op.drop_column("orders", "external_order_id")
    op.drop_index("ix_customers_external_customer_id", table_name="customers")
    op.drop_column("customers", "external_customer_id")
