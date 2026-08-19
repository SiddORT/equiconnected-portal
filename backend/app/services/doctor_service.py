"""
DoctorService — business logic for Doctor providers.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.enums import (
    DoctorOrganizationStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.doctor import DoctorOrganization, DoctorProfile, DoctorQualification
from app.models.provider import Provider
from app.repositories.doctor_repository import DoctorRepository


# ── Domain exceptions ─────────────────────────────────────────────────────────

class DoctorNotFoundError(Exception):
    """Raised when a doctor provider is not found."""

class OrgNotFoundError(Exception):
    """Raised when an org provider (Hospital/Clinic) is not found or wrong type."""

class OrgRelationshipNotFoundError(Exception):
    """Raised when the doctor↔org relationship does not exist."""

class DuplicateOrgRelationshipError(Exception):
    """Raised when the same org relationship already exists."""

class DoctorOrgSelfReferenceError(Exception):
    """Raised when trying to associate a doctor with itself."""

class QualificationNotFoundError(Exception):
    """Raised when a qualification is not found."""

class SpecializationNotFoundError(Exception):
    """Raised when a specialization is not found or inactive."""

class DuplicateSpecializationError(Exception):
    """Raised when a specialization is already assigned."""


# ── Service ───────────────────────────────────────────────────────────────────

class DoctorService:
    def __init__(self, repo: DoctorRepository) -> None:
        self._repo = repo

    # ── Reads ─────────────────────────────────────────────────────────────────

    def list(
        self,
        *,
        search: str | None = None,
        specialization_id: UUID | None = None,
        organization_id: UUID | None = None,
        visit_stability: VisitStability | None = None,
        status: ProviderStatus | None = None,
        publication_status: PublicationStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Provider], int]:
        return self._repo.list(
            search=search,
            specialization_id=specialization_id,
            organization_id=organization_id,
            visit_stability=visit_stability,
            status=status,
            publication_status=publication_status,
            page=page,
            page_size=page_size,
        )

    def get(self, doctor_id: UUID) -> Provider:
        doctor = self._repo.get_by_id(doctor_id)
        if doctor is None:
            raise DoctorNotFoundError(str(doctor_id))
        return doctor

    # ── Create ────────────────────────────────────────────────────────────────

    def create(
        self,
        *,
        name: str,
        visit_stability: VisitStability,
        status: ProviderStatus = ProviderStatus.ACTIVE,
        publication_status: PublicationStatus = PublicationStatus.UNPUBLISHED,
        website: str | None = None,
        professional_title: str | None = None,
        biography: str | None = None,
        years_experience: int | None = None,
        experience_description: str | None = None,
        specialization_ids: list[UUID] | None = None,
        organization_ids: list[UUID] | None = None,
        primary_organization_id: UUID | None = None,
        phones: list[dict] | None = None,
        emails: list[dict] | None = None,
    ) -> Provider:
        # Validate specializations
        for spec_id in (specialization_ids or []):
            spec = self._repo.get_specialization(spec_id)
            if spec is None or not spec.is_active:
                raise SpecializationNotFoundError(str(spec_id))

        # Validate organizations
        for org_id in (organization_ids or []):
            if self._repo.get_org_provider(org_id) is None:
                raise OrgNotFoundError(str(org_id))

        if primary_organization_id and primary_organization_id not in (organization_ids or []):
            if self._repo.get_org_provider(primary_organization_id) is None:
                raise OrgNotFoundError(str(primary_organization_id))

        try:
            provider = self._repo.create_provider(
                provider_type=ProviderType.DOCTOR,
                name=name,
                visit_stability=visit_stability,
                status=status,
                publication_status=publication_status,
                website=website,
            )
            # Doctor profile
            self._repo.create_profile(
                provider.id,
                professional_title=professional_title,
                biography=biography,
                years_experience=years_experience,
                experience_description=experience_description,
            )
            # Specializations
            for spec_id in dict.fromkeys(specialization_ids or []):
                self._repo.add_specialization(provider.id, spec_id)
            # Organizations
            added_org_ids: set[UUID] = set()
            for org_id in (organization_ids or []):
                if org_id in added_org_ids:
                    continue
                added_org_ids.add(org_id)
                self._repo.add_org_relationship(
                    provider.id,
                    org_id,
                    is_primary=(org_id == primary_organization_id),
                    status=DoctorOrganizationStatus.ACTIVE,
                )
            # Handle primary_org not in organization_ids
            if primary_organization_id and primary_organization_id not in added_org_ids:
                self._repo.add_org_relationship(
                    provider.id,
                    primary_organization_id,
                    is_primary=True,
                    status=DoctorOrganizationStatus.ACTIVE,
                )
            # Phones & emails
            for phone_fields in (phones or []):
                from app.repositories.provider_repository import ProviderRepository
                ProviderRepository(self._repo._db).add_phone(provider.id, **phone_fields)
            for email_fields in (emails or []):
                from app.repositories.provider_repository import ProviderRepository
                ProviderRepository(self._repo._db).add_email(provider.id, **email_fields)

            self._repo.commit()
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError("Duplicate specialization or org assignment.")

        return self.get(provider.id)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, doctor_id: UUID, *, update_fields: dict) -> Provider:
        doctor = self.get(doctor_id)
        # Split provider-level vs profile-level fields
        profile_fields = {
            "professional_title", "biography", "years_experience", "experience_description"
        }
        provider_updates = {k: v for k, v in update_fields.items() if k not in profile_fields}
        profile_updates = {k: v for k, v in update_fields.items() if k in profile_fields}

        if provider_updates:
            self._repo.update_provider(doctor, provider_updates)

        if profile_updates:
            profile = self._repo.get_profile(doctor_id)
            if profile is None:
                self._repo.create_profile(doctor_id, **profile_updates)
            else:
                self._repo.update_profile(profile, profile_updates)

        self._repo.commit()
        return self.get(doctor_id)

    def set_status(self, doctor_id: UUID, *, status: ProviderStatus) -> Provider:
        doctor = self.get(doctor_id)
        doctor.status = status
        self._repo.commit()
        return self.get(doctor_id)

    def set_publication(self, doctor_id: UUID, *, publication_status: PublicationStatus) -> Provider:
        doctor = self.get(doctor_id)
        doctor.publication_status = publication_status
        self._repo.commit()
        return self.get(doctor_id)

    # ── Specializations ───────────────────────────────────────────────────────

    def add_specialization(self, doctor_id: UUID, spec_id: UUID) -> Provider:
        self.get(doctor_id)
        spec = self._repo.get_specialization(spec_id)
        if spec is None or not spec.is_active:
            raise SpecializationNotFoundError(str(spec_id))
        if self._repo.get_spec_assignment(doctor_id, spec_id) is not None:
            raise DuplicateSpecializationError("Already assigned.")
        try:
            self._repo.add_specialization(doctor_id, spec_id)
            self._repo.commit()
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError("Already assigned.")
        return self.get(doctor_id)

    def remove_specialization(self, doctor_id: UUID, spec_id: UUID) -> Provider:
        self.get(doctor_id)
        link = self._repo.get_spec_assignment(doctor_id, spec_id)
        if link is None:
            raise SpecializationNotFoundError(str(spec_id))
        self._repo.remove_specialization(link)
        self._repo.commit()
        return self.get(doctor_id)

    # ── Qualifications ────────────────────────────────────────────────────────

    def add_qualification(self, doctor_id: UUID, *, fields: dict) -> DoctorQualification:
        self.get(doctor_id)
        q = self._repo.add_qualification(doctor_id, **fields)
        self._repo.commit()
        return q

    def update_qualification(
        self, doctor_id: UUID, q_id: UUID, *, fields: dict
    ) -> DoctorQualification:
        self.get(doctor_id)
        q = self._repo.get_qualification(doctor_id, q_id)
        if q is None:
            raise QualificationNotFoundError(str(q_id))
        for key, value in fields.items():
            setattr(q, key, value)
        self._repo.commit()
        return q

    def delete_qualification(self, doctor_id: UUID, q_id: UUID) -> None:
        self.get(doctor_id)
        q = self._repo.get_qualification(doctor_id, q_id)
        if q is None:
            raise QualificationNotFoundError(str(q_id))
        self._repo.delete_qualification(q)
        self._repo.commit()

    # ── Organization relationships ─────────────────────────────────────────────

    def add_org_relationship(
        self,
        doctor_id: UUID,
        *,
        organization_id: UUID,
        status: DoctorOrganizationStatus = DoctorOrganizationStatus.ACTIVE,
        is_primary: bool = False,
    ) -> Provider:
        self.get(doctor_id)
        if organization_id == doctor_id:
            raise DoctorOrgSelfReferenceError("A doctor cannot be affiliated with itself.")
        org = self._repo.get_org_provider(organization_id)
        if org is None:
            raise OrgNotFoundError(str(organization_id))
        if self._repo.get_org_relationship(doctor_id, organization_id) is not None:
            raise DuplicateOrgRelationshipError("Relationship already exists.")
        try:
            if is_primary:
                self._repo.clear_primary_org(doctor_id)
            self._repo.add_org_relationship(
                doctor_id, organization_id, status=status, is_primary=is_primary
            )
            self._repo.commit()
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateOrgRelationshipError("Relationship already exists.")
        return self.get(doctor_id)

    def update_org_relationship(
        self, doctor_id: UUID, rel_id: UUID, *, fields: dict
    ) -> Provider:
        self.get(doctor_id)
        rel = self._repo.get_org_relationship_by_id(rel_id)
        if rel is None or rel.doctor_id != doctor_id:
            raise OrgRelationshipNotFoundError(str(rel_id))
        if fields.get("is_primary"):
            self._repo.clear_primary_org(doctor_id)
        for key, value in fields.items():
            if value is not None:
                setattr(rel, key, value)
        self._repo.commit()
        return self.get(doctor_id)

    def remove_org_relationship(self, doctor_id: UUID, rel_id: UUID) -> Provider:
        self.get(doctor_id)
        rel = self._repo.get_org_relationship_by_id(rel_id)
        if rel is None or rel.doctor_id != doctor_id:
            raise OrgRelationshipNotFoundError(str(rel_id))
        self._repo.delete_org_relationship(rel)
        self._repo.commit()
        return self.get(doctor_id)
