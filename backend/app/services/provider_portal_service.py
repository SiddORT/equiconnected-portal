"""Provider-owned portal operations for administrator-invited provider accounts."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from uuid import UUID
import warnings

from PIL import Image, UnidentifiedImageError

from app.models.enums import (
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderProfileUpdateStatus,
)
from app.models.invitation import ProviderInvitation
from app.models.provider import DirectProviderPortalAccess
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.user import User
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.provider_profile_update_repository import ProviderProfileUpdateRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.review_repository import ReviewRepository
from app.services.invitation_service import InvalidProviderDataError
from app.services.provider_feedback import feedback_review, visible_review
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.review import ProviderFeedbackReview
from app.services.provider_profile_update_service import (
    ProviderProfileUpdateConflictError,
    append_visit_additions,
    apply_editable_profile,
    editable_profile_from_snapshot,
    editable_profile_from_provider,
    merge_editable_profile,
    serialize_editable_profile,
    sync_editable_profile_contacts,
    validate_editable_profile,
    portal_language_choices,
)


class ProviderPortalUnavailableError(Exception):
    """The authenticated provider does not own an approved listing."""


class ProviderProfileUpdateDiscardError(Exception):
    """A retained review record cannot be discarded by the provider."""


class ProviderPortalPhotoUploadError(Exception):
    """A provider portal photo upload does not meet the upload policy."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


