"""add private provider conversations and notification outbox

Revision ID: 4f8a2c1d6e90
Revises: c2f4a8d17e60
"""
from alembic import op
import sqlalchemy as sa


revision = "4f8a2c1d6e90"
down_revision = "c2f4a8d17e60"
branch_labels = None
depends_on = None

_BASE_PURPOSES = (
    "'provider_invitation', 'account_verification', 'provider_portal_access', "
    "'provider_portal_recovery', 'provider_approval', 'subscriber_confirmation', "
    "'contact_notification', 'contact_confirmation', 'smtp_test'"
)
_MESSAGING_PURPOSES = (
    _BASE_PURPOSES
    + ", 'messaging_member_acknowledgement', 'messaging_provider_new_message', "
    "'messaging_member_reply'"
)


def upgrade() -> None:
    op.create_table(
        "provider_conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("member_user_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("provider_user_id", sa.UUID(), nullable=False),
        sa.Column("contact_snapshot_ciphertext", sa.Text(), nullable=False),
        sa.Column("contact_consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("member_read_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_read_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "last_sequence >= 0", name="ck_provider_conversations_last_sequence"
        ),
        sa.CheckConstraint(
            "member_read_sequence >= 0 AND provider_read_sequence >= 0",
            name="ck_provider_conversations_read_sequences",
        ),
        sa.ForeignKeyConstraint(["member_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_user_id",
            "provider_id",
            "provider_user_id",
            name="uq_provider_conversations_participants",
        ),
    )
    op.create_index(
        "ix_provider_conversations_member_activity",
        "provider_conversations",
        ["member_user_id", "last_message_at", "id"],
    )
    op.create_index(
        "ix_provider_conversations_provider_activity",
        "provider_conversations",
        ["provider_user_id", "last_message_at", "id"],
    )

    op.create_table(
        "provider_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("sender_user_id", sa.UUID(), nullable=False),
        sa.Column("sender_side", sa.String(length=16), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("body_ciphertext", sa.Text(), nullable=False),
        sa.Column("member_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sequence >= 1", name="ck_provider_messages_sequence_positive"
        ),
        sa.CheckConstraint(
            "sender_side IN ('member', 'provider')",
            name="ck_provider_messages_sender_side",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["provider_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "sequence", name="uq_provider_messages_conversation_sequence"
        ),
        sa.UniqueConstraint(
            "sender_user_id", "request_id", name="uq_provider_messages_sender_request_id"
        ),
    )
    op.create_table(
        "messaging_notification_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("recipient_user_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('member_acknowledgement', 'provider_new_message', 'member_reply')",
            name="ck_messaging_outbox_event_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'failed')",
            name="ck_messaging_outbox_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_messaging_outbox_attempt_count"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["provider_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["message_id"], ["provider_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "recipient_user_id",
            "event_type",
            name="uq_messaging_outbox_message_recipient_event",
        ),
    )
    op.create_index(
        "ix_messaging_outbox_dispatch",
        "messaging_notification_outbox",
        ["status", "available_at", "created_at"],
    )

    op.create_table(
        "messaging_send_limits",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("send_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("send_count >= 0", name="ck_messaging_send_limits_count"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.drop_constraint("ck_email_delivery_logs_purpose", "email_delivery_logs", type_="check")
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        f"purpose IN ({_MESSAGING_PURPOSES})",
    )


def downgrade() -> None:
    # The check intentionally prevents a downgrade that would strand messaging
    # delivery history outside the allowed-purpose contract.
    op.drop_constraint("ck_email_delivery_logs_purpose", "email_delivery_logs", type_="check")
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        f"purpose IN ({_BASE_PURPOSES})",
    )
    op.drop_table("messaging_send_limits")
    op.drop_index("ix_messaging_outbox_dispatch", table_name="messaging_notification_outbox")
    op.drop_table("messaging_notification_outbox")
    op.drop_table("provider_messages")
    op.drop_index(
        "ix_provider_conversations_provider_activity", table_name="provider_conversations"
    )
    op.drop_index(
        "ix_provider_conversations_member_activity", table_name="provider_conversations"
    )
    op.drop_table("provider_conversations")