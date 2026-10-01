"""Privacy-minimal persistence for prospective provider contact insights."""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, Index, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import TimestampMixin


class ProviderContactClickDaily(TimestampMixin, Base):
    """Atomic daily provider/action aggregates with no member or destination."""

    __tablename__ = "provider_contact_click_daily"

    click_date: Mapped[date] = mapped_column(Date, primary_key=True)
    provider_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    action: Mapped[str] = mapped_column(String(16), primary_key=True)
    click_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    __table_args__ = (
        CheckConstraint("click_count >= 0", name="ck_provider_contact_click_count"),
        CheckConstraint(
            "action IN ('phone', 'email', 'website')",
            name="ck_provider_contact_click_action",
        ),
        Index(
            "ix_provider_contact_click_provider_date",
            "provider_id",
            "click_date",
        ),
    )


class ProviderContactClickTrackingMetadata(Base):
    """Independent, persistent contact-tracking rollout boundary."""

    __tablename__ = "provider_contact_click_tracking_metadata"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    tracking_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_provider_contact_tracking_singleton"),
    )


class ProviderInsightsConversationMetadata(Base):
    """Independent boundary for provider insights' conversation reporting."""

    __tablename__ = "provider_insights_conversation_metadata"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    tracking_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_provider_insights_conversation_singleton"),
    )


class ProviderContactClickReceipt(Base):
    """UUIDv7-only retry receipt; it stores no event or member relationship."""

    __tablename__ = "provider_contact_click_receipts"

    event_key: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_provider_contact_click_receipts_expiry", "expires_at"),
    )