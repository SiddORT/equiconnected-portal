"""
ProviderService — business logic for healthcare providers.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.enums import (
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.provider import (
    Provider,
    ProviderEmail,
    ProviderLocation,
    ProviderPhone,
    ProviderPhoto,
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
        status: ProviderStatus | None = None,
        publication_status: PublicationStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Provider], int]:
        return self._repo.list(
            search=search,
            provider_type=provider_type,
            visit_stability=visit_stability,
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
        audit_context: AuditContext | None = None,
    ) -> Provider:
        # Validate specialization IDs before touching the DB rows.
        for spec_id in specialization_ids:
            spec = self._repo.get_specialization(spec_id)
            if spec is None or not spec.is_active:
                raise SpecializationNotFoundError(str(spec_id))

        try:
            provider = self._repo.create(**core_fields)
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
        return self.get(provider.id)

    def update(
        self, id: UUID, *, update_fields: dict, doctor_profile: dict | None = None,
        audit_context: AuditContext | None = None,
    ) -> Provider:
        provider = self.get(id)
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
        if changes:
            self._record(
                "provider.updated", provider, f"Updated provider “{provider.name}”.",
                context=audit_context, changes=changes,
            )
        self._repo.commit()
        return self.get(id)

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
