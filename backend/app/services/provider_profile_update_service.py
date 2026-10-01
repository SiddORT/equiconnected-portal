"""Shared profile-snapshot validation and administrator decision operations."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import re
from types import SimpleNamespace
from uuid import UUID

from app.core.phone_metadata import SUPPORTED_PHONE_DIAL_CODES
from app.models.enums import (
    DoctorAvailability,
    ProviderProfileUpdateStatus,
    ProviderType,
)
from app.models.provider import Provider, ProviderProfileUpdate
from app.repositories.audit_repository import AuditRepository
from app.repositories.provider_profile_update_repository import ProviderProfileUpdateRepository
from app.repositories.provider_repository import ProviderRepository
from app.schemas.provider import ProviderPortalEditableProfile
from app.services.invitation_service import (
    InvalidProviderDataError,
    InvitationService,
    _is_complete_international_phone,
)


class ProviderProfileUpdateNotFoundError(Exception):
    pass


class ProviderProfileUpdateDecisionError(Exception):
    pass


class ProviderProfileUpdateConflictError(ProviderProfileUpdateDecisionError):
    """The approved listing changed after this draft was submitted."""


_DOCTOR_FIELDS = {
    "professional_title",
    "biography",
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


def _legacy_phone_contact(value: str) -> dict:
    """Convert the legacy scalar phone into the portal's structured format."""
    normalized = value.strip()
    match = re.match(r"^(\+\d{1,4})[\s.-]+(.+)$", normalized)
    if match:
        country_code, number = match.groups()
    else:
        compact = re.fullmatch(r"\+(\d{7,19})", normalized)
        if compact:
            for dial_code in sorted(
                SUPPORTED_PHONE_DIAL_CODES, key=len, reverse=True
            ):
                local_number = compact.group(1)[len(dial_code) - 1 :]
                if (
                    normalized.startswith(dial_code)
                    and 6 <= len(local_number) <= 15
                ):
                    return {
                        "country_code": dial_code,
                        "number": local_number,
                        "is_primary": True,
                    }
        # Pre-country-picker records may contain a local number only. The
        # portal's phone input already uses +1 as its default country.
        country_code, number = "+1", normalized
    return {"country_code": country_code, "number": number, "is_primary": True}


