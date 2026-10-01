"""Run the messaging migration against isolated transactional test tables."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from tests.conftest import engine


def test_messaging_migration_roundtrip_preserves_existing_account_tables():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/4f8a2c1d6e90_add_private_provider_messaging.py"
    )
    spec = importlib.util.spec_from_file_location("messaging_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    tables = {
        "provider_conversations",
        "provider_messages",
        "messaging_notification_outbox",
        "messaging_send_limits",
    }
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                remaining = set(inspect(connection).get_table_names())
                assert tables.isdisjoint(remaining)
                assert {"users", "providers", "email_delivery_logs"} <= remaining
                migration.upgrade()
                assert tables <= set(inspect(connection).get_table_names())
                constraints = inspect(connection).get_check_constraints("email_delivery_logs")
                purpose = next(item for item in constraints if item["name"] == "ck_email_delivery_logs_purpose")
                assert "messaging_member_acknowledgement" in purpose["sqltext"]
                assert "messaging_provider_new_message" in purpose["sqltext"]
                assert "messaging_member_reply" in purpose["sqltext"]
        finally:
            transaction.rollback()