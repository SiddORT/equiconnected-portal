"""Shared profile-snapshot validation and administrator decision operations."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace
from uuid import UUID

from app.models.enums import ProviderProfileUpdateStatus, ProviderType
from app.models.provider import Provider, ProviderProfileUpdate
from app.repositories.audit_repository import AuditRepository
from app.repositories.provider_profile_update_repository import ProviderProfileUpdateRepository
from app.repositories.provider_repository import ProviderRepository
from app.schemas.provider import ProviderPortalEditableProfile
from app.services.invitation_service import InvalidProviderDataError, InvitationService


class ProviderProfileUpdateNotFoundError(Exception):
    pass


class ProviderProfileUpdateDecisionError(Exception):
    pass


class ProviderProfileUpdateConflictError(ProviderProfileUpdateDecisionError):
    """The approved listing changed after this draft was submitted."""


_DOCTOR_FIELDS = {
    "professional_title",
    "biography",
    "years_experience",
    "experience_description",
    "qualifications",
}


def _canonicalize_collection(items: list) -> list:
    """Sort snapshots by their complete JSON value, avoiding ORM order leaks."""
    return sorted(
        items,
        key=lambda item: json.dumps(
            item, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ),
    )


def editable_profile_from_provider(provider: Provider) -> ProviderPortalEditableProfile:
    """Build the complete mutable surface without leaking administrative controls."""
    payload = {
        "name": provider.name,
        "description": provider.description,
        "email": provider.email,
        "phone": provider.phone,
        "website": provider.website,
        "visit_stability": provider.visit_stability,
        "specialization_ids": sorted(
            (link.specialization_id for link in provider.provider_specializations),
            key=str,
        ),
        "locations": [
            {
                "name": row.name,
                "address_line_1": row.address_line_1,
                "address_line_2": row.address_line_2,
                "city": row.city,
                "state_province": row.state_province,
                "country": row.country,
                "postal_code": row.postal_code,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "is_primary": row.is_primary,
            }
            for row in sorted(
                provider.locations,
                key=lambda row: (
                    not row.is_primary,
                    row.name or "",
                    row.address_line_1,
                    row.address_line_2 or "",
                    row.city,
                ),
            )
        ],
        "phones": [
            {
                "country_code": row.country_code,
                "number": row.number,
                "is_primary": row.is_primary,
            }
            for row in sorted(
                provider.phones,
                key=lambda row: (not row.is_primary, row.country_code, row.number),
            )
        ],
        "emails": [
            {"email": row.email, "is_primary": row.is_primary}
            for row in sorted(
                provider.emails,
                key=lambda row: (not row.is_primary, row.email),
            )
        ],
        "photos": [
            {
                "storage_reference": row.storage_reference,
                "alt_text": row.alt_text,
                "caption": row.caption,
                "display_order": row.display_order,
                "is_thumbnail": row.is_thumbnail,
            }
            for row in sorted(
                provider.photos,
                key=lambda row: (
                    not row.is_thumbnail,
                    row.display_order,
                    row.storage_reference,
                ),
            )
        ],
    }
    if provider.provider_type == ProviderType.DOCTOR:
        payload.update(
            {
                "professional_title": (
                    provider.doctor_profile.professional_title
                    if provider.doctor_profile else None
                ),
                "biography": provider.doctor_profile.biography if provider.doctor_profile else None,
                "years_experience": (
                    provider.doctor_profile.years_experience
                    if provider.doctor_profile else None
                ),
                "experience_description": (
                    provider.doctor_profile.experience_description
                    if provider.doctor_profile else None
                ),
                "qualifications": [
                    {
                        "title": row.title,
                        "institution": row.institution,
                        "year_obtained": row.year_obtained,
                        "description": row.description,
                        "display_order": row.display_order,
                    }
                    for row in sorted(
                        provider.qualifications,
                        key=lambda row: (
                            row.display_order,
                            row.title,
                            row.institution or "",
                        ),
                    )
                ],
            }
        )
    for field in ("locations", "phones", "emails", "photos", "qualifications"):
        if field in payload:
            payload[field] = _canonicalize_collection(payload[field])
    return ProviderPortalEditableProfile.model_validate(payload)


def merge_editable_profile(
    base: ProviderPortalEditableProfile, patch: dict
) -> ProviderPortalEditableProfile:
    merged = base.model_dump()
    merged.update(patch)
    return ProviderPortalEditableProfile.model_validate(merged)


def serialize_editable_profile(
    provider: Provider, profile: ProviderPortalEditableProfile
) -> dict:
    """Create a stable, JSON-safe payload for comparisons and persistence."""
    payload = profile.model_dump(mode="json")
    for field in ("locations", "phones", "emails", "photos", "qualifications"):
        if field in payload:
            payload[field] = _canonicalize_collection(payload[field])
    if provider.provider_type != ProviderType.DOCTOR:
        for field in _DOCTOR_FIELDS:
            payload.pop(field, None)
    return payload


def validate_editable_profile(
    provider: Provider,
    profile: ProviderPortalEditableProfile,
    provider_repo: ProviderRepository,
    *,
    supplied_fields: set[str] | None = None,
) -> None:
    if provider.provider_type != ProviderType.DOCTOR and supplied_fields and _DOCTOR_FIELDS.intersection(supplied_fields):
        raise InvalidProviderDataError(
            "Doctor-specific fields can only be saved for Doctor providers."
        )
    for specialization_id in dict.fromkeys(profile.specialization_ids):
        specialization = provider_repo.get_specialization(specialization_id)
        if specialization is None or not specialization.is_active:
            raise InvalidProviderDataError(
                f"Specialization not found or inactive: {specialization_id}"
            )
    for records, flag, label in (
        (profile.locations, "is_primary", "location"),
        (profile.phones, "is_primary", "phone"),
        (profile.emails, "is_primary", "email"),
        (profile.photos, "is_thumbnail", "photo"),
    ):
        if sum(bool(getattr(record, flag)) for record in records) > 1:
            raise InvalidProviderDataError(f"Only one {label} may be marked as {flag}.")


def apply_editable_profile(
    provider: Provider,
    profile: ProviderPortalEditableProfile,
    provider_repo: ProviderRepository,
) -> Provider:
    """Apply a validated full snapshot using the established collection writer."""
    helper = InvitationService.__new__(InvitationService)
    helper._providers = provider_repo
    fields = profile.model_dump()
    if provider.provider_type != ProviderType.DOCTOR:
        for field in _DOCTOR_FIELDS:
            fields.pop(field, None)
    return InvitationService._apply_provider_fields(
        helper,
        SimpleNamespace(provider_id=provider.id),
        fields,
    )


class ProviderProfileUpdateService:
    def __init__(
        self,
        update_repo: ProviderProfileUpdateRepository,
        provider_repo: ProviderRepository,
    ) -> None:
        self._updates = update_repo
        self._providers = provider_repo
        self._db = update_repo._db
        self._audit = AuditRepository(self._db)

    def list(self, **filters) -> tuple[list[ProviderProfileUpdate], int]:
        return self._updates.list(**filters)

    def get(self, update_id: UUID) -> ProviderProfileUpdate:
        update = self._updates.get(update_id)
        if update is None:
            raise ProviderProfileUpdateNotFoundError()
        return update

    def approve(self, update_id: UUID, reviewer_id: UUID) -> ProviderProfileUpdate:
        # Lock in the same root→draft order as provider submissions. Reading
        # the provider id before locking is safe because the UUID is immutable.
        requested = self._updates.get(update_id)
        if requested is None:
            raise ProviderProfileUpdateNotFoundError()
        provider = self._providers.lock_provider(requested.provider_id)
        if provider is None:
            self._db.rollback()
            raise ProviderProfileUpdateNotFoundError()
        update = self._updates.get_for_update(update_id)
        if update is None or update.provider_id != provider.id:
            self._db.rollback()
            raise ProviderProfileUpdateNotFoundError()
        if update.review_status != ProviderProfileUpdateStatus.PENDING_REVIEW:
            self._db.rollback()
            raise ProviderProfileUpdateDecisionError(
                "Only pending provider profile updates can be approved."
            )
        loaded = self._providers.get_by_id(provider.id)
        assert loaded is not None
        current_profile = editable_profile_from_provider(loaded)
        if serialize_editable_profile(loaded, current_profile) != update.base_profile:
            self._db.rollback()
            raise ProviderProfileUpdateConflictError(
                "The approved profile changed after this update was submitted. "
                "Review the latest listing before approving the draft."
            )
        profile = ProviderPortalEditableProfile.model_validate(update.proposed_profile)
        validate_editable_profile(loaded, profile, self._providers)
        apply_editable_profile(loaded, profile, self._providers)
        now = datetime.now(timezone.utc)
        update.review_status = ProviderProfileUpdateStatus.APPROVED
        update.reviewed_by_user_id = reviewer_id
        update.reviewed_at = now
        update.rejection_reason = None
        self._audit.log(
            action="provider_profile_update.approved",
            user_id=reviewer_id,
            resource_type="provider_profile_update",
            resource_id=str(update.id),
            metadata={"provider_id": str(loaded.id), "provider_name": loaded.name},
            summary="Approved a provider-owned profile update.",
        )
        self._db.commit()
        return update

    def reject(
        self, update_id: UUID, reviewer_id: UUID, rejection_reason: str | None
    ) -> ProviderProfileUpdate:
        update = self._updates.get_for_update(update_id)
        if update is None:
            raise ProviderProfileUpdateNotFoundError()
        if update.review_status != ProviderProfileUpdateStatus.PENDING_REVIEW:
            self._db.rollback()
            raise ProviderProfileUpdateDecisionError(
                "Only pending provider profile updates can be rejected."
            )
        update.review_status = ProviderProfileUpdateStatus.REJECTED
        update.reviewed_by_user_id = reviewer_id
        update.reviewed_at = datetime.now(timezone.utc)
        update.rejection_reason = rejection_reason
        self._audit.log(
            action="provider_profile_update.rejected",
            user_id=reviewer_id,
            resource_type="provider_profile_update",
            resource_id=str(update.id),
            metadata={"provider_id": str(update.provider_id), "rejection_reason": rejection_reason},
            summary="Rejected a provider-owned profile update.",
        )
        self._db.commit()
        return update