def editable_profile_from_provider(provider: Provider) -> ProviderPortalEditableProfile:
    """Build the complete mutable surface without leaking administrative controls."""
    payload = {
        "name": provider.name,
        "description": provider.description,
        "email": provider.email,
        "phone": provider.phone,
        "website": provider.website,
        "years_experience": (
            provider.years_experience
            if provider.years_experience is not None
            else (
                provider.doctor_profile.years_experience
                if provider.provider_type == ProviderType.DOCTOR
                and provider.doctor_profile is not None
                else None
            )
        ),
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
        ] or ([_legacy_phone_contact(provider.phone)] if provider.phone else []),
        "emails": [
            {"email": row.email, "is_primary": row.is_primary}
            for row in sorted(
                provider.emails,
                key=lambda row: (not row.is_primary, row.email),
            )
        ] or (
            [{"email": provider.email, "is_primary": True}]
            if provider.email else []
        ),
        "maximum_working_radius_km": (
            float(provider.maximum_working_radius_km)
            if provider.maximum_working_radius_km is not None else None
        ),
        "emergency_services_available": provider.emergency_services_available,
        "emergency_contact_number": provider.emergency_contact_number,
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
        # Approved/admin-created visits are immutable history, not editable
        # profile fields. The portal only carries not-yet-recorded additions.
        "visit_additions": [],
    }
    if provider.provider_type == ProviderType.DOCTOR:
        payload.update(
            {
                "professional_title": (
                    provider.doctor_profile.professional_title
                    if provider.doctor_profile else None
                ),
                "biography": provider.doctor_profile.biography if provider.doctor_profile else None,
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
    for field in (
        "locations",
        "phones",
        "emails",
        "photos",
        "qualifications",
        "visit_additions",
    ):
        if field in payload:
            payload[field] = _canonicalize_collection(payload[field])
    return ProviderPortalEditableProfile.model_validate(payload)


def merge_editable_profile(
    base: ProviderPortalEditableProfile, patch: dict
) -> ProviderPortalEditableProfile:
    merged = base.model_dump()
    merged.update(patch)
    return ProviderPortalEditableProfile.model_validate(merged)


def sync_editable_profile_contacts(
    profile: ProviderPortalEditableProfile, supplied_fields: set[str]
) -> ProviderPortalEditableProfile:
    """Mirror explicitly supplied contact collections into legacy scalar fields."""
    payload = profile.model_dump()
    if "emails" in supplied_fields:
        entries = payload["emails"]
        primary = next(
            (entry["email"] for entry in entries if entry["is_primary"]),
            entries[0]["email"] if entries else None,
        )
        payload["email"] = primary
    if "phones" in supplied_fields:
        entries = payload["phones"]
        primary = next(
            (entry for entry in entries if entry["is_primary"]),
            entries[0] if entries else None,
        )
        payload["phone"] = (
            f"{primary['country_code']} {primary['number']}" if primary else None
        )
    return ProviderPortalEditableProfile.model_validate(payload)


def editable_profile_from_snapshot(
    provider: Provider, snapshot: dict
) -> ProviderPortalEditableProfile:
    """Load a persisted snapshot while supplying fields added after it was saved."""
    profile = merge_editable_profile(editable_profile_from_provider(provider), snapshot)
    payload = profile.model_dump()
    # Older snapshots captured empty collections before contact editing was
    # unified. Those empties meant "no structured contacts yet", not "clear the
    # legacy scalar contact"; newly cleared snapshots also clear their scalar.
    if not snapshot.get("emails") and snapshot.get("email"):
        payload["emails"] = [{"email": snapshot["email"], "is_primary": True}]
    if not snapshot.get("phones") and snapshot.get("phone"):
        payload["phones"] = [_legacy_phone_contact(snapshot["phone"])]
    return ProviderPortalEditableProfile.model_validate(payload)


def serialize_editable_profile(
    provider: Provider, profile: ProviderPortalEditableProfile
) -> dict:
    """Create a stable, JSON-safe payload for comparisons and persistence."""
    payload = profile.model_dump(mode="json")
    for field in (
        "locations",
        "phones",
        "emails",
        "photos",
        "qualifications",
        "visit_additions",
    ):
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
    previous_visit_additions: list | None = None,
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

    previous_radius = (
        float(provider.maximum_working_radius_km)
        if provider.maximum_working_radius_km is not None else None
    )
    if (
        profile.visit_stability.value == "STABLE_VISIT"
        and (
            profile.visit_stability != provider.visit_stability
            or profile.maximum_working_radius_km != previous_radius
        )
        and (
            profile.maximum_working_radius_km is None
            or profile.maximum_working_radius_km <= 0
        )
    ):
        raise InvalidProviderDataError(
            "Stable visits require a positive maximum working radius."
        )

    emergency_changed = (
        profile.emergency_services_available != provider.emergency_services_available
        or profile.emergency_contact_number != provider.emergency_contact_number
    )
    if (
        profile.emergency_services_available is True
        and emergency_changed
        and not _is_complete_international_phone(profile.emergency_contact_number)
    ):
        raise InvalidProviderDataError(
            "Enter a complete international emergency contact number with a dial code and 6–15 local digits."
        )

    # Do not invalidate retained trips on unrelated edits: an administrator
    # may have changed the schedule since submission. Recheck the live schedule
    # when additions are revised and, independently, when an admin approves.
    should_validate_visits = supplied_fields is None or (
        "visit_additions" in supplied_fields
    )
    if should_validate_visits and profile.visit_additions:
        if (
            provider.provider_type != ProviderType.DOCTOR
            or provider.doctor_availability != DoctorAvailability.VISITING
        ):
            raise InvalidProviderDataError(
                "Only visiting doctors can add scheduled visits."
            )

        unchanged_additions = {
            json.dumps(
                addition.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
            for addition in (previous_visit_additions or [])
        }
        for addition in profile.visit_additions:
            if supplied_fields is not None and "visit_additions" in supplied_fields:
                key = json.dumps(
                    addition.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if key not in unchanged_additions and addition.start_date < date.today():
                    raise InvalidProviderDataError(
                        "New visit dates must start today or later."
                    )

        recorded_ranges = [
            (visit.start_date, visit.end_date)
            for visit in provider_repo.visits(provider.id)
        ]
        addition_ranges = [
            (addition.start_date, addition.end_date)
            for addition in profile.visit_additions
        ]
        for index, (start, end) in enumerate(addition_ranges):
            overlaps_recorded = any(
                recorded_start <= end and start <= recorded_end
                for recorded_start, recorded_end in recorded_ranges
            )
            overlaps_addition = any(
                other_start <= end and start <= other_end
                for other_start, other_end in addition_ranges[index + 1 :]
            )
            if overlaps_recorded or overlaps_addition:
                raise InvalidProviderDataError(
                    "Visit dates overlap another scheduled visit, including endpoints."
                )


def apply_editable_profile(
    provider: Provider,
    profile: ProviderPortalEditableProfile,
    provider_repo: ProviderRepository,
) -> Provider:
    """Apply a validated full snapshot using the established collection writer."""
    helper = InvitationService.__new__(InvitationService)
    helper._providers = provider_repo
    # This path is reserved for provider-portal updates; invitation contact
    # suggestion semantics intentionally remain owned by InvitationService.
    profile = sync_editable_profile_contacts(profile, {"emails", "phones"})
    fields = profile.model_dump()
    # These virtual draft entries are persisted as DoctorVisit rows only after
    # validation; they are not writable provider attributes.
    fields.pop("visit_additions", None)
    if provider.provider_type != ProviderType.DOCTOR:
        for field in _DOCTOR_FIELDS:
            fields.pop(field, None)
    return InvitationService._apply_provider_fields(
        helper,
        SimpleNamespace(provider_id=provider.id),
        fields,
    )


def append_visit_additions(
    provider: Provider,
    profile: ProviderPortalEditableProfile,
    provider_repo: ProviderRepository,
) -> None:
    """Append validated trip additions while leaving all saved visits intact."""
    for addition in profile.visit_additions:
        provider_repo.add_visit(
            provider.id,
            {
                "location": addition.location.model_dump(mode="json"),
                "start_date": addition.start_date,
                "end_date": addition.end_date,
            },
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
        current_snapshot = serialize_editable_profile(loaded, current_profile)
        # Normalize legacy omissions using that snapshot's own scalar values:
        # pre-collection bases used empty arrays plus scalar public contacts,
        # and pre-service bases omitted the later service fields. This preserves
        # compatibility without overlooking a real change to captured fields.
        base_profile = editable_profile_from_snapshot(
            loaded, update.base_profile
        )
        base_snapshot = serialize_editable_profile(loaded, base_profile)
        if current_snapshot != base_snapshot:
            self._db.rollback()
            raise ProviderProfileUpdateConflictError(
                "The approved profile changed after this update was submitted. "
                "Review the latest listing before approving the draft."
            )
        profile = editable_profile_from_snapshot(loaded, update.proposed_profile)
        try:
            validate_editable_profile(loaded, profile, self._providers)
        except InvalidProviderDataError as exc:
            self._db.rollback()
            raise ProviderProfileUpdateConflictError(str(exc)) from exc
        apply_editable_profile(loaded, profile, self._providers)
        append_visit_additions(loaded, profile, self._providers)
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