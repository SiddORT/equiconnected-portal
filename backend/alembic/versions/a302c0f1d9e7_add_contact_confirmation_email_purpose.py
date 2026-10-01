"""Allow distinct contact confirmation email delivery history.

Revision ID: a302c0f1d9e7
Revises: d9a4f13b7c20
"""
from alembic import op
import sqlalchemy as sa


revision = "a302c0f1d9e7"
down_revision = "d9a4f13b7c20"
branch_labels = None
depends_on = None


_PURPOSES = (
    "'provider_invitation', 'account_verification', "
    "'provider_portal_access', 'subscriber_confirmation', "
    "'contact_notification', 'contact_confirmation', 'smtp_test'"
)
_PREVIOUS_PURPOSES = (
    "'provider_invitation', 'account_verification', "
    "'provider_portal_access', 'subscriber_confirmation', "
    "'contact_notification', 'smtp_test'"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        f"purpose IN ({_PURPOSES})",
    )


def downgrade() -> None:
    # Refuse to remove support for the new purpose while audit rows use it.
    # Keep the existing constraint and records intact on a failed downgrade.
    has_contact_confirmation_rows = op.get_bind().execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM email_delivery_logs "
            "WHERE purpose = :purpose"
            ")"
        ),
        {"purpose": "contact_confirmation"},
    ).scalar_one()
    if has_contact_confirmation_rows:
        raise RuntimeError(
            "Cannot downgrade email purpose constraint while "
            "contact_confirmation email delivery log rows exist."
        )

    op.drop_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        f"purpose IN ({_PREVIOUS_PURPOSES})",
    )