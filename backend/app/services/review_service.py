"""Business rules for member provider discovery and review moderation."""
from __future__ import annotations

from uuid import UUID

from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.review_repository import ReviewRepository


class DiscoverableProviderNotFoundError(Exception):
    """The provider is not currently available in the member directory."""


class ReviewNotFoundError(Exception):
    """The requested review does not exist."""


class ReviewService:
    def __init__(self, repository: ReviewRepository) -> None:
        self._repo = repository
        self._audit = AuditRepository(repository._db)

    def list_discoverable(self, **kwargs):
        return self._repo.list_discoverable(**kwargs)

    def get_discoverable(self, provider_id: UUID):
        provider = self._repo.get_discoverable(provider_id)
        if provider is None:
            raise DiscoverableProviderNotFoundError(str(provider_id))
        return provider

    def totals(self, provider_id: UUID):
        return self._repo.get_totals(provider_id)

    def visible_reviews(self, provider_id: UUID):
        return self._repo.list_visible_reviews(provider_id)

    def member_review(self, provider_id: UUID, member_id: UUID):
        return self._repo.get_member_review(provider_id, member_id)

    def save_member_review(
        self,
        provider_id: UUID,
        member_id: UUID,
        *,
        rating: int,
        comment: str,
        audit_context: AuditContext | None,
    ):
        self.get_discoverable(provider_id)
        review, created = self._repo.save_member_review(
            provider_id, member_id, rating=rating, comment=comment
        )
        self._audit.record(
            "provider_review.submitted",
            context=audit_context,
            resource_type="provider_review",
            resource_id=str(review.id),
            summary="Submitted a provider review.",
            metadata={
                "provider_id": str(provider_id),
                "rating": rating,
                "created": created,
            },
        )
        self._repo.commit()
        return review

    def list_admin_reviews(self, **kwargs):
        return self._repo.list_admin_reviews(**kwargs)

    def set_comment_visibility(
        self,
        review_id: UUID,
        *,
        comment_visible: bool,
        audit_context: AuditContext | None,
    ):
        review = self._repo.get_review(review_id)
        if review is None:
            raise ReviewNotFoundError(str(review_id))
        if review.comment_visible != comment_visible:
            review.comment_visible = comment_visible
            self._audit.record(
                "provider_review.comment_visibility_changed",
                context=audit_context,
                resource_type="provider_review",
                resource_id=str(review.id),
                summary=(
                    "Restored a provider review comment."
                    if comment_visible
                    else "Hid a provider review comment."
                ),
                metadata={
                    "provider_id": str(review.provider_id),
                    "rating": review.rating,
                    "comment_visible": comment_visible,
                },
            )
            self._repo.commit()
        return review