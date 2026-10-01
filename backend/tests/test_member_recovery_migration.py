"""Sibling email-purpose migrations must converge without dropping features."""
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select
from app.models.email_delivery_log import EmailDeliveryLog

from tests.conftest import engine


def _migration(filename):
    path = Path(__file__).parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(filename, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("recovery_first", [True, False])
@pytest.mark.parametrize("populated", [True, False])
def test_member_recovery_merge_preserves_both_email_purposes(recovery_first, populated):
    recovery = _migration("a7f9c2d63184_member_password_recovery.py")
    messaging = _migration("4f8a2c1d6e90_add_private_provider_messaging.py")
    insights = _migration("d353c0353201_add_provider_performance_insights.py")
    merge = _migration("e352d353a901_merge_member_recovery_and_provider_.py")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                insights.downgrade()
                recovery.downgrade()
                messaging.downgrade()
                if recovery_first:
                    recovery.upgrade()
                    existing_purposes = ("member_password_recovery",)
                else:
                    messaging.upgrade()
                    insights.upgrade()
                    existing_purposes = (
                        "messaging_member_acknowledgement",
                        "messaging_provider_new_message", "messaging_member_reply",
                    )
                expected = []
                if populated:
                    expected = [{
                        "id": uuid4(), "recipient_email": "migration-fixture@example.test",
                        "purpose": purpose, "status": status,
                        "failure_message": "Safe fixture failure" if status == "failed" else None,
                        "created_at": datetime.now(timezone.utc),
                    } for purpose in existing_purposes for status in ("pending", "success", "failed")]
                    connection.execute(EmailDeliveryLog.__table__.insert(), expected)
                if recovery_first:
                    messaging.upgrade()
                    insights.upgrade()
                else:
                    recovery.upgrade()
                merge.upgrade()
                for expected_row in expected:
                    actual = connection.execute(select(EmailDeliveryLog.__table__).where(
                        EmailDeliveryLog.id == expected_row["id"]
                    )).mappings().one()
                    assert dict(actual) == expected_row
                constraints = inspect(connection).get_check_constraints("email_delivery_logs")
                purpose = next(item["sqltext"] for item in constraints
                               if item["name"] == "ck_email_delivery_logs_purpose")
                for name in (
                    "member_password_recovery", "messaging_member_acknowledgement",
                    "messaging_provider_new_message", "messaging_member_reply",
                ):
                    assert name in purpose
                assert {"member_password_recovery_tokens", "provider_conversations",
                        "provider_messages", "provider_contact_click_daily"} <= set(
                            inspect(connection).get_table_names()
                        )
        finally:
            transaction.rollback()