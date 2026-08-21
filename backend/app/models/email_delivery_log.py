"""Safe, durable record of transactional email handoff attempts."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EmailDeliveryLog(Base):
    __tablename__ = "email_delivery_logs"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('provider_invitation', 'account_verification')",
            name="ck_email_delivery_logs_purpose",
        ),
        CheckConstraint(
            "status IN ('pending', 'success', 'failed')",
            name="ck_email_delivery_logs_status",
        ),
        Index("ix_email_delivery_logs_created_at_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
