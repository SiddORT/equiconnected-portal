"""Persistence and transaction helpers for platform feedback and member history."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models.enums import (
    MemberFeedbackCategory,
    MemberFeedbackStatus,
    ProviderStatus,
    PublicationStatus,
)
from app.models.member_feedback import MemberFeedback, MemberFeedbackAction
from app.models.member_history import MemberBrowsingHistory
from app.models.provider import Provider
from app.models.user import User
from app.repositories import page_filtered_candidates
from app.db.contact_types import prepare_contact_values


def _safe_human_name(user: User, *, fallback: str = "Account holder") -> str:
    """Build a historical display name without falling back to the user's email."""
    name = " ".join(
        part.strip()
        for part in (user.first_name, user.last_name)
        if part and part.strip()
    )
    return name[:200] or fallback


class MemberFeedbackRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        member: User,
        category: MemberFeedbackCategory,
        subject: str | None,
        rating: int | None,
        message: str,
        idempotency_key: UUID,
    ) -> tuple[MemberFeedback, bool]:
        now = datetime.now(timezone.utc)
        feedback_id = uuid4()
        values = dict(
            id=feedback_id,
            member_id=member.id,
            submitter_name=_safe_human_name(member, fallback="Member"),
            idempotency_key=idempotency_key,
            category=category,
            subject=subject,
            rating=rating,
            message=message,
            status=MemberFeedbackStatus.PENDING,
            submitted_at=now,
            created_at=now,
            updated_at=now,
            version=1,
        )
        values.update(
            prepare_contact_values(
                MemberFeedback,
                str(feedback_id),
                {"submitter_email": member.email[:254]},
            )
        )
        statement = insert(MemberFeedback).values(values)
        inserted_id = self.db.scalar(
            statement.on_conflict_do_nothing(
                constraint="uq_member_feedback_member_idempotency"
            ).returning(MemberFeedback.id)
        )
        created = inserted_id is not None
        feedback = self.by_idempotency(member.id, idempotency_key) if not created else self.get(inserted_id)
        assert feedback is not None
        return feedback, created

    def by_idempotency(self, member_id: UUID, key: UUID) -> MemberFeedback | None:
        return self.db.scalar(
            select(MemberFeedback).where(
                MemberFeedback.member_id == member_id,
                MemberFeedback.idempotency_key == key,
            )
        )

    def get(self, feedback_id: UUID, *, lock: bool = False) -> MemberFeedback | None:
        stmt = select(MemberFeedback).where(MemberFeedback.id == feedback_id)
        if lock:
            stmt = stmt.with_for_update(of=MemberFeedback)
        return self.db.scalar(stmt)

    def get_member(self, feedback_id: UUID, member_id: UUID, *, lock: bool = False):
        stmt = select(MemberFeedback).where(
            MemberFeedback.id == feedback_id,
            MemberFeedback.member_id == member_id,
        )
        if lock:
            stmt = stmt.with_for_update(of=MemberFeedback)
        return self.db.scalar(stmt)

    def list_member(
        self, *, member_id: UUID, status: MemberFeedbackStatus | None, page: int, page_size: int
    ) -> tuple[list[MemberFeedback], int]:
        conditions = [
            MemberFeedback.member_id == member_id,
            MemberFeedback.withdrawn_at.is_(None),
        ]
        if status is not None:
            conditions.append(MemberFeedback.status == status)
        total = self.db.scalar(
            select(func.count()).select_from(MemberFeedback).where(*conditions)
        ) or 0
        items = list(
            self.db.scalars(
                select(MemberFeedback)
                .where(*conditions)
                .order_by(MemberFeedback.submitted_at.desc(), MemberFeedback.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def member_counts(self, member_id: UUID) -> dict[str, int]:
        rows = self.db.execute(
            select(MemberFeedback.status, func.count(MemberFeedback.id))
            .where(MemberFeedback.member_id == member_id, MemberFeedback.withdrawn_at.is_(None))
            .group_by(MemberFeedback.status)
        ).all()
        result = {
            "total": 0,
            "pending": 0,
            "in_review": 0,
            "resolved": 0,
            "rejected": 0,
        }
        key_by_status = {
            MemberFeedbackStatus.PENDING: "pending",
            MemberFeedbackStatus.IN_REVIEW: "in_review",
            MemberFeedbackStatus.RESOLVED: "resolved",
            MemberFeedbackStatus.REJECTED: "rejected",
        }
        for status, count in rows:
            result[key_by_status[status]] = count
            result["total"] += count
        return result

    def list_admin(
        self,
        *,
        status: MemberFeedbackStatus | Literal["withdrawn"] | None,
        category: MemberFeedbackCategory | None,
        query: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[MemberFeedback], int]:
        conditions = []
        if status == "withdrawn":
            conditions.append(MemberFeedback.withdrawn_at.is_not(None))
        elif status is not None:
            conditions.append(MemberFeedback.status == status)
        if category is not None:
            conditions.append(MemberFeedback.category == category)
        search_term = query.strip().lower() if query else ""
        statement = (
            select(MemberFeedback)
            .where(*conditions)
            .order_by(MemberFeedback.submitted_at.desc(), MemberFeedback.id.desc())
        )
        if search_term:
            return page_filtered_candidates(
                self.db.scalars(statement.execution_options(yield_per=250)),
                lambda feedback: (
                    search_term in (feedback.submitter_name or "").lower()
                    or search_term in (feedback.submitter_email or "").lower()
                    or search_term in (feedback.subject or "").lower()
                    or search_term in (feedback.message or "").lower()
                ),
                page=page,
                page_size=page_size,
            )
        total = self.db.scalar(
            select(func.count()).select_from(MemberFeedback).where(*conditions)
        ) or 0
        items = list(
            self.db.scalars(
                statement
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def detail(self, feedback_id: UUID) -> MemberFeedback | None:
        return self.db.scalar(
            select(MemberFeedback)
            .where(MemberFeedback.id == feedback_id)
            .options(selectinload(MemberFeedback.actions))
        )

    def add_action(
        self,
        feedback: MemberFeedback,
        *,
        actor: User,
        actor_type: str,
        action: str,
        from_status: MemberFeedbackStatus | None,
        to_status: MemberFeedbackStatus | None,
    ) -> MemberFeedbackAction:
        item = MemberFeedbackAction(
            feedback_id=feedback.id,
            actor_id=actor.id,
            actor_name=_safe_human_name(actor),
            actor_email=actor.email[:254],
            actor_type=actor_type,
            action=action,
            from_status=from_status,
            to_status=to_status,
            version=feedback.version,
            content_snapshot={
            "category": feedback.category.value if hasattr(feedback.category, "value") else feedback.category,
                "subject": feedback.subject,
                "rating": feedback.rating,
                "message": feedback.message,
                "status": feedback.status.value if hasattr(feedback.status, "value") else feedback.status,
                "member_response": feedback.member_response,
                "internal_note": feedback.internal_note,
                "withdrawn_at": feedback.withdrawn_at.isoformat() if feedback.withdrawn_at else None,
            },
        )
        self.db.add(item)
        return item

    def append_history(
        self,
        *,
        member_id: UUID,
        event_key: str,
        event_type: str,
        provider_id: UUID | None,
        provider_name: str | None,
        filters: dict | None,
    ) -> tuple[MemberBrowsingHistory, bool]:
        now = datetime.now(timezone.utc)
        statement = insert(MemberBrowsingHistory).values(
            id=uuid4(),
            member_id=member_id,
            event_key=event_key,
            event_type=event_type,
            provider_id=provider_id,
            provider_name=provider_name,
            filters=filters,
            occurred_at=now,
        )
        inserted_id = self.db.scalar(
            statement.on_conflict_do_nothing(
                constraint="uq_member_history_member_event_key"
            ).returning(MemberBrowsingHistory.id)
        )
        if inserted_id is not None:
            return self.db.get(MemberBrowsingHistory, inserted_id), True
        existing = self.db.scalar(
            select(MemberBrowsingHistory).where(
                MemberBrowsingHistory.member_id == member_id,
                MemberBrowsingHistory.event_key == event_key,
            )
        )
        assert existing is not None
        return existing, False

    def get_history_event(
        self, *, member_id: UUID, event_key: str
    ) -> MemberBrowsingHistory | None:
        return self.db.scalar(
            select(MemberBrowsingHistory).where(
                MemberBrowsingHistory.member_id == member_id,
                MemberBrowsingHistory.event_key == event_key,
            )
        )

    def list_history(
        self, *, member_id: UUID, page: int, page_size: int
    ) -> tuple[list[MemberBrowsingHistory], int]:
        total = self.db.scalar(
            select(func.count()).select_from(MemberBrowsingHistory).where(
                MemberBrowsingHistory.member_id == member_id
            )
        ) or 0
        items = list(
            self.db.scalars(
                select(MemberBrowsingHistory)
                .where(MemberBrowsingHistory.member_id == member_id)
                .order_by(MemberBrowsingHistory.occurred_at.desc(), MemberBrowsingHistory.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def recent_history(self, *, member_id: UUID, limit: int) -> list[MemberBrowsingHistory]:
        return list(
            self.db.scalars(
                select(MemberBrowsingHistory)
                .where(MemberBrowsingHistory.member_id == member_id)
                .order_by(MemberBrowsingHistory.occurred_at.desc(), MemberBrowsingHistory.id.desc())
                .limit(limit)
            ).all()
        )

    def provider_availability(self, provider_id: UUID | None) -> bool:
        if provider_id is None:
            return False
        return self.db.scalar(
            select(Provider.id).where(
                Provider.id == provider_id,
                Provider.status == ProviderStatus.ACTIVE,
                Provider.publication_status == PublicationStatus.PUBLISHED,
            )
        ) is not None

    def commit(self) -> None:
        self.db.commit()