"""Encrypted private provider conversations and durable notification intents."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import TimestampMixin


class ProviderConversation(TimestampMixin, Base):
    __tablename__ = "provider_conversations"
    __table_args__ = (
        UniqueConstraint(
            "member_user_id",
            "provider_id",
            "provider_user_id",
            name="uq_provider_conversations_participants",
        ),
        CheckConstraint("last_sequence >= 0", name="ck_provider_conversations_last_sequence"),
        CheckConstraint(
            "member_read_sequence >= 0 AND provider_read_sequence >= 0",
            name="ck_provider_conversations_read_sequences",
        ),
        Index(
            "ix_provider_conversations_member_activity",
            "member_user_id",
            "last_message_at",
            "id",
        ),
        Index(
            "ix_provider_conversations_provider_activity",
            "provider_user_id",
            "last_message_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    # Immutable owner identity: if ownership changes, history is not transferred.
    provider_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    contact_snapshot_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    contact_consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    member_read_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    provider_read_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProviderMessage(TimestampMixin, Base):
    __tablename__ = "provider_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sequence", name="uq_provider_messages_conversation_sequence"
        ),
        UniqueConstraint(
            "sender_user_id", "request_id", name="uq_provider_messages_sender_request_id"
        ),
        CheckConstraint("sequence >= 1", name="ck_provider_messages_sequence_positive"),
        CheckConstraint(
            "sender_side IN ('member', 'provider')", name="ck_provider_messages_sender_side"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sender_side: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    body_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    member_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MessagingNotificationOutbox(TimestampMixin, Base):
    """Message-free durable work items consumed by the isolated notification worker."""

    __tablename__ = "messaging_notification_outbox"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "recipient_user_id",
            "event_type",
            name="uq_messaging_outbox_message_recipient_event",
        ),
        CheckConstraint(
            "event_type IN ('member_acknowledgement', 'provider_new_message', 'member_reply')",
            name="ck_messaging_outbox_event_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'failed')",
            name="ck_messaging_outbox_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_messaging_outbox_attempt_count"),
        Index("ix_messaging_outbox_dispatch", "status", "available_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_messages.id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Only a short allow-listed failure code belongs here, never raw SMTP errors.
    last_error: Mapped[str | None] = mapped_column(String(80), nullable=True)


class MessagingSendLimit(TimestampMixin, Base):
    """Database-backed account send budget, serialized by locking this row."""

    __tablename__ = "messaging_send_limits"
    __table_args__ = (
        CheckConstraint("send_count >= 0", name="ck_messaging_send_limits_count"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")