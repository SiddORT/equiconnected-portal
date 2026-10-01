"""Persisted public contact enquiries."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ContactEnquiry(Base):
    """A single submission from the public contact form."""

    __tablename__ = "contact_enquiries"
    __table_args__ = (
        CheckConstraint(
            "enquiry_type IN ('general', 'listing', 'partnership', 'other')",
            name="ck_contact_enquiries_enquiry_type",
        ),
        Index("ix_contact_enquiries_submitted_at_id", "submitted_at", "id"),
        Index(
            "ix_contact_enquiries_enquiry_type_submitted_at",
            "enquiry_type",
            "submitted_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    enquiry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )