"""SQLAlchemy declarative base.

Kept in its own tiny module (rather than in models/__init__.py) so that
Alembic's env.py and the models package can both import it without
creating a circular import between "the base" and "the things built on it".
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class every ORM model inherits from."""

    pass
