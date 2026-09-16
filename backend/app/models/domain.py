import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import GUID, TimestampMixin, UUIDPKMixin, enum_column
from app.models.enums import NotificationChannel, RequestCategory


class Customer(Base, UUIDPKMixin, TimestampMixin):
    """A demo org's customer. In a real deployment this table wouldn't
    exist -- the customer-lookup step would call the client's actual
    CRM/e-commerce platform through an integration. Here it plays that
    role so the whole pipeline is demonstrable with zero external
    credentials."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_customer_org_email"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "order_number", name="uq_order_org_number"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


class Policy(Base, UUIDPKMixin, TimestampMixin):
    """The deterministic knowledge source. `content` is human-readable
    (usable as bounded context for an LLM drafting step); `structured_rules`
    is what the business-rule engine actually evaluates against -- e.g.
    {"refund_window_days": 30, "max_auto_refund_usd": 75}. Intentionally a
    plain table, not embeddings: an SMB's policy set is small and
    structured enough that a lookup-by-category beats a vector index, and
    building one here would just be re-doing Meridian's retrieval layer
    for no benefit."""

    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "category", name="uq_policy_org_category"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[RequestCategory] = mapped_column(enum_column(RequestCategory), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Lead(Base, UUIDPKMixin, TimestampMixin):
    """Seeded lead data. CRM-related fields are reserved; the current
    lead workflow only classifies the request and records a notification."""

    __tablename__ = "leads"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)
    external_crm_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    crm_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class NotificationLog(Base, UUIDPKMixin):
    """The observable mock outbox. When a workflow "sends an email" or
    "posts to Slack" in demo mode, it lands here -- so a reviewer can see
    exactly what would have gone out, without needing a real inbox or
    workspace connected."""

    __tablename__ = "notifications_log"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("workflow_executions.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        enum_column(NotificationChannel), nullable=False
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="sent", nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
