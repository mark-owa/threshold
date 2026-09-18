"""Shared pytest fixtures.

Tests run against a real PostgreSQL database rather than SQLite -- the
app uses Postgres-specific types (JSONB, UUID) that SQLite can't
faithfully emulate, and "tests pass on a DB engine we don't ship on"
isn't worth much. `_ensure_test_database` creates the test DB
automatically so `pytest` works with zero manual setup beyond having a
Postgres server reachable at DATABASE_URL's host.
"""

import os

# Keep security-related tests self-contained when pytest is invoked outside
# Docker Compose. Explicit environment values still win.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SECRET_KEY", "pytest-only-threshold-secret-key-32-bytes-minimum")
os.environ.setdefault(
    "WEBHOOK_SIGNING_SECRET",
    "pytest-only-threshold-webhook-secret-32-bytes-minimum",
)

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (populates Base.metadata)
from app.core.config import get_settings
from app.db.base_class import Base

TEST_DATABASE_URL = make_url(get_settings().DATABASE_URL).set(database="threshold_test")


def _ensure_test_database(url) -> None:
    db_name = url.database
    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            try:
                conn.execute(text(f"CREATE DATABASE {db_name}"))
            except ProgrammingError as exc:
                if getattr(exc.orig, "sqlstate", None) != "42P04":
                    raise
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def engine():
    _ensure_test_database(TEST_DATABASE_URL)
    eng = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection, future=True)
    session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
