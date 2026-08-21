"""
Provider domain models: providers, provider_locations, provider_photos,
and the provider_specializations association table.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import TimestampMixin
from app.models.enums import (
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    ProviderProfileUpdateStatus,
    VisitStability,
)


class Provider(TimestampMixin, Base):
    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", native_enum=True),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    visit_stability: Mapped[VisitStability] = mapped_column(
        Enum(VisitStability, name="visit_stability", native_enum=True),
        nullable=False,
    )
    status: Mapped[ProviderStatus] = mapped_column(
        Enum(ProviderStatus, name="provider_status", native_enum=True),
        nullable=False,
        default=ProviderStatus.ACTIVE,
        server_default=ProviderStatus.ACTIVE.value,
    )
    publication_status: Mapped[PublicationStatus] = mapped_column(
        Enum(PublicationStatus, name="publication_status", native_enum=True),
        nullable=False,
        default=PublicationStatus.UNPUBLISHED,
        server_default=PublicationStatus.UNPUBLISHED.value,
    )

    locations: Mapped[list["ProviderLocation"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )
    photos: Mapped[list["ProviderPhoto"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )
    provider_specializations: Mapped[list["ProviderSpecialization"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )
    phones: Mapped[list["ProviderPhone"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )
    emails: Mapped[list["ProviderEmail"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["ProviderReview"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )
    provider_registration_application: Mapped["ProviderRegistrationApplication | None"] = relationship(  # noqa: F821
        "ProviderRegistrationApplication", back_populates="provider", uselist=False
    )
    profile_update: Mapped["ProviderProfileUpdate | None"] = relationship(  # noqa: F821
        "ProviderProfileUpdate",
        back_populates="provider",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # ── Doctor extensions (populated only when provider_type == DOCTOR) ────────
    doctor_profile: Mapped["app.models.doctor.DoctorProfile | None"] = relationship(  # type: ignore[name-defined]
        "DoctorProfile",
        back_populates="provider",
        cascade="all, delete-orphan",
        uselist=False,
    )
    qualifications: Mapped[list["app.models.doctor.DoctorQualification"]] = relationship(  # type: ignore[name-defined]
        "DoctorQualification",
        back_populates="provider",
        cascade="all, delete-orphan",
        order_by="DoctorQualification.display_order, DoctorQualification.created_at",
    )
    # Relationships where this provider is the DOCTOR side
    doctor_organizations: Mapped[list["app.models.doctor.DoctorOrganization"]] = relationship(  # type: ignore[name-defined]
        "DoctorOrganization",
        foreign_keys="DoctorOrganization.doctor_id",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
    # Relationships where this provider is the ORGANIZATION side
    organization_doctors: Mapped[list["app.models.doctor.DoctorOrganization"]] = relationship(  # type: ignore[name-defined]
        "DoctorOrganization",
        foreign_keys="DoctorOrganization.organization_id",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_providers_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<Provider id={self.id} type={self.provider_type} name={self.name!r}>"


class ProviderReview(TimestampMixin, Base):
    """One member-owned rating and optional comment for a directory provider."""

    __tablename__ = "provider_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    comment_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    provider: Mapped["Provider"] = relationship(back_populates="reviews")
    member: Mapped["User"] = relationship(back_populates="provider_reviews")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_provider_reviews_rating"),
        UniqueConstraint(
            "provider_id", "member_id", name="uq_provider_reviews_provider_member"
        ),
        Index("ix_provider_reviews_provider_id", "provider_id"),
        Index("ix_provider_reviews_comment_visible", "comment_visible"),
        Index("ix_provider_reviews_created_at", "created_at"),
    )


class ProviderProfileUpdate(TimestampMixin, Base):
    """One private, reviewable profile snapshot for a published provider."""

    __tablename__ = "provider_profile_updates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    proposed_profile: Mapped[dict] = mapped_column(JSONB, nullable=False)
    base_profile: Mapped[dict] = mapped_column(JSONB, nullable=False)
    review_status: Mapped[ProviderProfileUpdateStatus] = mapped_column(
        Enum(
            ProviderProfileUpdateStatus,
            name="provider_profile_update_status",
            native_enum=True,
        ),
        nullable=False,
        default=ProviderProfileUpdateStatus.PENDING_REVIEW,
        server_default=ProviderProfileUpdateStatus.PENDING_REVIEW.value,
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    provider: Mapped["Provider"] = relationship(back_populates="profile_update")
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by_user_id])

    __table_args__ = (
        Index("ix_provider_profile_updates_review_status", "review_status", "submitted_at"),
    )


class ProviderPhone(TimestampMixin, Base):
    __tablename__ = "provider_phones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    country_code: Mapped[str] = mapped_column(String(10), nullable=False)
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    provider: Mapped["Provider"] = relationship(back_populates="phones")

    __table_args__ = (
        Index("ix_provider_phones_provider_id", "provider_id"),
        # Only one primary phone per provider — enforced by the database itself.
        Index(
            "uq_provider_phones_one_primary",
            "provider_id",
            unique=True,
            postgresql_where=(is_primary.is_(True)),
        ),
    )

    def __repr__(self) -> str:
        return f"<ProviderPhone id={self.id} provider_id={self.provider_id} number={self.country_code}{self.number}>"


class ProviderEmail(TimestampMixin, Base):
    __tablename__ = "provider_emails"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    provider: Mapped["Provider"] = relationship(back_populates="emails")

    __table_args__ = (
        Index("ix_provider_emails_provider_id", "provider_id"),
        # Only one primary email per provider — enforced by the database itself.
        Index(
            "uq_provider_emails_one_primary",
            "provider_id",
            unique=True,
            postgresql_where=(is_primary.is_(True)),
        ),
    )

    def __repr__(self) -> str:
        return f"<ProviderEmail id={self.id} provider_id={self.provider_id} email={self.email!r}>"


class ProviderLocation(TimestampMixin, Base):
    __tablename__ = "provider_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line_1: Mapped[str] = mapped_column(String(300), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str] = mapped_column(String(150), nullable=False)
    state_province: Mapped[str | None] = mapped_column(String(150), nullable=True)
    country: Mapped[str | None] = mapped_column(String(150), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    provider: Mapped["Provider"] = relationship(back_populates="locations")

    __table_args__ = (
        Index("ix_provider_locations_provider_id", "provider_id"),
        # Only one primary location per provider — enforced by the database itself.
        Index(
            "uq_provider_locations_one_primary",
            "provider_id",
            unique=True,
            postgresql_where=(is_primary.is_(True)),
        ),
    )

    def __repr__(self) -> str:
        return f"<ProviderLocation id={self.id} provider_id={self.provider_id} city={self.city!r}>"


class ProviderPhoto(TimestampMixin, Base):
    __tablename__ = "provider_photos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_thumbnail: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    provider: Mapped["Provider"] = relationship(back_populates="photos")

    __table_args__ = (
        Index("ix_provider_photos_provider_id", "provider_id"),
        # Only one thumbnail per provider — enforced by the database itself.
        Index(
            "uq_provider_photos_one_thumbnail",
            "provider_id",
            unique=True,
            postgresql_where=(is_thumbnail.is_(True)),
        ),
    )

    def __repr__(self) -> str:
        return f"<ProviderPhoto id={self.id} provider_id={self.provider_id} thumb={self.is_thumbnail}>"


class ProviderSpecialization(Base):
    __tablename__ = "provider_specializations"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    specialization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("specializations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    provider: Mapped["Provider"] = relationship(
        back_populates="provider_specializations"
    )
    specialization: Mapped["Specialization"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "specialization_id",
            name="uq_provider_specializations_provider_specialization",
        ),
        Index("ix_provider_specializations_provider_id", "provider_id"),
        Index("ix_provider_specializations_specialization_id", "specialization_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProviderSpecialization provider_id={self.provider_id} "
            f"specialization_id={self.specialization_id}>"
        )


from app.models.specialization import Specialization  # noqa: E402
