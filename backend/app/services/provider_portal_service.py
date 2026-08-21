"""Provider-owned portal operations for administrator-invited provider accounts."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.models.enums import (
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderProfileUpdateStatus,
)
from app.models.invitation import ProviderInvitation
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.user import User
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.provider_profile_update_repository import ProviderProfileUpdateRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.review_repository import ReviewRepository
from app.services.invitation_service import InvalidProviderDataError
from app.services.provider_profile_update_service import (
    apply_editable_profile,
    editable_profile_from_provider,
    merge_editable_profile,
    serialize_editable_profile,
    validate_editable_profile,
)


class ProviderPortalUnavailableError(Exception):
    """The authenticated provider does not own an approved listing."""


class ProviderProfileUpdateDiscardError(Exception):
    """A retained review record cannot be discarded by the provider."""


class ProviderPortalService:
    def __init__(
        self,
        provider_repo: ProviderRepository,
        review_repo: ReviewRepository,
        update_repo: ProviderProfileUpdateRepository,
    ) -> None:
        self._providers = provider_repo
        self._reviews = review_repo
        self._updates = update_repo
        self._db = provider_repo._db
        self._audit = AuditRepository(self._db)

    def _provider_id_for_user(self, user: User) -> UUID:
        """Resolve one explicitly approved provider listing for this account.

        Provider ownership is created through either a completed administrator
        invitation or an approved self-service registration. A missing or
        ambiguous link is deliberately not inferred from an email address.
        """
        provider_ids = {
            provider_id
            for (provider_id,) in self._db.query(ProviderInvitation.provider_id)
            .filter(
                ProviderInvitation.portal_user_id == user.id,
                ProviderInvitation.status == InvitationStatus.COMPLETED,
                ProviderInvitation.provider_id.is_not(None),
            )
            .all()
        }
        provider_ids.update(
            provider_id
            for (provider_id,) in self._db.query(
                ProviderRegistrationApplication.provider_id
            )
            .filter(
                ProviderRegistrationApplication.user_id == user.id,
                ProviderRegistrationApplication.review_status
                == ProviderApplicationStatus.APPROVED,
                ProviderRegistrationApplication.provider_id.is_not(None),
            )
            .all()
        )
        if len(provider_ids) != 1:
            raise ProviderPortalUnavailableError()
        return provider_ids.pop()

    def _profile_response(self, provider_id: UUID):
        from app.schemas.provider import ProviderPortalResponse, ProviderProfileUpdateState

        provider = self._providers.get_by_id(provider_id)
        assert provider is not None
        profile_update = self._updates.get_by_provider(provider_id)
        editable = editable_profile_from_provider(provider)
        state = None
        if profile_update is not None:
            if profile_update.review_status in (
                ProviderProfileUpdateStatus.PENDING_REVIEW,
                ProviderProfileUpdateStatus.REJECTED,
            ):
                editable = editable.model_validate(profile_update.proposed_profile)
            state = ProviderProfileUpdateState(
                id=profile_update.id,
                review_status=profile_update.review_status,
                submitted_at=profile_update.submitted_at,
                reviewed_at=profile_update.reviewed_at,
                reviewed_by_name=(
                    profile_update.reviewer.full_name if profile_update.reviewer else None
                ),
                rejection_reason=profile_update.rejection_reason,
            )
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
            editable_profile=editable,
            profile_update=state,
        )

    def get_profile(self, user: User):
        return self._profile_response(self._provider_id_for_user(user))

    def update_profile(self, user: User, fields: dict, *, audit_context: AuditContext | None):
        provider = self._providers.get_by_id(self._provider_id_for_user(user))
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
        # Serializing submissions through the provider row prevents two browser
        # tabs from each creating a separate draft before the unique row exists.
        locked = self._providers.lock_provider(provider.id)
        if locked is None:
            self._db.rollback()
            raise ProviderPortalUnavailableError()
        provider = self._providers.get_by_id(provider.id)
        assert provider is not None
        profile_update = self._updates.get_for_provider_for_update(provider.id)
        base = editable_profile_from_provider(provider)
        if profile_update and profile_update.review_status in (
            ProviderProfileUpdateStatus.PENDING_REVIEW,
            ProviderProfileUpdateStatus.REJECTED,
        ):
            base = base.model_validate(profile_update.proposed_profile)
        editable = merge_editable_profile(base, safe_fields)
        validate_editable_profile(
            provider, editable, self._providers, supplied_fields=set(safe_fields)
        )

        if provider.publication_status.value == "PUBLISHED":
            now = datetime.now(timezone.utc)
            serialized = serialize_editable_profile(provider, editable)
            if profile_update is None:
                profile_update = self._updates.create(
                    provider_id=provider.id,
                    proposed_profile=serialized,
                    base_profile=serialize_editable_profile(provider, base),
                    review_status=ProviderProfileUpdateStatus.PENDING_REVIEW,
                    submitted_at=now,
                )
            else:
                profile_update.proposed_profile = serialized
                if profile_update.review_status == ProviderProfileUpdateStatus.APPROVED:
                    profile_update.base_profile = serialize_editable_profile(
                        provider, base
                    )
                profile_update.review_status = ProviderProfileUpdateStatus.PENDING_REVIEW
                profile_update.submitted_at = now
                profile_update.reviewed_by_user_id = None
                profile_update.reviewed_at = None
                profile_update.rejection_reason = None
            self._audit.record(
                "provider_profile_update.submitted",
                context=audit_context,
                resource_type="provider_profile_update",
                resource_id=str(profile_update.id),
                summary="Submitted a provider-owned profile update for review.",
                metadata={"provider_id": str(provider.id), "updated_fields": sorted(safe_fields)},
            )
        else:
            apply_editable_profile(provider, editable, self._providers)
            self._audit.record(
                "provider_portal.profile_updated",
                context=audit_context,
                resource_type="provider",
                resource_id=str(provider.id),
                summary="Updated the provider's own unpublished portal profile.",
                metadata={"updated_fields": sorted(safe_fields)},
            )
        self._db.commit()
        return self._profile_response(provider.id)

    def discard_profile_update(
        self, user: User, *, audit_context: AuditContext | None
    ):
        """Discard a stale/private draft and return to the latest approved source."""
        provider = self._providers.lock_provider(self._provider_id_for_user(user))
        if provider is None:
            self._db.rollback()
            raise ProviderPortalUnavailableError()
        profile_update = self._updates.get_for_provider_for_update(provider.id)
        if profile_update is None:
            self._db.rollback()
            raise ProviderPortalUnavailableError()
        if profile_update.review_status == ProviderProfileUpdateStatus.APPROVED:
            self._db.rollback()
            raise ProviderProfileUpdateDiscardError(
                "Approved profile update records cannot be discarded."
            )
        self._db.delete(profile_update)
        self._audit.record(
            "provider_profile_update.discarded",
            context=audit_context,
            resource_type="provider_profile_update",
            resource_id=str(profile_update.id),
            summary="Discarded a provider-owned profile update draft.",
            metadata={"provider_id": str(provider.id)},
        )
        self._db.commit()
        return self._profile_response(provider.id)