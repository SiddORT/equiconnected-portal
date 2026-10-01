"""Exercise the prospective traffic migration without touching live tables."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from tests.conftest import engine


def test_traffic_migration_roundtrip_preserves_legacy_counter():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic/versions/e3b5a49c1d72_add_analytics_traffic_aggregates.py"
    )
    spec = importlib.util.spec_from_file_location("traffic_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    traffic_tables = {
        "analytics_traffic_page_category_daily",
        "analytics_traffic_provider_profile_daily",
        "analytics_traffic_visitor_daily",
        "analytics_traffic_tracking_metadata",
        "analytics_traffic_tracking_receipts",
    }
    # The shared fixture installs every model in its isolated test schema.
    # Transaction rollback restores that schema after exercising the migration.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
                assert traffic_tables.isdisjoint(inspect(connection).get_table_names())
                assert "public_visit_daily" in inspect(connection).get_table_names()
                migration.upgrade()
                assert traffic_tables <= set(inspect(connection).get_table_names())
                assert "public_visit_daily" in inspect(connection).get_table_names()
        finally:
            transaction.rollback()