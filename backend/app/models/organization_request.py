"""Requests from invited doctors for an organization not yet in the catalogue."""
import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import TimestampMixin
from app.models.enums import OrganizationRequestStatus, ProviderType


class OrganizationRequest(TimestampMixin, Base):
    __tablename__ = "organization_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    organization_name: Mapped[str] = mapped_column(String(300), nullable=False)
    organization_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", native_enum=True), nullable=False
    )
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    location_hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[OrganizationRequestStatus] = mapped_column(
        Enum(OrganizationRequestStatus, name="organization_request_status", native_enum=True),
        nullable=False,
        default=OrganizationRequestStatus.PENDING,
        server_default=OrganizationRequestStatus.PENDING.value,
    )

    __table_args__ = (
        CheckConstraint(
            "organization_type IN ('HOSPITAL', 'CLINIC')",
            name="ck_organization_request_type",
        ),
        Index("ix_organization_requests_doctor_provider_id", "doctor_provider_id"),
        Index("ix_organization_requests_status", "status"),
        Index("ix_organization_requests_organization_type", "organization_type"),
    )