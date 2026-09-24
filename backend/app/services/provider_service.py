"""
ProviderService — business logic for healthcare providers.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.enums import (
    ProviderStatus,
    ProviderType,
    DoctorAvailability,
    PublicationStatus,
    VisitStability,
)
from app.models.provider import (
    Provider,
    ProviderEmail,
    ProviderLocation,
    ProviderPhone,
    ProviderPhoto,
    DoctorVisit,
)
from app.repositories.provider_repository import ProviderRepository
from app.repositories.audit_repository import AuditContext, AuditRepository


# ── Domain exceptions ─────────────────────────────────────────────────────────

class ProviderNotFoundError(Exception):
    """Raised when a provider is not found by ID."""


class SpecializationNotFoundError(Exception):
    """Raised when a specialization does not exist (or is not active)."""


class DuplicateSpecializationError(Exception):
    """Raised when a specialization is already assigned to the provider."""


class LocationNotFoundError(Exception):
    """Raised when a location does not exist for the provider."""


class PhotoNotFoundError(Exception):
    """Raised when a photo does not exist for the provider."""


class PhoneNotFoundError(Exception):
    """Raised when a phone does not exist for the provider."""


class EmailNotFoundError(Exception):
    """Raised when an email does not exist for the provider."""


class VisitNotFoundError(Exception):
    """Raised when a visit is not part of this provider."""


# ── Service ───────────────────────────────────────────────────────────────────

class ProviderService:
    def __init__(self, repo: ProviderRepository) -> None:
        self._repo = repo
        self._audit = AuditRepository(repo._db)

    def _record(
        self,
        action: str,
        provider: Provider,
        summary: str,
        *,
        context: AuditContext | None = None,
        changes: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._audit.record(
            action,
            context=context,
            resource_type="provider",
            resource_id=str(provider.id),
            summary=summary,
            changes=changes,
            metadata={
                "provider_name": provider.name,
                "provider_type": provider.provider_type.value,
                **(metadata or {}),
            },
        )

    # ── Core CRUD ─────────────────────────────────────────────────────────────

    def list(
        self,
        *,
        search: str | None = None,
        provider_type: ProviderType | None = None,
        visit_stability: VisitStability | None = None,
        emergency_services_available: bool | None = None,
        status: ProviderStatus | None = None,
        publication_status: PublicationStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Provider], int]:
        return self._repo.list(
            search=search,
            provider_type=provider_type,
            visit_stability=visit_stability,
            emergency_services_available=emergency_services_available,
            status=status,
            publication_status=publication_status,
            page=page,
            page_size=page_size,
        )

    def get(self, id: UUID) -> Provider:
        provider = self._repo.get_by_id(id)
        if provider is None:
            raise ProviderNotFoundError(str(id))
        return provider

    def create(
        self,
        *,
        core_fields: dict,
        specialization_ids: list[UUID],
        primary_location: dict | None,
        phones: list[dict] | None = None,
        emails: list[dict] | None = None,
        doctor_profile: dict | None = None,
        language_ids: list[UUID] | None = None,
        qualifications: list[dict] | None = None,
        admin_form_version: int | None = None,
        initial_visit: dict | None = None,
        audit_context: AuditContext | None = None,
    ) -> Provider:
        # Validate specialization IDs before touching the DB rows.
        for spec_id in specialization_ids:
            spec = self._repo.get_specialization(spec_id)
            if spec is None or not spec.is_active:
                raise SpecializationNotFoundError(str(spec_id))
        for language_id in language_ids or []:
            language = self._repo.get_language(language_id)
            if language is None or not language.is_active:
                raise ValueError(f"Language not found or inactive: {language_id}")

        try:
            provider = self._repo.create(**core_fields)
            if initial_visit:
                if provider.provider_type != ProviderType.DOCTOR or provider.doctor_availability != DoctorAvailability.VISITING:
                    raise ValueError("A visit requires a visiting doctor.")
                self._repo.add_visit(provider.id, initial_visit)
            for spec_id in dict.fromkeys(specialization_ids):  # dedupe, keep order
                self._repo.add_specialization(provider.id, spec_id)
            if primary_location is not None:
                primary_location["is_primary"] = True
                self._repo.add_location(provider.id, **primary_location)
            # Bulk-insert phones/emails; keep at most one primary of each.
            seen_primary_phone = False
            for phone_fields in phones or []:
                if phone_fields.get("is_primary"):
                    if seen_primary_phone:
                        phone_fields["is_primary"] = False
                    seen_primary_phone = True
                self._repo.add_phone(provider.id, **phone_fields)
            seen_primary_email = False
            for email_fields in emails or []:
                if email_fields.get("is_primary"):
                    if seen_primary_email:
                        email_fields["is_primary"] = False
                    seen_primary_email = True
                self._repo.add_email(provider.id, **email_fields)
            if language_ids is not None:
                self._repo.replace_languages(provider.id, language_ids)
            if provider.provider_type == ProviderType.DOCTOR and qualifications is not None:
                self._repo.replace_qualifications(provider.id, qualifications)
            # Doctor-only professional profile — never applied to other types.
            if (
                provider.provider_type == ProviderType.DOCTOR
                and doctor_profile
                and any(v is not None for v in doctor_profile.values())
            ):
                self._repo.upsert_doctor_profile(provider.id, doctor_profile)
            self._record(
                "provider.created",
                provider,
                f"Created {provider.provider_type.value.title()} provider “{provider.name}”.",
                context=audit_context,
                changes=[
                    {"field": key, "before": None, "after": value}
                    for key, value in core_fields.items()
                    if key not in {"email", "phone"}
                ],
            )
            self._repo.commit()
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError("Duplicate specialization assignment.")
        except Exception:
            self._repo.rollback()
            raise
        return self.get(provider.id)

    def update(
        self, id: UUID, *, update_fields: dict, doctor_profile: dict | None = None,
        language_ids: list[UUID] | None = None, qualifications: list[dict] | None = None,
        admin_form_version: int | None = None,
        audit_context: AuditContext | None = None,
    ) -> Provider:
        if self._repo.lock_provider(id) is None:
            raise ProviderNotFoundError(str(id))
        provider = self.get(id)
        effective_type = update_fields.get("provider_type", provider.provider_type)
        effective_availability = update_fields.get("doctor_availability", provider.doctor_availability)
        if effective_type != ProviderType.DOCTOR:
            if update_fields.get("doctor_availability") is not None:
                raise ValueError("Doctor availability is only available for doctors.")
            if provider.provider_type == ProviderType.DOCTOR and provider.doctor_visits:
                raise ValueError("A doctor with recorded visits cannot change provider type.")
            if provider.provider_type == ProviderType.DOCTOR:
                update_fields["doctor_availability"] = None
        if effective_availability != DoctorAvailability.VISITING and provider.doctor_visits and effective_type == ProviderType.DOCTOR:
            raise ValueError("A doctor with recorded visits must remain visiting.")
        effective_stability = update_fields.get("visit_stability", provider.visit_stability)
        radius = update_fields.get("maximum_working_radius_km", provider.maximum_working_radius_km)
        stability_changed = (
            "visit_stability" in update_fields
            and update_fields["visit_stability"] != provider.visit_stability
        )
        radius_changed = "maximum_working_radius_km" in update_fields
        if admin_form_version == 2 and effective_stability == VisitStability.STABLE_VISIT and (
            radius is None or float(radius) <= 0
        ) and (stability_changed or radius_changed or provider.maximum_working_radius_km is not None):
            raise ValueError("stable visits require a positive radius")
        if admin_form_version == 2 and effective_stability == VisitStability.NOT_STABLE_VISIT:
            update_fields["maximum_working_radius_km"] = None
        emergency = update_fields.get("emergency_services_available", provider.emergency_services_available)
        number = update_fields.get("emergency_contact_number", provider.emergency_contact_number)
        if admin_form_version == 2 and emergency and not (number or "").strip() and (
            "emergency_services_available" in update_fields or "emergency_contact_number" in update_fields
        ):
            raise ValueError("emergency contact number is required")
        if admin_form_version == 2 and emergency is False and "emergency_services_available" in update_fields:
            update_fields["emergency_contact_name"] = None
            update_fields["emergency_contact_number"] = None
        existing_language_ids = {row.language_id for row in provider.provider_languages}
        for language_id in language_ids or []:
            language = self._repo.get_language(language_id)
            if language is None or (not language.is_active and language_id not in existing_language_ids):
                raise ValueError(f"Language not found or inactive: {language_id}")
        changes = [
            {"field": key, "before": getattr(provider, key), "after": value}
            for key, value in update_fields.items()
            if getattr(provider, key, object()) != value
        ]
        if "name" in update_fields and update_fields["name"] is not None:
            update_fields["name"] = update_fields["name"].strip()
        self._repo.update(provider, update_fields)
        # Apply doctor profile only when the provider is (now) a doctor.
        if doctor_profile and provider.provider_type == ProviderType.DOCTOR:
            has_values = any(v is not None for v in doctor_profile.values())
            if has_values or self._repo.get_doctor_profile(provider.id) is not None:
                self._repo.upsert_doctor_profile(provider.id, doctor_profile)
                changes.extend(
                    {
                        "field": f"professional.{key}",
                        "before": None,
                        "after": value,
                    }
                    for key, value in doctor_profile.items()
                )
        if language_ids is not None:
            self._repo.replace_languages(provider.id, language_ids)
        if qualifications is not None and provider.provider_type == ProviderType.DOCTOR:
            self._repo.replace_qualifications(provider.id, qualifications)
        if changes:
            self._record(
                "provider.updated", provider, f"Updated provider “{provider.name}”.",
                context=audit_context, changes=changes,
            )
        self._repo.commit()
        return self.get(id)

    def _validate_visit(self, provider: Provider, fields: dict, *, exclude_id: UUID | None = None) -> None:
        if provider.provider_type != ProviderType.DOCTOR or provider.doctor_availability != DoctorAvailability.VISITING:
            raise ValueError("Visits are only available for visiting doctors.")
        start, end = fields["start_date"], fields["end_date"]
        if start > end:
            raise ValueError("Visit end date must be on or after start date.")
        if any(v.start_date <= end and start <= v.end_date for v in self._repo.visits(provider.id) if v.id != exclude_id):
            raise ValueError("Visit dates overlap an existing visit (including endpoints).")

    def add_visit(self, provider_id: UUID, fields: dict, *, audit_context: AuditContext | None = None) -> Provider:
        provider = self._repo.lock_provider(provider_id)
        if provider is None:
            raise ProviderNotFoundError(str(provider_id))
        self._validate_visit(provider, fields)
        self._repo.add_visit(provider_id, fields)
        self._record("provider.visit_added", provider, "Scheduled a doctor visit.", context=audit_context)
        self._repo.commit()
        return self.get(provider_id)

    def update_visit(self, provider_id: UUID, visit_id: UUID, fields: dict, *, audit_context: AuditContext | None = None) -> Provider:
        provider = self._repo.lock_provider(provider_id)
        if provider is None:
            raise ProviderNotFoundError(str(provider_id))
        visit = next((v for v in self._repo.visits(provider_id) if v.id == visit_id), None)
        if visit is None:
            raise VisitNotFoundError(str(visit_id))
        if visit.start_date <= date.today():
            raise ValueError("Only upcoming visits can be edited.")
        self._validate_visit(provider, fields, exclude_id=visit_id)
        for key, value in fields.items():
            setattr(visit, key, value)
        self._record("provider.visit_updated", provider, "Corrected an upcoming doctor visit.", context=audit_context)
        self._repo.commit()
        return self.get(provider_id)

    def set_status(self, id: UUID, *, status: ProviderStatus,
                   audit_context: AuditContext | None = None) -> Provider:
        provider = self.get(id)
        before = provider.status.value
        provider.status = status
        self._record(
            "provider.status_changed", provider, f"Changed provider status to {status.value.title()}.",
            context=audit_context,
            changes=[{"field": "status", "before": before, "after": status.value}],
        )
        self._repo.commit()
        return self.get(id)

    def set_publication(
        self, id: UUID, *, publication_status: PublicationStatus,
        audit_context: AuditContext | None = None,
    ) -> Provider:
        provider = self.get(id)
        before = provider.publication_status.value
        provider.publication_status = publication_status
        self._record(
            "provider.publication_changed",
            provider,
            f"Changed publication status to {publication_status.value.title()}.",
            context=audit_context,
            changes=[{"field": "publication_status", "before": before, "after": publication_status.value}],
        )
        self._repo.commit()
        return self.get(id)

    # ── Specializations ───────────────────────────────────────────────────────

    def add_specialization(self, provider_id: UUID, spec_id: UUID,
                           audit_context: AuditContext | None = None) -> Provider:
        provider = self.get(provider_id)
        spec = self._repo.get_specialization(spec_id)
        if spec is None or not spec.is_active:
            raise SpecializationNotFoundError(str(spec_id))
        if self._repo.get_assignment(provider_id, spec_id) is not None:
            raise DuplicateSpecializationError(
                "Specialization is already assigned to this provider."
            )
        try:
            self._repo.add_specialization(provider_id, spec_id)
            self._record(
                "provider.specialization_added", provider, "Added a specialization to the provider.",
                context=audit_context, metadata={"specialization_id": str(spec_id)},
            )
            self._repo.commit()
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError(
                "Specialization is already assigned to this provider."
            )
        return self.get(provider_id)

    def remove_specialization(self, provider_id: UUID, spec_id: UUID,
                              audit_context: AuditContext | None = None) -> Provider:
        provider = self.get(provider_id)
        link = self._repo.get_assignment(provider_id, spec_id)
        if link is None:
            raise SpecializationNotFoundError(str(spec_id))
        self._repo.remove_specialization(link)
        self._record(
            "provider.specialization_removed", provider, "Removed a specialization from the provider.",
            context=audit_context, metadata={"specialization_id": str(spec_id)},
        )
        self._repo.commit()
        return self.get(provider_id)

    # ── Locations ─────────────────────────────────────────────────────────────

    def add_location(self, provider_id: UUID, *, fields: dict,
                     audit_context: AuditContext | None = None) -> ProviderLocation:
        provider = self.get(provider_id)
        if fields.get("is_primary"):
            self._repo.clear_primary_location(provider_id)
        loc = self._repo.add_location(provider_id, **fields)
        self._record("provider.location_added", provider, "Added a provider location.",
                     context=audit_context, metadata={"location_name": loc.name})
        self._repo.commit()
        return loc

    def update_location(
        self, provider_id: UUID, loc_id: UUID, *, update_fields: dict,
        audit_context: AuditContext | None = None,
    ) -> ProviderLocation:
        provider = self.get(provider_id)
        loc = self._repo.get_location(provider_id, loc_id)
        if loc is None:
            raise LocationNotFoundError(str(loc_id))
        if update_fields.get("is_primary"):
            self._repo.clear_primary_location(provider_id)
        changes = [
            {"field": key, "before": getattr(loc, key), "after": value}
            for key, value in update_fields.items()
            if getattr(loc, key) != value
        ]
        for key, value in update_fields.items():
            setattr(loc, key, value)
        self._record("provider.location_updated", provider, "Updated a provider location.",
                     context=audit_context, changes=changes, metadata={"location_name": loc.name})
        self._repo.commit()
        return loc

    def delete_location(self, provider_id: UUID, loc_id: UUID,
                        audit_context: AuditContext | None = None) -> None:
        provider = self.get(provider_id)
        loc = self._repo.get_location(provider_id, loc_id)
        if loc is None:
            raise LocationNotFoundError(str(loc_id))
        self._repo.delete_location(loc)
        self._record("provider.location_deleted", provider, "Deleted a provider location.",
                     context=audit_context, metadata={"location_name": loc.name})
        self._repo.commit()

    # ── Phones ────────────────────────────────────────────────────────────────

    def add_provider_phone(self, provider_id: UUID, *, fields: dict,
                           audit_context: AuditContext | None = None) -> ProviderPhone:
        provider = self.get(provider_id)
        if fields.get("is_primary"):
            self._repo.clear_primary_phone(provider_id)
        phone = self._repo.add_phone(provider_id, **fields)
        self._record("provider.phone_added", provider, "Added a provider phone number.", context=audit_context)
        self._repo.commit()
        return phone

    def remove_provider_phone(self, provider_id: UUID, phone_id: UUID,
                              audit_context: AuditContext | None = None) -> None:
        provider = self.get(provider_id)
        phone = self._repo.get_phone(provider_id, phone_id)
        if phone is None:
            raise PhoneNotFoundError(str(phone_id))
        self._repo.delete_phone(phone)
        self._record("provider.phone_removed", provider, "Removed a provider phone number.", context=audit_context)
        self._repo.commit()

    # ── Emails ────────────────────────────────────────────────────────────────

    def add_provider_email(self, provider_id: UUID, *, fields: dict,
                           audit_context: AuditContext | None = None) -> ProviderEmail:
        provider = self.get(provider_id)
        if fields.get("is_primary"):
            self._repo.clear_primary_email(provider_id)
        email = self._repo.add_email(provider_id, **fields)
        self._record("provider.email_added", provider, "Added a provider email address.", context=audit_context)
        self._repo.commit()
        return email

    def remove_provider_email(self, provider_id: UUID, email_id: UUID,
                              audit_context: AuditContext | None = None) -> None:
        provider = self.get(provider_id)
        email = self._repo.get_email(provider_id, email_id)
        if email is None:
            raise EmailNotFoundError(str(email_id))
        self._repo.delete_email(email)
        self._record("provider.email_removed", provider, "Removed a provider email address.", context=audit_context)
        self._repo.commit()

    # ── Photos ────────────────────────────────────────────────────────────────

    def add_photo(self, provider_id: UUID, *, fields: dict,
                  audit_context: AuditContext | None = None) -> ProviderPhoto:
        provider = self.get(provider_id)
        if fields.get("is_thumbnail"):
            self._repo.clear_thumbnail(provider_id)
        photo = self._repo.add_photo(provider_id, **fields)
        self._record("provider.photo_added", provider, "Added a provider photo.", context=audit_context)
        self._repo.commit()
        return photo

    def update_photo(
        self, provider_id: UUID, photo_id: UUID, *, update_fields: dict,
        audit_context: AuditContext | None = None,
    ) -> ProviderPhoto:
        provider = self.get(provider_id)
        photo = self._repo.get_photo(provider_id, photo_id)
        if photo is None:
            raise PhotoNotFoundError(str(photo_id))
        changes = [
            {"field": key, "before": getattr(photo, key), "after": value}
            for key, value in update_fields.items()
            if getattr(photo, key) != value
        ]
        for key, value in update_fields.items():
            setattr(photo, key, value)
        self._record("provider.photo_updated", provider, "Updated a provider photo.",
                     context=audit_context, changes=changes)
        self._repo.commit()
        return photo

    def delete_photo(self, provider_id: UUID, photo_id: UUID,
                     audit_context: AuditContext | None = None) -> None:
        provider = self.get(provider_id)
        photo = self._repo.get_photo(provider_id, photo_id)
        if photo is None:
            raise PhotoNotFoundError(str(photo_id))
        self._repo.delete_photo(photo)
        self._record("provider.photo_deleted", provider, "Deleted a provider photo.", context=audit_context)
        self._repo.commit()

    def set_thumbnail(self, provider_id: UUID, photo_id: UUID,
                      audit_context: AuditContext | None = None) -> ProviderPhoto:
        provider = self.get(provider_id)
        photo = self._repo.get_photo(provider_id, photo_id)
        if photo is None:
            raise PhotoNotFoundError(str(photo_id))
        self._repo.clear_thumbnail(provider_id)
        photo.is_thumbnail = True
        self._record("provider.thumbnail_set", provider, "Set the provider photo thumbnail.", context=audit_context)
        self._repo.commit()
        return photo
