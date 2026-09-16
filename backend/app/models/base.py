"""Shared mixins and type helpers used across ORM models.

Two deliberate choices worth flagging (see docs/DECISIONS.md for the full
rationale):

1. UUID primary keys, generated client-side. Safe for a multi-tenant system
   (no sequential-ID enumeration across orgs), and they double as stable
   correlation identifiers in logs without needing a separate column.

2. Enum columns are stored as VARCHAR (`native_enum=False`) with the
   Python enum's `.value` persisted (not its `.name`, which is
   SQLAlchemy's default and a common source of subtle bugs when the two
   differ in case). Native Postgres ENUM types are more "correct" in
   theory, but adding a new status/category later means an
   `ALTER TYPE ... ADD VALUE` migration with its own transaction quirks.
   VARCHAR + application-level validation is the more boring, more
   maintainable choice for a system whose workflow categories are
   expected to grow.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

# Shared UUID column type so every FK matches every PK exactly.
GUID = PGUUID(as_uuid=True)


def enum_column(enum_cls):
    """Return a SQLAlchemy Enum type that persists `.value`, not `.name`."""
    return SQLEnum(
        enum_cls,
        values_callable=lambda x: [e.value for e in x],
        native_enum=False,
        length=50,
    )


class UUIDPKMixin:
    """Adds a client-generated UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Adds created_at / updated_at, both server-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
