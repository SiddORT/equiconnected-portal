"""Lifecycle rules for member platform feedback and private browsing history."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.models.enums import (
    MemberFeedbackCategory,
    MemberFeedbackStatus,
    ProviderStatus,
    PublicationStatus,
)
from app.models.member_feedback import MemberFeedback
from app.models.provider import Provider
from app.models.user import User
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.member_feedback_repository import MemberFeedbackRepository


class FeedbackNotFoundError(Exception):
    pass


class FeedbackConflictError(Exception):
    pass


class FeedbackStaleVersionError(FeedbackConflictError):
    pass


class HistoryProviderNotFoundError(Exception):
    """A requested provider history event may only reference visible listings."""


class MemberFeedbackService:
    def __init__(self, repository: MemberFeedbackRepository) -> None:
        self.repo = repository
        self.audit = AuditRepository(repository.db)

    @staticmethod
    def _value(value):
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _snapshot(feedback: MemberFeedback) -> dict:
        return {
            "category": MemberFeedbackService._value(feedback.category),
            "subject": feedback.subject,
            "rating": feedback.rating,
            "message": feedback.message,
            "status": MemberFeedbackService._value(feedback.status),
            "member_response": feedback.member_response,
            "internal_note": feedback.internal_note,
            "withdrawn_at": feedback.withdrawn_at.isoformat() if feedback.withdrawn_at else None,
        }

    def create(
        self,
        member: User,
        *,
        category: MemberFeedbackCategory,
        subject: str | None,
        rating: int | None,
        message: str,
        idempotency_key: UUID,
        audit_context: AuditContext,
    ) -> MemberFeedback:
        feedback, created = self.repo.create(
            member=member,
            category=category,
            subject=subject,
            rating=rating,
            message=message,
            idempotency_key=idempotency_key,
        )
        if created:
            self.repo.add_action(
                feedback, actor=member, actor_type="member", action="submitted",
                from_status=None, to_status=MemberFeedbackStatus.PENDING,
            )
            self.audit.record(
                "member_feedback.submitted",
                context=audit_context,
                resource_type="member_feedback",
                resource_id=str(feedback.id),
                summary="A member submitted platform feedback.",
                metadata={"status": self._value(feedback.status)},
            )
            self.repo.commit()
        return feedback

    def list_member(self, **kwargs):
        return self.repo.list_member(**kwargs)

    def member_counts(self, member_id: UUID):
        return self.repo.member_counts(member_id)

    def member_detail(self, feedback_id: UUID, member_id: UUID):
        feedback = self.repo.get_member(feedback_id, member_id)
        if feedback is None:
            raise FeedbackNotFoundError()
        return self.repo.detail(feedback.id)

    def update_member(
        self,
        feedback_id: UUID,
        member: User,
        *,
        expected_version: int,
        changes: dict,
        audit_context: AuditContext,
    ) -> MemberFeedback:
        feedback = self.repo.get_member(feedback_id, member.id, lock=True)
        if feedback is None:
            raise FeedbackNotFoundError()
        if feedback.version != expected_version:
            raise FeedbackStaleVersionError()
        if feedback.status != MemberFeedbackStatus.PENDING or feedback.withdrawn_at is not None:
            raise FeedbackConflictError("Only active pending feedback can be edited.")
        for field, value in changes.items():
            setattr(feedback, field, value)
        feedback.version += 1
        feedback.updated_at = datetime.now(timezone.utc)
        self.repo.add_action(
            feedback, actor=member, actor_type="member", action="edited",
            from_status=feedback.status, to_status=feedback.status,
        )
        self.audit.record(
            "member_feedback.edited",
            context=audit_context,
            resource_type="member_feedback",
            resource_id=str(feedback.id),
            summary="A member edited pending platform feedback.",
            metadata={"status": self._value(feedback.status), "updated_fields": list(changes)},
        )
        self.repo.commit()
        return feedback

    def withdraw(
        self, feedback_id: UUID, member: User, *, expected_version: int,
        audit_context: AuditContext,
    ) -> MemberFeedback:
        feedback = self.repo.get_member(feedback_id, member.id, lock=True)
        if feedback is None:
            raise FeedbackNotFoundError()
        if feedback.version != expected_version:
            raise FeedbackStaleVersionError()
        if feedback.status != MemberFeedbackStatus.PENDING or feedback.withdrawn_at is not None:
            raise FeedbackConflictError("Only active pending feedback can be withdrawn.")
        feedback.withdrawn_at = datetime.now(timezone.utc)
        feedback.updated_at = feedback.withdrawn_at
        feedback.version += 1
        self.repo.add_action(
            feedback, actor=member, actor_type="member", action="withdrawn",
            from_status=feedback.status, to_status=feedback.status,
        )
        self.audit.record(
            "member_feedback.withdrawn",
            context=audit_context,
            resource_type="member_feedback",
            resource_id=str(feedback.id),
            summary="A member withdrew pending platform feedback.",
            metadata={"status": self._value(feedback.status)},
        )
        self.repo.commit()
        return feedback

    def list_admin(self, **kwargs):
        return self.repo.list_admin(**kwargs)

    def admin_detail(self, feedback_id: UUID):
        feedback = self.repo.detail(feedback_id)
        if feedback is None:
            raise FeedbackNotFoundError()
        return feedback

    def update_admin(
        self,
        feedback_id: UUID,
        actor: User,
        *,
        expected_version: int,
        changes: dict,
        audit_context: AuditContext,
    ) -> MemberFeedback:
        feedback = self.repo.get(feedback_id, lock=True)
        if feedback is None:
            raise FeedbackNotFoundError()
        if feedback.version != expected_version:
            raise FeedbackStaleVersionError()
        old_status = feedback.status
        changed_fields = []
        for field, value in changes.items():
            if getattr(feedback, field) != value:
                setattr(feedback, field, value)
                changed_fields.append(field)
        if not changed_fields:
            return feedback
        feedback.version += 1
        feedback.updated_at = datetime.now(timezone.utc)
        action = (
            "status_changed" if "status" in changed_fields
            else "member_response_updated" if "member_response" in changed_fields
            else "internal_note_updated" if changed_fields == ["internal_note"]
            else "admin_updated"
        )
        self.repo.add_action(
            feedback, actor=actor, actor_type="admin", action=action,
            from_status=old_status, to_status=feedback.status,
        )
        self.audit.record(
            "member_feedback.moderated",
            context=audit_context,
            resource_type="member_feedback",
            resource_id=str(feedback.id),
            summary="An administrator updated member platform feedback.",
            metadata={"status": self._value(feedback.status), "updated_fields": changed_fields},
        )
        self.repo.commit()
        return feedback

    def append_history(
        self,
        member_id: UUID,
        *,
        event_key: str,
        event_type: str,
        provider_id: UUID | None,
        filters: dict | None,
    ):
        existing = self.repo.get_history_event(member_id=member_id, event_key=event_key)
        if existing is not None:
            return existing
        provider_name = None
        if event_type == "provider" and provider_id is not None:
            provider = self.repo.db.scalar(
                select(Provider).where(
                    Provider.id == provider_id,
                    Provider.status == ProviderStatus.ACTIVE,
                    Provider.publication_status == PublicationStatus.PUBLISHED,
                )
            )
            if provider is None:
                raise HistoryProviderNotFoundError()
            provider_name = provider.name
        item, created = self.repo.append_history(
            member_id=member_id,
            event_key=event_key,
            event_type=event_type,
            provider_id=provider_id,
            provider_name=provider_name,
            filters=filters,
        )
        if created:
            self.repo.commit()
        return item

    def list_history(self, **kwargs):
        return self.repo.list_history(**kwargs)

    def recent_history(self, **kwargs):
        return self.repo.recent_history(**kwargs)

    def provider_available(self, provider_id: UUID | None) -> bool:
        return self.repo.provider_availability(provider_id)