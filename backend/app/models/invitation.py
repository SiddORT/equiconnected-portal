"""Provider invitation persistence model. Invitation tokens are never stored raw."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import TimestampMixin
from app.models.enums import InvitationStatus, ProviderType


class ProviderInvitation(TimestampMixin, Base):
    __tablename__ = "provider_invitations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", native_enum=True), nullable=False
    )
    recipient_email: Mapped[str] = mapped_column(String(254), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus, name="invitation_status", native_enum=True),
        nullable=False,
        default=InvitationStatus.PENDING,
        server_default=InvitationStatus.PENDING.value,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        Index("ix_provider_invitations_provider_email", "provider_id", "recipient_email"),
        Index(
            "uq_provider_invitations_active_provider_email",
            "provider_id",
            "recipient_email",
            unique=True,
            postgresql_where=status.in_(
                [InvitationStatus.PENDING, InvitationStatus.ACCEPTED]
            ),
        ),
        Index("ix_provider_invitations_status", "status"),
        Index("ix_provider_invitations_expires_at", "expires_at"),
    )