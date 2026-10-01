"""Business rules for member provider discovery and review moderation."""
from __future__ import annotations

from uuid import UUID

from app.models.enums import ProviderReviewStatus
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.review_repository import ReviewRepository


class DiscoverableProviderNotFoundError(Exception):
    """The provider is not currently available in the member directory."""


class ReviewNotFoundError(Exception):
    """The requested review does not exist or is not owned by the member."""


class ReviewConflictError(Exception):
    """The review was changed since the caller last read it."""


class ReviewStateError(Exception):
    """The requested operation is not permitted in the current review state."""


class ReviewService:
    def __init__(self, repository: ReviewRepository) -> None:
        self._repo = repository
        self._audit = AuditRepository(repository._db)

    def list_discoverable(self, **kwargs):
        return self._repo.list_discoverable(**kwargs)

    def directory_facets(self):
        return self._repo.directory_facets()

    def get_discoverable(self, provider_id: UUID, *, include_profile: bool = False):
        provider = self._repo.get_discoverable(provider_id, include_profile=include_profile)
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
        expected_version: int | None,
        audit_context: AuditContext | None,
    ):
        self.get_discoverable(provider_id)
        previous = self._repo.get_member_review(provider_id, member_id)
        previous_status = previous.status if previous is not None else None
        if previous is not None and previous.status == ProviderReviewStatus.HIDDEN:
            if (
                expected_version is None
                and previous.rating == rating
                and previous.comment == comment
            ):
                return previous
            raise ReviewStateError("Hidden reviews cannot be edited.")
        if previous is not None and expected_version is None:
            if previous.rating == rating and previous.comment == comment:
                # A lost-response retry is a read-only success, even if
                # moderation already changed the review since its submission.
                return previous
            raise ReviewConflictError("Reload this review before editing it.")
        if previous is not None:
            review = self._repo.update_member_review(
                previous.id,
                member_id,
                rating=rating,
                comment=comment,
                expected_version=expected_version,
            )
            _created = False
        else:
            if expected_version is not None:
                raise ReviewConflictError("This review changed. Reload it before trying again.")
            review, _created = self._repo.save_member_review(
                provider_id,
                member_id,
                rating=rating,
                comment=comment,
                expected_version=None,
            )
        if review is None:
            raise ReviewConflictError("This review changed. Reload it before trying again.")
        if previous is None and not _created:
            if review.rating != rating or review.comment != comment:
                raise ReviewConflictError(
                    "A review was submitted in another request. Reload it before editing."
                )
            # A lost-response retry must not duplicate its attributable action
            # history or reset moderation state.
            return review
        self._repo.record_action(
            review_id=review.id,
            actor_id=member_id,
            action="member_submitted" if previous is None else "member_edited",
            from_status=previous_status,
            to_status=review.status,
            version=review.version,
            actor_type="member",
        )
        self._audit.record(
            "provider_review.submitted" if previous is None else "provider_review.updated",
            context=audit_context,
            resource_type="provider_review",
            resource_id=str(review.id),
            summary="Submitted a provider review." if previous is None else "Updated a provider review.",
            metadata={"status": review.status.value},
        )
        self._repo.commit()
        return review

    def list_member_reviews(self, member_id: UUID, *, page: int, page_size: int):
        return self._repo.list_member_reviews(member_id, page=page, page_size=page_size)

    def get_member_review(self, review_id: UUID, member_id: UUID):
        review = self._repo.get_review(review_id)
        if review is None or review.member_id != member_id or review.deleted_at is not None:
            raise ReviewNotFoundError(str(review_id))
        return review

    def member_review_counts(self, member_id: UUID):
        return self._repo.member_review_counts(member_id)

    def edit_member_review(
        self,
        review_id: UUID,
        member_id: UUID,
        *,
        rating: int,
        comment: str,
        expected_version: int,
        audit_context: AuditContext | None,
    ):
        review = self._repo.get_review(review_id)
        if review is None or review.member_id != member_id or review.deleted_at is not None:
            raise ReviewNotFoundError(str(review_id))
        if review.status == ProviderReviewStatus.HIDDEN:
            raise ReviewStateError("Hidden reviews cannot be edited.")
        previous_status = review.status
        updated = self._repo.update_member_review(
            review_id,
            member_id,
            rating=rating,
            comment=comment,
            expected_version=expected_version,
        )
        if updated is None:
            raise ReviewConflictError("This review changed. Reload it before trying again.")
        self._repo.record_action(
            review_id=updated.id,
            actor_id=member_id,
            action="member_edited",
            from_status=previous_status,
            to_status=updated.status,
            version=updated.version,
            actor_type="member",
        )
        self._audit.record(
            "provider_review.updated",
            context=audit_context,
            resource_type="provider_review",
            resource_id=str(updated.id),
            summary="Updated a provider review.",
            metadata={"status": updated.status.value},
        )
        self._repo.commit()
        return updated

    def delete_member_review(
        self,
        review_id: UUID,
        member_id: UUID,
        *,
        expected_version: int,
        audit_context: AuditContext | None,
    ) -> None:
        review = self._repo.get_review(review_id)
        if review is None or review.member_id != member_id or review.deleted_at is not None:
            raise ReviewNotFoundError(str(review_id))
        deleted = self._repo.delete_member_review(review_id, member_id, expected_version)
        if deleted is None:
            raise ReviewConflictError("This review changed. Reload it before trying again.")
        self._repo.record_action(
            review_id=deleted.id,
            actor_id=member_id,
            action="member_deleted",
            from_status=deleted.status,
            to_status=deleted.status,
            version=deleted.version,
            actor_type="member",
        )
        self._audit.record(
            "provider_review.deleted",
            context=audit_context,
            resource_type="provider_review",
            resource_id=str(deleted.id),
            summary="Deleted a provider review.",
            metadata={"status": deleted.status.value},
        )
        self._repo.commit()

    def list_admin_reviews(self, **kwargs):
        return self._repo.list_admin_reviews(**kwargs)

    def set_comment_visibility(
        self,
        review_id: UUID,
        *,
        comment_visible: bool,
        expected_version: int,
        audit_context: AuditContext | None,
    ):
        return self.update_admin_review(
            review_id,
            status=(
                ProviderReviewStatus.PUBLISHED
                if comment_visible
                else ProviderReviewStatus.HIDDEN
            ),
            expected_version=expected_version,
            member_note=None,
            internal_note=None,
            update_member_note=False,
            update_internal_note=False,
            audit_context=audit_context,
        )

    def update_admin_review(
        self,
        review_id: UUID,
        *,
        status: ProviderReviewStatus,
        expected_version: int,
        member_note: str | None,
        internal_note: str | None,
        update_member_note: bool,
        update_internal_note: bool,
        audit_context: AuditContext | None,
    ):
        review = self._repo.get_review(review_id)
        if review is None:
            raise ReviewNotFoundError(str(review_id))
        if review.deleted_at is not None:
            raise ReviewStateError("Deleted reviews cannot be moderated.")
        old_status = review.status
        if status == ProviderReviewStatus.HIDDEN and old_status not in (
            ProviderReviewStatus.PUBLISHED,
            ProviderReviewStatus.HIDDEN,
        ):
            raise ReviewStateError("Only a published review can have its comment hidden.")
        updated = self._repo.set_review_status(
            review_id,
            expected_version=expected_version,
            new_status=status,
            member_note=member_note,
            internal_note=internal_note,
            update_member_note=update_member_note,
            update_internal_note=update_internal_note,
        )
        if updated is None:
            raise ReviewConflictError("This review changed. Reload it before moderating.")
        actor_id = audit_context.user_id if audit_context else None
        self._repo.record_action(
            review_id=updated.id,
            actor_id=actor_id,
            action=f"admin_{status.value.lower()}",
            from_status=old_status,
            to_status=updated.status,
            version=updated.version,
            actor_type=audit_context.actor_type if audit_context else "admin",
        )
        self._audit.record(
            "provider_review.status_changed",
            context=audit_context,
            resource_type="provider_review",
            resource_id=str(updated.id),
            summary=f"Changed provider review status to {updated.status.value}.",
            metadata={"status": updated.status.value},
        )
        self._repo.commit()
        return updated

    def review_history(self, review_id: UUID):
        if self._repo.get_review(review_id) is None:
            raise ReviewNotFoundError(str(review_id))
        return self._repo.list_review_actions(review_id)