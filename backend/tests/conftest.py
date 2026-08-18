"""
pytest configuration and shared fixtures.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Use an in-test DB (same DATABASE_URL) but a separate schema for isolation
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DB_URL = os.environ.get("DATABASE_URL", "")
if TEST_DB_URL.startswith("postgres://"):
    TEST_DB_URL = TEST_DB_URL.replace("postgres://", "postgresql://", 1)

# Override with test schema
TEST_SCHEMA = "test_equiconnected"

engine = create_engine(
    TEST_DB_URL,
    connect_args={},
    pool_pre_ping=True,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in the test schema before the test session, drop after."""
    with engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
        conn.execute(text(f"SET search_path TO {TEST_SCHEMA}"))
        conn.commit()

    # Temporarily set search_path on the engine
    engine.execute = None  # type: ignore
    Base.metadata.create_all(bind=engine)

    yield

    with engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.commit()


@pytest.fixture()
def db():
    """Per-test database session with rollback isolation."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """FastAPI test client with overridden DB dependency."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_admin(db):
    """Create a test admin user and return (user, plain_password)."""
    from app.core.security import hash_password
    from app.repositories.user_repository import UserRepository

    repo = UserRepository(db)
    role = repo.get_role_by_name("admin")
    if role is None:
        role = repo.create_role("admin", "Administrator")

    password = "TestAdmin#2026!"
    user = repo.create_user(
        email="testadmin@equiconnected.test",
        password_hash=hash_password(password),
        role=role,
        first_name="Test",
        last_name="Admin",
    )
    db.commit()
    return user, password
