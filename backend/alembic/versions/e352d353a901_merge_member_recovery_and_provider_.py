"""merge member recovery and provider insights

Revision ID: e352d353a901
Revises: a7f9c2d63184, d353c0353201
Create Date: 2026-10-01 07:32:35.454159

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e352d353a901'
down_revision: Union[str, None] = ('a7f9c2d63184', 'd353c0353201')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both sibling migrations extend the same delivery-purpose constraint.
    # Whichever branch runs last must not exclude the other branch's emails.
    op.drop_constraint(
        "ck_email_delivery_logs_purpose", "email_delivery_logs", type_="check"
    )
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        "purpose IN ('provider_invitation', 'account_verification', "
        "'provider_portal_access', 'provider_portal_recovery', "
        "'member_password_recovery', 'provider_approval', "
        "'subscriber_confirmation', 'contact_notification', "
        "'contact_confirmation', 'smtp_test', "
        "'messaging_member_acknowledgement', 'messaging_provider_new_message', "
        "'messaging_member_reply')",
    )


def downgrade() -> None:
    # Both parents remain applied after splitting this merge. Keep the union
    # until a parent migration itself removes its feature and purpose values.
    pass
