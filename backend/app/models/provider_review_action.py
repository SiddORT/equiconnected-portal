"""Attributable, append-only action history for provider reviews."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.contact_types import (
    ContactSnapshotJSON,
    contact_index_column,
    contact_text_column,
    protect_model_contacts,
)


class ProviderReviewAction(Base):
    __tablename__ = "provider_review_actions"
    __table_args__ = (
        Index("ix_provider_review_actions_review_created", "review_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_reviews.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_email: Mapped[str] = contact_text_column(
        "actor_email", nullable=False
    )
    _actor_email_blind_index: Mapped[str] = contact_index_column(
        "actor_email", nullable=False
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_snapshot: Mapped[dict] = mapped_column(
        ContactSnapshotJSON("content_snapshot"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    review: Mapped["ProviderReview"] = relationship(back_populates="actions")
    actor: Mapped["User | None"] = relationship("User")


protect_model_contacts(
    ProviderReviewAction,
    fields=("actor_email",),
    snapshots=("content_snapshot",),
)