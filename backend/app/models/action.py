import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import GUID, TimestampMixin, UUIDPKMixin, enum_column
from app.models.enums import ActionStatus, IntegrationProvider


class IntegrationConfig(Base, UUIDPKMixin, TimestampMixin):
    """Per-org configuration for an external system integration. `config`
    holds non-secret settings only (endpoint URLs, channel names); any
    actual credential is referenced by name, never stored raw here -- in
    demo mode there are no real credentials at all, since every provider
    is a mock that reads/writes local tables."""

    __tablename__ = "integration_configs"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_integration_org_provider"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        enum_column(IntegrationProvider), nullable=False
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    circuit_open_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recovery_timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)


class ActionExecution(Base, UUIDPKMixin, TimestampMixin):
    """One mock action and its retry history. The
    idempotency_key is unique: the database prevents duplicate action rows for this key. Real
    external effects would also require provider-side idempotency."""

    __tablename__ = "action_executions"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_action_idempotency"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_execution_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True
    )
    integration_config_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("integration_configs.id", ondelete="SET NULL"), nullable=True
    )

    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ActionStatus] = mapped_column(
        enum_column(ActionStatus), default=ActionStatus.PENDING, nullable=False, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
