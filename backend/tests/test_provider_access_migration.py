"""Round-trip portal lifecycle changes in the isolated test schema."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from tests.conftest import engine


def test_provider_access_migration_roundtrip_preserves_legacy_tables():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/c2f4a8d17e60_provider_portal_password_recovery.py"
    )
    spec = importlib.util.spec_from_file_location("provider_access_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    lifecycle_columns = {
        "provider_portal_approval_pending",
        "provider_portal_approval_email_sent_at",
    }
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                schema = inspect(connection)
                assert "provider_portal_recovery_tokens" not in schema.get_table_names()
                assert lifecycle_columns.isdisjoint(
                    {column["name"] for column in schema.get_columns("users")}
                )
                assert {"provider_portal_setup_tokens", "provider_invitations", "users"} <= set(
                    schema.get_table_names()
                )
                migration.upgrade()
                schema = inspect(connection)
                assert "provider_portal_recovery_tokens" in schema.get_table_names()
                columns = {column["name"]: column for column in schema.get_columns("users")}
                assert lifecycle_columns <= columns.keys()
                assert columns["provider_portal_approval_pending"]["nullable"] is False
                assert "false" in columns["provider_portal_approval_pending"]["default"]
                purpose_check = next(
                    constraint["sqltext"]
                    for constraint in schema.get_check_constraints("email_delivery_logs")
                    if constraint["name"] == "ck_email_delivery_logs_purpose"
                )
                assert "provider_approval" in purpose_check
                assert "provider_portal_recovery" in purpose_check
        finally:
            transaction.rollback()