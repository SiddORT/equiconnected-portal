"""Exercise the status-only migration without changing development/live tables."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from tests.conftest import engine


def test_owner_saved_status_migration_roundtrip():
    path = Path(__file__).parents[1] / "alembic/versions/8e6a1d4b2c90_retire_owner_saved_profile_drafts.py"
    spec = importlib.util.spec_from_file_location("owner_saved_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            def labels():
                return connection.scalars(text(
                    "SELECT enumlabel FROM pg_enum "
                    "WHERE enumtypid = 'provider_profile_update_status'::regtype ORDER BY enumsortorder"
                )).all()

            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                assert labels() == ["PENDING_REVIEW", "APPROVED", "REJECTED"]
                migration.upgrade()
                migration.upgrade()  # retry is harmless and never applies any draft
                assert labels() == ["PENDING_REVIEW", "APPROVED", "REJECTED", "SAVED_DIRECTLY"]
        finally:
            transaction.rollback()
