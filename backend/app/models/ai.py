import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import GUID, TimestampMixin, UUIDPKMixin


class PromptTemplate(Base, UUIDPKMixin, TimestampMixin):
    """A versioned prompt. Business logic references a template by
    (key, version) -- e.g. ("classify_intent", 3) -- never an inline
    f-string. This is the entire answer to "don't bury prompts throughout
    the codebase": there is exactly one place prompts live, and changing
    one is a new row (new version), not an edit that silently changes
    behavior for everything already relying on the old wording.
    """

    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("key", "version", name="uq_prompt_key_version"),)

    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    model_target: Mapped[str] = mapped_column(String(100), default="gpt-4o-mini", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AIUsageLog(Base, UUIDPKMixin):
    """One row per LLM call. This is what the dashboard's "estimated AI
    cost" figure is computed from -- summed per org, per workflow, or per
    time window."""

    __tablename__ = "ai_usage_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("workflow_executions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    step_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("step_executions.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
