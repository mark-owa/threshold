import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import GUID, UUIDPKMixin


class ExternalWebhookReceipt(Base, UUIDPKMixin):
    """Durable deduplication record for third-party webhook deliveries.

    A receipt is committed in the same transaction as the business state it
    protects. If processing rolls back, the receipt rolls back too so the
    provider can safely retry.
    """

    __tablename__ = "external_webhook_receipts"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_external_webhook_provider_event"),
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OAuthStateNonce(Base, UUIDPKMixin):
    """Single-use nonce backing a signed OAuth state token.

    Signed state protects integrity; this row adds replay protection. The raw
    nonce is never stored, only its SHA-256 digest.
    """

    __tablename__ = "oauth_state_nonces"
    __table_args__ = (UniqueConstraint("nonce_hash", name="uq_oauth_state_nonce_hash"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    initiated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
