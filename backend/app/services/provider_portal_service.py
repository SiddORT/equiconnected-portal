"""Provider-owned portal operations for administrator-invited provider accounts."""
from __future__ import annotations

from uuid import UUID

from app.models.enums import InvitationStatus, ProviderType
from app.models.invitation import ProviderInvitation
from app.models.user import User
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.review_repository import ReviewRepository
from app.services.invitation_service import InvalidProviderDataError, InvitationService


class ProviderPortalUnavailableError(Exception):
    """The authenticated provider is not linked to a completed invitation."""


class ProviderPortalService:
    def __init__(self, provider_repo: ProviderRepository, review_repo: ReviewRepository) -> None:
        self._providers = provider_repo
        self._reviews = review_repo
        self._db = provider_repo._db
        self._audit = AuditRepository(self._db)

    def _invitation_for_user(self, user: User) -> ProviderInvitation:
        invitation = (
            self._db.query(ProviderInvitation)
            .filter(
                ProviderInvitation.portal_user_id == user.id,
                ProviderInvitation.status == InvitationStatus.COMPLETED,
            )
            .first()
        )
        if invitation is None or invitation.provider_id is None:
            raise ProviderPortalUnavailableError()
        return invitation

    def _profile_response(self, provider_id: UUID):
        from app.schemas.provider import ProviderPortalResponse

        provider = self._providers.get_by_id(provider_id)
        assert provider is not None
        average_rating, review_count = self._reviews.get_totals(provider_id)
        visible_reviews = [
            {
                "id": review.id,
                "rating": review.rating,
                "comment": review.comment,
                "reviewer_name": member.full_name,
                "created_at": review.created_at,
            }
            for review, member in self._reviews.list_visible_reviews(provider_id)
        ]
        return ProviderPortalResponse.from_provider(
            provider,
            average_rating=average_rating,
            review_count=review_count,
            visible_reviews=visible_reviews,
        )

    def get_profile(self, user: User):
        invitation = self._invitation_for_user(user)
        return self._profile_response(invitation.provider_id)

    def update_profile(self, user: User, fields: dict, *, audit_context: AuditContext | None):
        invitation = self._invitation_for_user(user)
        provider = self._providers.get_by_id(invitation.provider_id)
        if provider is None:
            raise ProviderPortalUnavailableError()
        # Share the invitation's proven collection and doctor validation, while
        # making the allowed surface explicit here rather than trusting a client.
        allowed = {
            "name", "description", "email", "phone", "website", "visit_stability",
            "specialization_ids", "locations", "phones", "emails", "photos",
            "professional_title", "biography", "years_experience",
            "experience_description", "qualifications",
        }
        safe_fields = {key: value for key, value in fields.items() if key in allowed}
        if not safe_fields:
            return self._profile_response(provider.id)
        try:
            # The shared routine does not write status, publication, or type
            # unless those fields are supplied; they are excluded above.
            helper = InvitationService.__new__(InvitationService)
            helper._providers = self._providers
            InvitationService._apply_provider_fields(helper, invitation, safe_fields)
        except InvalidProviderDataError:
            raise
        self._audit.record(
            "provider_portal.profile_updated",
            context=audit_context,
            resource_type="provider",
            resource_id=str(provider.id),
            summary="Updated the provider's own portal profile.",
            metadata={"updated_fields": sorted(safe_fields)},
        )
        self._db.commit()
        return self._profile_response(provider.id)