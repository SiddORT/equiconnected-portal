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
from app.models.provider import Provider, ProviderLocation, ProviderPhoto
from app.repositories.provider_repository import ProviderRepository


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


# ── Service ───────────────────────────────────────────────────────────────────

class ProviderService:
    def __init__(self, repo: ProviderRepository) -> None:
        self._repo = repo

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
            self._repo.commit()
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError("Duplicate specialization assignment.")
        return self.get(provider.id)

    def update(self, id: UUID, *, update_fields: dict) -> Provider:
        provider = self.get(id)
        if "name" in update_fields and update_fields["name"] is not None:
            update_fields["name"] = update_fields["name"].strip()
        self._repo.update(provider, update_fields)
        self._repo.commit()
        return self.get(id)

    def set_status(self, id: UUID, *, status: ProviderStatus) -> Provider:
        provider = self.get(id)
        provider.status = status
        self._repo.commit()
        return self.get(id)

    def set_publication(
        self, id: UUID, *, publication_status: PublicationStatus
    ) -> Provider:
        provider = self.get(id)
        provider.publication_status = publication_status
        self._repo.commit()
        return self.get(id)

    # ── Specializations ───────────────────────────────────────────────────────

    def add_specialization(self, provider_id: UUID, spec_id: UUID) -> Provider:
        self.get(provider_id)
        spec = self._repo.get_specialization(spec_id)
        if spec is None or not spec.is_active:
            raise SpecializationNotFoundError(str(spec_id))
        if self._repo.get_assignment(provider_id, spec_id) is not None:
            raise DuplicateSpecializationError(
                "Specialization is already assigned to this provider."
            )
        try:
            self._repo.add_specialization(provider_id, spec_id)
            self._repo.commit()
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError(
                "Specialization is already assigned to this provider."
            )
        return self.get(provider_id)

    def remove_specialization(self, provider_id: UUID, spec_id: UUID) -> Provider:
        self.get(provider_id)
        link = self._repo.get_assignment(provider_id, spec_id)
        if link is None:
            raise SpecializationNotFoundError(str(spec_id))
        self._repo.remove_specialization(link)
        self._repo.commit()
        return self.get(provider_id)

    # ── Locations ─────────────────────────────────────────────────────────────

    def add_location(self, provider_id: UUID, *, fields: dict) -> ProviderLocation:
        self.get(provider_id)
        if fields.get("is_primary"):
            self._repo.clear_primary_location(provider_id)
        loc = self._repo.add_location(provider_id, **fields)
        self._repo.commit()
        return loc

    def update_location(
        self, provider_id: UUID, loc_id: UUID, *, update_fields: dict
    ) -> ProviderLocation:
        self.get(provider_id)
        loc = self._repo.get_location(provider_id, loc_id)
        if loc is None:
            raise LocationNotFoundError(str(loc_id))
        if update_fields.get("is_primary"):
            self._repo.clear_primary_location(provider_id)
        for key, value in update_fields.items():
            setattr(loc, key, value)
        self._repo.commit()
        return loc

    def delete_location(self, provider_id: UUID, loc_id: UUID) -> None:
        self.get(provider_id)
        loc = self._repo.get_location(provider_id, loc_id)
        if loc is None:
            raise LocationNotFoundError(str(loc_id))
        self._repo.delete_location(loc)
        self._repo.commit()

    # ── Photos ────────────────────────────────────────────────────────────────

    def add_photo(self, provider_id: UUID, *, fields: dict) -> ProviderPhoto:
        self.get(provider_id)
        if fields.get("is_thumbnail"):
            self._repo.clear_thumbnail(provider_id)
        photo = self._repo.add_photo(provider_id, **fields)
        self._repo.commit()
        return photo

    def update_photo(
        self, provider_id: UUID, photo_id: UUID, *, update_fields: dict
    ) -> ProviderPhoto:
        self.get(provider_id)
        photo = self._repo.get_photo(provider_id, photo_id)
        if photo is None:
            raise PhotoNotFoundError(str(photo_id))
        for key, value in update_fields.items():
            setattr(photo, key, value)
        self._repo.commit()
        return photo

    def delete_photo(self, provider_id: UUID, photo_id: UUID) -> None:
        self.get(provider_id)
        photo = self._repo.get_photo(provider_id, photo_id)
        if photo is None:
            raise PhotoNotFoundError(str(photo_id))
        self._repo.delete_photo(photo)
        self._repo.commit()

    def set_thumbnail(self, provider_id: UUID, photo_id: UUID) -> ProviderPhoto:
        self.get(provider_id)
        photo = self._repo.get_photo(provider_id, photo_id)
        if photo is None:
            raise PhotoNotFoundError(str(photo_id))
        self._repo.clear_thumbnail(provider_id)
        photo.is_thumbnail = True
        self._repo.commit()
        return photo
