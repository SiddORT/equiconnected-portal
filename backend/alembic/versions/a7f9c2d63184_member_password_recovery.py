"""add member-only password recovery tokens and mail purpose

Revision ID: a7f9c2d63184
Revises: c2f4a8d17e60
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7f9c2d63184"
down_revision: Union[str, None] = "c2f4a8d17e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "member_password_recovery_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_member_password_recovery_tokens_user_id",
        "member_password_recovery_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_member_password_recovery_tokens_user_active",
        "member_password_recovery_tokens",
        ["user_id", "used_at"],
    )
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
    # New-purpose delivery history cannot satisfy the previous constraint.
    op.execute(
        "DELETE FROM email_delivery_logs WHERE purpose = 'member_password_recovery'"
    )
    op.drop_constraint(
        "ck_email_delivery_logs_purpose", "email_delivery_logs", type_="check"
    )
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        "purpose IN ('provider_invitation', 'account_verification', "
        "'provider_portal_access', 'provider_portal_recovery', "
        "'provider_approval', 'subscriber_confirmation', "
        "'contact_notification', 'contact_confirmation', 'smtp_test', "
        "'messaging_member_acknowledgement', 'messaging_provider_new_message', "
        "'messaging_member_reply')",
    )
    op.drop_index(
        "ix_member_password_recovery_tokens_user_active",
        table_name="member_password_recovery_tokens",
    )
    op.drop_index(
        "ix_member_password_recovery_tokens_user_id",
        table_name="member_password_recovery_tokens",
    )
    op.drop_table("member_password_recovery_tokens")