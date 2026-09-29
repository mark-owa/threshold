import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import GUID, TimestampMixin, UUIDPKMixin, enum_column
from app.models.enums import OutboxStatus


class OutboxMessage(Base, UUIDPKMixin, TimestampMixin):
    """Durable handoff between the database transaction and Celery.

    Publishing is intentionally at-least-once. Consumers therefore use stable
    aggregate ids/idempotency keys and are required to be idempotent.
    """

    __tablename__ = "outbox_messages"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        enum_column(OutboxStatus), default=OutboxStatus.PENDING, nullable=False, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class WebhookEndpoint(Base, UUIDPKMixin, TimestampMixin):
    """Tenant-scoped signed webhook ingress configuration.

    The database stores only a secret reference. The actual HMAC secret lives
    in the deployment secret store/environment.
    """

    __tablename__ = "webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("endpoint_key", name="uq_webhook_endpoint_key"),
        UniqueConstraint("organization_id", "name", name="uq_webhook_org_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    signing_secret_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allowed_clock_skew_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
