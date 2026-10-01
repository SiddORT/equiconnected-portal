"""Persisted public contact enquiries."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.db.contact_types import (
    contact_index_column,
    contact_text_column,
    protect_model_contacts,
)


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
    email: Mapped[str] = contact_text_column("email", nullable=False)
    _email_blind_index: Mapped[str] = contact_index_column(
        "email", nullable=False
    )
    enquiry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    phone: Mapped[str | None] = contact_text_column("phone", nullable=True)
    _phone_blind_index: Mapped[str | None] = contact_index_column("phone")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


protect_model_contacts(ContactEnquiry, fields=("email", "phone"))