_IMAGE_FORMATS: dict[str, tuple[str, str]] = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "GIF": ("image/gif", ".gif"),
    "WEBP": ("image/webp", ".webp"),
}
_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
_UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"


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
        # Apply the authoritative account gate even for service callers. Do not
        # infer approval from publication or retroactively gate eligible legacy
        # invitation/direct-access accounts by their listing's operational status.
        from app.auth.account_access import public_account_access_issue

        if (
            not user.is_active
            or user.provider_portal_setup_pending
            or user.role.name != "provider"
            or public_account_access_issue(user) is not None
        ):
            raise ProviderPortalUnavailableError()
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
        provider_ids.update(
            provider_id
            for (provider_id,) in self._db.query(DirectProviderPortalAccess.provider_id)
            .filter(DirectProviderPortalAccess.user_id == user.id).all()
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
                editable = editable_profile_from_snapshot(
                    provider, profile_update.proposed_profile
                )
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
            visible_review(review, member).model_dump()
            for review, member in self._reviews.list_visible_provider_reviews(provider_id)
        ]
        response = ProviderPortalResponse.from_provider(
            provider,
            average_rating=average_rating,
            review_count=review_count,
            visible_reviews=visible_reviews,
            editable_profile=editable,
            profile_update=state,
        )
        response.language_choices = portal_language_choices(provider, editable)
        return response

    def get_profile(self, user: User):
        return self._profile_response(self._provider_id_for_user(user))

    def get_feedback(
        self, user: User, *, page: int, page_size: int
    ) -> PaginatedResponse[ProviderFeedbackReview]:
        provider_id = self._provider_id_for_user(user)
        if self._providers.get_by_id(provider_id) is None:
            raise ProviderPortalUnavailableError()
        rows, total = self._reviews.list_provider_feedback(
            provider_id, page=page, page_size=page_size
        )
        return PaginatedResponse(
            data=[feedback_review(review, member) for review, member in rows],
            meta=PaginationMeta(
                page=page, page_size=page_size, total=total,
                total_pages=(total + page_size - 1) // page_size,
            ),
        )

    def get_insights(
        self,
        user: User,
        *,
        preset: str,
        date_from,
        date_to,
    ):
        """Return aggregate reporting for the listing explicitly linked to this account."""
        from app.core.time_standards import system_today
        from app.repositories.system_settings_repository import SystemSettingsRepository
        from app.services.provider_insights_service import ProviderInsightsService

        provider_id = self._provider_id_for_user(user)
        timezone_name = SystemSettingsRepository(self._db).get_or_create().timezone
        report = ProviderInsightsService(self._db, self._reviews).report(
            provider_id=provider_id,
            provider_user_id=user.id,
            timezone_name=timezone_name,
            today=system_today(timezone_name),
            preset=preset,
            date_from=date_from,
            date_to=date_to,
        )
        if report is None:
            raise ProviderPortalUnavailableError()
        return report

    async def upload_photo(
        self,
        user: User,
        *,
        upload,
        audit_context: AuditContext | None,
    ) -> str:
        """Stream, verify, and save an image for a later owner-profile save."""
        provider_id = self._provider_id_for_user(user)
        if self._providers.get_by_id(provider_id) is None:
            raise ProviderPortalUnavailableError()
        destination_dir = _UPLOADS_DIR / "providers" / str(provider_id) / "photos"
        destination_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = destination_dir / f".{uuid4()}.upload"
        try:
            size = 0
            with temporary_path.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > _MAX_IMAGE_SIZE_BYTES:
                        raise ProviderPortalPhotoUploadError(
                            "image_too_large",
                            "Images must be 10 MB or smaller.",
                        )
                    target.write(chunk)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(temporary_path) as image:
                        image_format = image.format
                        image.verify()
            except (
                UnidentifiedImageError,
                OSError,
                SyntaxError,
                ValueError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
            ) as exc:
                raise ProviderPortalPhotoUploadError(
                    "invalid_image_content",
                    "The uploaded file is not a valid supported image.",
                ) from exc
            if image_format not in _IMAGE_FORMATS:
                raise ProviderPortalPhotoUploadError(
                    "invalid_image_type",
                    "Only JPEG, PNG, GIF, and WebP images are accepted.",
                )
            image_type, extension = _IMAGE_FORMATS[image_format]
            if upload.content_type and upload.content_type != image_type:
                raise ProviderPortalPhotoUploadError(
                    "invalid_image_content",
                    "The uploaded file content does not match its declared image type.",
                )
            filename = f"{uuid4()}{extension}"
            temporary_path.replace(destination_dir / filename)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        storage_reference = f"/uploads/providers/{provider_id}/photos/{filename}"
        self._audit.record(
            "provider_portal.photo_uploaded",
            context=audit_context,
            resource_type="provider",
            resource_id=str(provider_id),
            summary="Uploaded a photo for a provider-owned profile update.",
        )
        self._db.commit()
        return storage_reference

    def _validate_photo_references(self, provider, editable) -> None:
        """Allow portal saves to retain existing photos or use this provider's uploads."""
        if not editable.photos:
            return
        existing_references = {
            photo.storage_reference for photo in provider.photos
        }
        owned_prefix = f"/uploads/providers/{provider.id}/photos/"
        owned_directory = (
            _UPLOADS_DIR / "providers" / str(provider.id) / "photos"
        ).resolve()
        for photo in editable.photos:
            reference = photo.storage_reference
            if reference in existing_references:
                continue
            if not reference.startswith(owned_prefix):
                raise InvalidProviderDataError(
                    "Profile photos must be uploaded through your provider portal."
                )
            upload_path = (
                _UPLOADS_DIR / reference.removeprefix("/uploads/")
            ).resolve()
            if upload_path.parent != owned_directory or not upload_path.is_file():
                raise InvalidProviderDataError(
                    "One or more selected profile photos are unavailable. Please upload them again."
                )

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
            "maximum_working_radius_km", "emergency_services_available",
            "emergency_contact_number",
            "visit_additions", "first_name", "last_name", "doctor_availability", "language_ids",
        }
        safe_fields = {key: value for key, value in fields.items() if key in allowed}
        if set(fields) - allowed:
            raise InvalidProviderDataError("Only provider-owned profile fields may be updated.")
        if not safe_fields:
            return self._profile_response(provider.id)
        # Serialize owner writes and legacy decisions through the same root row.
        # Reload canonical collections only after the lock has been acquired.
        locked = self._providers.lock_provider(provider.id)
        if locked is None:
            self._db.rollback()
            raise ProviderPortalUnavailableError()
        provider = self._providers.get_by_id(provider.id)
        assert provider is not None
        profile_update = self._updates.get_for_provider_for_update(provider.id)
        canonical = editable_profile_from_provider(provider)
        base = canonical
        if profile_update and profile_update.review_status in (
            ProviderProfileUpdateStatus.PENDING_REVIEW,
            ProviderProfileUpdateStatus.REJECTED,
        ):
            expected_base = serialize_editable_profile(
                provider, editable_profile_from_snapshot(provider, profile_update.base_profile)
            )
            if serialize_editable_profile(provider, canonical) != expected_base:
                self._db.rollback()
                raise ProviderProfileUpdateConflictError(
                    "The listing changed after this draft was created. "
                    "Discard the draft and reload the latest listing before saving."
                )
            base = editable_profile_from_snapshot(
                provider, profile_update.proposed_profile
            )
        editable = merge_editable_profile(base, safe_fields)
        editable = sync_editable_profile_contacts(editable, set(safe_fields))
        self._validate_photo_references(provider, editable)
        validate_editable_profile(
            provider,
            editable,
            self._providers,
            supplied_fields=set(safe_fields),
            previous_visit_additions=base.visit_additions,
        )

        # Every account admitted above has passed initial approval or the
        # existing legacy access policy. Publication is an independent control.
        # Recheck retained trip additions against today's recorded schedule.
        if editable.visit_additions:
            validate_editable_profile(provider, editable, self._providers)
        try:
            apply_editable_profile(provider, editable, self._providers)
            append_visit_additions(provider, editable, self._providers)
            if profile_update is not None and profile_update.review_status in (
                ProviderProfileUpdateStatus.PENDING_REVIEW,
                ProviderProfileUpdateStatus.REJECTED,
            ):
                # Keep both encrypted snapshots and original reviewer/rejection
                # provenance. This is not an administrator approval.
                profile_update.review_status = ProviderProfileUpdateStatus.SAVED_DIRECTLY
                self._audit.record(
                    "provider_profile_update.saved_directly",
                    context=audit_context,
                    resource_type="provider_profile_update",
                    resource_id=str(profile_update.id),
                    summary="Owner explicitly saved a retained draft without further review.",
                    metadata={"provider_id": str(provider.id)},
                )
            self._audit.record(
                "provider_portal.profile_updated",
                context=audit_context,
                resource_type="provider",
                resource_id=str(provider.id),
                summary="Saved the provider's own profile without changing listing lifecycle controls.",
                metadata={"updated_fields": sorted(safe_fields)},
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
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
        if profile_update.review_status not in (
            ProviderProfileUpdateStatus.PENDING_REVIEW,
            ProviderProfileUpdateStatus.REJECTED,
        ):
            self._db.rollback()
            raise ProviderProfileUpdateDiscardError(
                "Completed profile update history cannot be discarded."
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