"""Provider-account registration applications and their review lifecycle."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Integer, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import TimestampMixin
from app.models.enums import ProviderApplicationStatus, ProviderType, VisitStability


class ProviderRegistrationApplication(TimestampMixin, Base):
    """One provider account application per user and, once approved, provider listing."""

    __tablename__ = "provider_registration_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", native_enum=True), nullable=False
    )
    provider_name: Mapped[str] = mapped_column(String(300), nullable=False)
    visit_stability: Mapped[VisitStability] = mapped_column(
        Enum(VisitStability, name="visit_stability", native_enum=True), nullable=False
    )
    professional_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specialization_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    working_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stable_visit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    clinic_hospital_visit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    maximum_working_radius_km: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    emergency_services_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    emergency_contact_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_status: Mapped[ProviderApplicationStatus] = mapped_column(
        Enum(
            ProviderApplicationStatus,
            name="provider_application_status",
            native_enum=True,
        ),
        nullable=False,
        default=ProviderApplicationStatus.AWAITING_EMAIL_VERIFICATION,
        server_default=ProviderApplicationStatus.AWAITING_EMAIL_VERIFICATION.value,
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[user_id], back_populates="provider_registration_application"
    )
    reviewer: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[reviewed_by_user_id]
    )
    provider: Mapped["Provider | None"] = relationship(  # noqa: F821
        "Provider", back_populates="provider_registration_application"
    )

    __table_args__ = (
        Index(
            "ix_provider_registration_applications_review_status",
            "review_status",
            "created_at",
        ),
        Index(
            "ix_provider_registration_applications_provider_type",
            "provider_type",
        ),
    )