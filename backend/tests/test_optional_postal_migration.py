"""Optional postal migration preserves existing codes and never fills nulls."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from tests.conftest import engine


def test_optional_postal_migration_round_trip():
    path = Path(__file__).parents[1] / "alembic/versions/7d5f9b3a2c01_optional_provider_registration_postal.py"
    spec = importlib.util.spec_from_file_location("optional_postal", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            def nullable():
                return next(column["nullable"] for column in inspect(connection).get_columns(
                    "provider_registration_applications") if column["name"] == "postal_code")

            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                assert not nullable()
                migration.upgrade()
                assert nullable()
                migration.downgrade()
                assert not nullable()
                migration.upgrade()
                assert nullable()
        finally:
            transaction.rollback()
