"""
Doctor domain models — extend the Provider foundation.

Tables:
  doctor_profiles       — 1:1 extension of providers for doctor-specific fields
  doctor_qualifications — 1:many qualifications per doctor
  doctor_organizations  — M:M junction between a doctor and their hospital/clinic affiliations
"""
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import TimestampMixin
from app.models.enums import DoctorOrganizationStatus


class DoctorProfile(TimestampMixin, Base):
    """
    One-to-one extension of the Provider table for Doctor-specific profile fields.
    The provider_id is both PK and FK so each Provider has at most one profile row.
    """
    __tablename__ = "doctor_profiles"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    professional_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experience_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Back-reference to the parent Provider
    provider: Mapped["app.models.provider.Provider"] = relationship(  # type: ignore[name-defined]
        "Provider", back_populates="doctor_profile"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DoctorProfile provider_id={self.provider_id} title={self.professional_title!r}>"


class DoctorQualification(TimestampMixin, Base):
    """
    One doctor may have many qualifications (MBBS, MD, Fellowship, etc.).
    Each row is a separate relational record — no JSON storage.
    """
    __tablename__ = "doctor_qualifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year_obtained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    provider: Mapped["app.models.provider.Provider"] = relationship(  # type: ignore[name-defined]
        "Provider", back_populates="qualifications"
    )

    __table_args__ = (
        Index("ix_doctor_qualifications_provider_id", "provider_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DoctorQualification id={self.id} title={self.title!r}>"


class DoctorOrganization(TimestampMixin, Base):
    """
    Many-to-many junction between a Doctor provider and a Hospital/Clinic provider.

    Constraints:
      - UNIQUE(doctor_id, organization_id) — one row per doctor-org pair
      - Partial UNIQUE on doctor_id WHERE is_primary=True — only one primary org per doctor
      - CHECK: doctor_id != organization_id (a doctor cannot affiliate with itself)
    """
    __tablename__ = "doctor_organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[DoctorOrganizationStatus] = mapped_column(
        Enum(DoctorOrganizationStatus, name="doctor_organization_status", native_enum=True),
        nullable=False,
        default=DoctorOrganizationStatus.ACTIVE,
        server_default=DoctorOrganizationStatus.ACTIVE.value,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    doctor: Mapped["app.models.provider.Provider"] = relationship(  # type: ignore[name-defined]
        "Provider",
        foreign_keys=[doctor_id],
        back_populates="doctor_organizations",
    )
    organization: Mapped["app.models.provider.Provider"] = relationship(  # type: ignore[name-defined]
        "Provider",
        foreign_keys=[organization_id],
        back_populates="organization_doctors",
    )

    __table_args__ = (
        UniqueConstraint("doctor_id", "organization_id", name="uq_doctor_organizations_pair"),
        # Only one primary org per doctor (partial unique index)
        Index(
            "uq_doctor_organizations_one_primary",
            "doctor_id",
            unique=True,
            postgresql_where=(is_primary.is_(True)),
        ),
        Index("ix_doctor_organizations_doctor_id", "doctor_id"),
        Index("ix_doctor_organizations_organization_id", "organization_id"),
        CheckConstraint("doctor_id != organization_id", name="ck_doctor_org_no_self"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DoctorOrganization doctor={self.doctor_id} org={self.organization_id}"
            f" status={self.status.value} primary={self.is_primary}>"
        )
