"""
pytest configuration and shared fixtures.

Test-isolation strategy:
  - A dedicated PostgreSQL schema (test_equiconnected) is created once for the
    entire session and dropped afterwards.
  - Each test gets its own SQLAlchemy session.  After each test, all table rows
    are deleted in FK-safe order so the next test starts with a clean slate.
    This is simpler and more reliable than the SAVEPOINT/outer-transaction
    pattern in SQLAlchemy 2.x, which has subtle behaviour differences depending
    on the SA version.
  - Rate limiting is disabled for all tests via a dependency override.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.rate_limit import (
    check_email_verification_rate_limit,
    check_login_rate_limit,
    check_registration_rate_limit,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# ── Database URL ──────────────────────────────────────────────────────────────

_RAW_DB_URL = os.environ.get("DATABASE_URL", "")
TEST_DB_URL = (
    _RAW_DB_URL.replace("postgres://", "postgresql://", 1)
    if _RAW_DB_URL.startswith("postgres://")
    else _RAW_DB_URL
)

TEST_SCHEMA = "test_equiconnected"

# ── Tables that need truncation in FK-safe reverse order ─────────────────────
# Leaf tables first so FK constraints are satisfied.
_CLEANUP_TABLES = [
    "horses",
    "stable_profiles",
    "provider_reviews",
    "provider_registration_applications",
    "refresh_tokens",
    "email_verification_tokens",
    "email_delivery_logs",
    "audit_logs",
    "provider_invitations",
    "organization_requests",
    "doctor_organizations",
    "doctor_qualifications",
    "doctor_profiles",
    "user_roles",
    "users",
    "roles",
    "provider_specializations",
    "provider_phones",
    "provider_emails",
    "provider_photos",
    "provider_locations",
    "providers",
    "specializations",
    "public_visit_daily",
    "system_settings",
]


# ── Engine with search_path pinned to the test schema ────────────────────────

def _make_engine(schema: str):
    """Return a SQLAlchemy engine whose connections always use *schema*."""
    e = create_engine(TEST_DB_URL, pool_pre_ping=True, pool_size=5)

    @event.listens_for(e, "connect")
    def _set_search_path(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {schema}")
        cursor.close()

    return e


engine = _make_engine(TEST_SCHEMA)
# Use positional arg (SA-2.x recommended) to avoid deprecation warning
TestingSessionLocal = sessionmaker(engine, autocommit=False, autoflush=False)


# ── Session-scoped schema + table setup ───────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Create the test schema and all ORM-mapped tables before any test runs.
    Tear down the schema (CASCADE) after the session ends.

    A separate engine without the search_path listener is used for DROP/CREATE
    SCHEMA so those DDL statements run against the public schema.
    """
    admin_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
        conn.commit()
    admin_engine.dispose()

    # create_all picks up the search_path event → tables land in TEST_SCHEMA
    Base.metadata.create_all(bind=engine)

    yield

    admin_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.commit()
    admin_engine.dispose()


# ── Per-test DB session ───────────────────────────────────────────────────────

def _delete_all_rows() -> None:
    """Remove every row from every table in FK-safe order."""
    with engine.connect() as conn:
        available_tables = set(inspect(conn).get_table_names())
        for table in _CLEANUP_TABLES:
            if table in available_tables:
                conn.execute(text(f"DELETE FROM {table}"))
        conn.commit()
    # The verification concurrency test creates independent sessions. Dispose
    # the shared pool after every test so a closed worker connection cannot
    # outlive its test and interfere with the next isolated session.
    engine.dispose()


@pytest.fixture()
def db():
    """
    Database session for a single test.

    After the test (pass or fail) all rows are deleted so the next test
    starts with a completely empty schema.
    """
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        # Roll back any uncommitted/errored transaction before closing so that
        # the cleanup DELETE statements can run on a clean connection.
        try:
            session.rollback()
        except Exception:
            pass
        session.close()
        _delete_all_rows()


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture()
def client(db):
    """
    FastAPI test client with:
      - the per-test DB session injected via dependency override
      - login rate limiting disabled
    """
    def _override_get_db():
        yield db

    def _no_rate_limit():
        return None

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[check_login_rate_limit] = _no_rate_limit
    app.dependency_overrides[check_registration_rate_limit] = _no_rate_limit
    app.dependency_overrides[check_email_verification_rate_limit] = _no_rate_limit

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture()
def seeded_admin(db):
    """
    Create a fully active admin user for the current test.
    Returns (user_orm_object, plain_password).
    """
    from app.core.security import hash_password
    from app.repositories.user_repository import UserRepository

    repo = UserRepository(db)
    role = repo.get_role_by_name("admin")
    if role is None:
        role = repo.create_role("admin", "Administrator")

    password = "TestAdmin#2026!"
    user = repo.create_user(
        email="testadmin@example.com",
        password_hash=hash_password(password),
        role=role,
        first_name="Test",
        last_name="Admin",
    )
    db.commit()
    return user, password
