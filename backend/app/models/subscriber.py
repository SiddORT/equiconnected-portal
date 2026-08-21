"""Public launch-interest registrations."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.enums import SubscriberRegistrationType


class Subscriber(Base):
    """One normalized email identity interested in the EquiConnected launch."""

    __tablename__ = "subscribers"
    __table_args__ = (
        UniqueConstraint("email", name="uq_subscribers_email"),
        CheckConstraint(
            "registration_type IN "
            "('VET', 'HORSE_OWNER', 'HOSPITAL', 'CLINIC', 'STABLE_MANAGER', 'OTHER')",
            name="ck_subscribers_registration_type",
        ),
        Index("ix_subscribers_submitted_at_id", "submitted_at", "id"),
        Index("ix_subscribers_registration_type_submitted_at", "registration_type", "submitted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_type: Mapped[SubscriberRegistrationType] = mapped_column(
        String(30), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )