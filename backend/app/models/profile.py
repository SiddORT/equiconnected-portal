"""Member-owned stable and horse profile models."""
import uuid

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.contact_types import (
    contact_index_column,
    contact_text_column,
    protect_model_contacts,
)
from app.models.base import TimestampMixin


class LocationCoordinates:
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)


def coordinate_constraint(table: str) -> CheckConstraint:
    return CheckConstraint(
        "(latitude IS NULL AND longitude IS NULL) OR "
        "(latitude IS NOT NULL AND longitude IS NOT NULL "
        "AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
        name=f"ck_{table}_coordinates",
    )


class StableProfile(LocationCoordinates, TimestampMixin, Base):
    __tablename__ = "stable_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = contact_text_column(
        "contact_phone", nullable=True
    )
    _contact_phone_blind_index: Mapped[str | None] = contact_index_column(
        "contact_phone"
    )
    contact_email: Mapped[str | None] = contact_text_column(
        "contact_email", nullable=True
    )
    _contact_email_blind_index: Mapped[str | None] = contact_index_column(
        "contact_email"
    )

    user: Mapped["User"] = relationship("User", back_populates="stable_profile")

    __table_args__ = (Index("ix_stable_profiles_user_id", "user_id"), coordinate_constraint("stable_profiles"))


protect_model_contacts(
    StableProfile,
    fields=("contact_email", "contact_phone"),
)


class Horse(LocationCoordinates, TimestampMixin, Base):
    __tablename__ = "horses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sex: Mapped[str] = mapped_column(String(24), nullable=False)
    registered_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    breed: Mapped[str | None] = mapped_column(String(120), nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(String(10), nullable=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    primary_discipline: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    microchip_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="custom", server_default="custom")
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="horses")

    @property
    def effective_location(self) -> dict:
        source = self.user.stable_profile if self.location_mode == "stable" else self
        fields = ("address", "address_line_2", "country", "state_province", "city", "postal_code", "latitude", "longitude")
        location = {field: getattr(source, field, None) for field in fields}
        available = location["latitude"] is not None and location["longitude"] is not None
        reason = None
        if source is None:
            reason = "Save stable details and coordinates in Stable Info first."
        elif not available:
            reason = "Add both latitude and longitude in Stable Info." if self.location_mode == "stable" else "Add both latitude and longitude in Horse Info."
        return {**location, "available": available, "reason": reason}

    __table_args__ = (
        Index("ix_horses_user_id", "user_id"),
        coordinate_constraint("horses"),
        CheckConstraint("location_mode IN ('custom', 'stable')", name="ck_horses_location_mode"),
    )