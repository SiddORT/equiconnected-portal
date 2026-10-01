"""Private member-to-platform feedback and attributable action history."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import TimestampMixin
from app.models.enums import MemberFeedbackCategory, MemberFeedbackStatus


class MemberFeedback(TimestampMixin, Base):
    """Private platform feedback submitted by a member."""

    __tablename__ = "member_feedback"
    __table_args__ = (
        CheckConstraint(
            "category IN ('Website / App', 'Search & Matching', 'Provider Experience', "
            "'Account / Profile', 'Technical Issue', 'Suggestion', 'Other')",
            name="ck_member_feedback_category",
        ),
        CheckConstraint(
            "status IN ('Pending', 'In review', 'Resolved', 'Rejected')",
            name="ck_member_feedback_status",
        ),
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="ck_member_feedback_rating"),
        CheckConstraint("version >= 1", name="ck_member_feedback_version"),
        UniqueConstraint("member_id", "idempotency_key", name="uq_member_feedback_member_idempotency"),
        Index("ix_member_feedback_status_submitted", "status", "submitted_at"),
        Index("ix_member_feedback_member_submitted", "member_id", "submitted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitter_name: Mapped[str] = mapped_column(String(200), nullable=False)
    submitter_email: Mapped[str] = mapped_column(String(254), nullable=False)
    idempotency_key: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    category: Mapped[MemberFeedbackCategory] = mapped_column(String(40), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MemberFeedbackStatus] = mapped_column(
        String(20), nullable=False, default=MemberFeedbackStatus.PENDING,
        server_default=MemberFeedbackStatus.PENDING.value,
    )
    member_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    actions: Mapped[list["MemberFeedbackAction"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan",
        order_by="MemberFeedbackAction.created_at",
    )


class MemberFeedbackAction(Base):
    """Immutable action and content snapshots for authorized feedback review."""

    __tablename__ = "member_feedback_actions"
    __table_args__ = (
        Index("ix_member_feedback_actions_feedback_created", "feedback_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feedback_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("member_feedback.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_email: Mapped[str] = mapped_column(String(254), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[MemberFeedbackStatus | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[MemberFeedbackStatus | None] = mapped_column(String(20), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    feedback: Mapped[MemberFeedback] = relationship(back_populates="actions")
