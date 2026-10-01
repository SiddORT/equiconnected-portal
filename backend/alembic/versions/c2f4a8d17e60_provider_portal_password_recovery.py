"""add purpose-specific provider portal recovery tokens

Revision ID: c2f4a8d17e60
Revises: ebedc6d4b893
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c2f4a8d17e60"
down_revision: Union[str, None] = "ebedc6d4b893"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Invited accounts that set a password during submission remain gated until
    # explicit approval; the timestamp makes approval-email retries idempotent.
    op.add_column(
        "users",
        sa.Column(
            "provider_portal_approval_pending",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "provider_portal_approval_email_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_table(
        "provider_portal_recovery_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_provider_portal_recovery_tokens_provider_id",
        "provider_portal_recovery_tokens",
        ["provider_id"],
    )
    op.create_index(
        "ix_provider_portal_recovery_tokens_user_id",
        "provider_portal_recovery_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_provider_portal_recovery_tokens_user_active",
        "provider_portal_recovery_tokens",
        ["user_id", "used_at"],
    )
    op.drop_constraint(
        "ck_email_delivery_logs_purpose", "email_delivery_logs", type_="check"
    )
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        "purpose IN ('provider_invitation', 'account_verification', "
        "'provider_portal_access', 'provider_portal_recovery', 'provider_approval', "
        "'subscriber_confirmation', 'contact_notification', "
        "'contact_confirmation', 'smtp_test')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_email_delivery_logs_purpose", "email_delivery_logs", type_="check"
    )
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        "purpose IN ('provider_invitation', 'account_verification', "
        "'provider_portal_access', 'subscriber_confirmation', "
        "'contact_notification', 'contact_confirmation', 'smtp_test')",
    )
    op.drop_index(
        "ix_provider_portal_recovery_tokens_user_active",
        table_name="provider_portal_recovery_tokens",
    )
    op.drop_index(
        "ix_provider_portal_recovery_tokens_user_id",
        table_name="provider_portal_recovery_tokens",
    )
    op.drop_index(
        "ix_provider_portal_recovery_tokens_provider_id",
        table_name="provider_portal_recovery_tokens",
    )
    op.drop_table("provider_portal_recovery_tokens")
    op.drop_column("users", "provider_portal_approval_email_sent_at")
    op.drop_column("users", "provider_portal_approval_pending")