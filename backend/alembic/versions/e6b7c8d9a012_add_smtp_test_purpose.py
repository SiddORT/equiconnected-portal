"""Allow SMTP test delivery history.

Revision ID: e6b7c8d9a012
Revises: c2d4e6f8a901
"""
from alembic import op

revision = "e6b7c8d9a012"
down_revision = "c2d4e6f8a901"
branch_labels = None
depends_on = None

_old = ("'provider_invitation', 'account_verification', "
        "'provider_portal_access', 'subscriber_confirmation'")
_new = _old + ", 'smtp_test'"


def upgrade() -> None:
    op.drop_constraint("ck_email_delivery_logs_purpose", "email_delivery_logs", type_="check")
    op.create_check_constraint("ck_email_delivery_logs_purpose", "email_delivery_logs",
                               f"purpose IN ({_new})")


def downgrade() -> None:
    # PostgreSQL will reject this constraint while SMTP test history exists;
    # preserve history rather than deleting it implicitly.
    op.drop_constraint("ck_email_delivery_logs_purpose", "email_delivery_logs", type_="check")
    op.create_check_constraint("ck_email_delivery_logs_purpose", "email_delivery_logs",
                               f"purpose IN ({_old})")