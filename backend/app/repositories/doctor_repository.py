"""
DoctorRepository — data access for Doctor providers and their sub-resources.

Doctors are Providers with provider_type=DOCTOR, extended by:
  - DoctorProfile (1:1)
  - DoctorQualification (1:many)
  - DoctorOrganization (M:M junction)

Delegates core Provider CRUD to ProviderRepository.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.doctor import DoctorOrganization, DoctorProfile, DoctorQualification
from app.models.enums import (
    DoctorOrganizationStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.provider import Provider, ProviderSpecialization
from app.models.specialization import Specialization


class DoctorRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Helpers ───────────────────────────────────────────────────────────────

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()

    def _doctor_options(self):
        """selectinload chain for a fully-hydrated Doctor provider."""
        return [
            selectinload(Provider.phones),
            selectinload(Provider.emails),
            selectinload(Provider.photos),
            selectinload(Provider.locations),
            selectinload(Provider.doctor_profile),
            selectinload(Provider.qualifications),
            selectinload(Provider.provider_specializations).selectinload(
                ProviderSpecialization.specialization
            ),
            selectinload(Provider.doctor_organizations).selectinload(
                DoctorOrganization.organization
            ).selectinload(Provider.photos),
        ]

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get_by_id(self, doctor_id: UUID) -> Provider | None:
        return self._db.scalar(
            select(Provider)
            .where(Provider.id == doctor_id, Provider.provider_type == ProviderType.DOCTOR)
            .options(*self._doctor_options())
        )

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
        stmt = (
            select(Provider)
            .where(Provider.provider_type == ProviderType.DOCTOR)
            .options(
                selectinload(Provider.photos),
                selectinload(Provider.doctor_profile),
                selectinload(Provider.doctor_organizations).selectinload(
                    DoctorOrganization.organization
                ).selectinload(Provider.photos),
                selectinload(Provider.provider_specializations).selectinload(
                    ProviderSpecialization.specialization
                ),
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(Provider)
            .where(Provider.provider_type == ProviderType.DOCTOR)
        )

        if search:
            term = f"%{search.strip()}%"
            # Search by doctor name or professional title (via join)
            stmt = stmt.outerjoin(Provider.doctor_profile)
            count_stmt = count_stmt.outerjoin(Provider.doctor_profile)
            cond = or_(
                Provider.name.ilike(term),
                DoctorProfile.professional_title.ilike(term),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        if specialization_id is not None:
            stmt = stmt.join(
                ProviderSpecialization,
                (ProviderSpecialization.provider_id == Provider.id)
                & (ProviderSpecialization.specialization_id == specialization_id),
            )
            count_stmt = count_stmt.join(
                ProviderSpecialization,
                (ProviderSpecialization.provider_id == Provider.id)
                & (ProviderSpecialization.specialization_id == specialization_id),
            )

        if organization_id is not None:
            stmt = stmt.join(
                DoctorOrganization,
                (DoctorOrganization.doctor_id == Provider.id)
                & (DoctorOrganization.organization_id == organization_id),
            )
            count_stmt = count_stmt.join(
                DoctorOrganization,
                (DoctorOrganization.doctor_id == Provider.id)
                & (DoctorOrganization.organization_id == organization_id),
            )

        if visit_stability is not None:
            stmt = stmt.where(Provider.visit_stability == visit_stability)
            count_stmt = count_stmt.where(Provider.visit_stability == visit_stability)

        if status is not None:
            stmt = stmt.where(Provider.status == status)
            count_stmt = count_stmt.where(Provider.status == status)

        if publication_status is not None:
            stmt = stmt.where(Provider.publication_status == publication_status)
            count_stmt = count_stmt.where(Provider.publication_status == publication_status)

        total: int = self._db.scalar(count_stmt) or 0
        stmt = stmt.order_by(Provider.name, Provider.id).offset((page - 1) * page_size).limit(page_size)
        items = list(self._db.scalars(stmt).unique().all())
        return items, total

    # ── Provider writes ───────────────────────────────────────────────────────

    def create_provider(self, **fields) -> Provider:
        provider = Provider(**fields)
        self._db.add(provider)
        self._db.flush()
        return provider

    def update_provider(self, provider: Provider, fields: dict) -> Provider:
        for key, value in fields.items():
            setattr(provider, key, value)
        self._db.flush()
        return provider

    # ── Doctor profile ────────────────────────────────────────────────────────

    def get_profile(self, doctor_id: UUID) -> DoctorProfile | None:
        return self._db.get(DoctorProfile, doctor_id)

    def create_profile(self, doctor_id: UUID, **fields) -> DoctorProfile:
        profile = DoctorProfile(provider_id=doctor_id, **fields)
        self._db.add(profile)
        self._db.flush()
        return profile

    def update_profile(self, profile: DoctorProfile, fields: dict) -> DoctorProfile:
        for key, value in fields.items():
            setattr(profile, key, value)
        self._db.flush()
        return profile

    # ── Qualifications ────────────────────────────────────────────────────────

    def add_qualification(self, doctor_id: UUID, **fields) -> DoctorQualification:
        q = DoctorQualification(provider_id=doctor_id, **fields)
        self._db.add(q)
        self._db.flush()
        return q

    def get_qualification(self, doctor_id: UUID, q_id: UUID) -> DoctorQualification | None:
        return self._db.scalar(
            select(DoctorQualification).where(
                DoctorQualification.id == q_id,
                DoctorQualification.provider_id == doctor_id,
            )
        )

    def delete_qualification(self, qual: DoctorQualification) -> None:
        self._db.delete(qual)
        self._db.flush()

    # ── Specializations ───────────────────────────────────────────────────────

    def get_specialization(self, spec_id: UUID) -> Specialization | None:
        return self._db.get(Specialization, spec_id)

    def get_spec_assignment(self, doctor_id: UUID, spec_id: UUID) -> ProviderSpecialization | None:
        return self._db.get(ProviderSpecialization, (doctor_id, spec_id))

    def add_specialization(self, doctor_id: UUID, spec_id: UUID) -> ProviderSpecialization:
        link = ProviderSpecialization(provider_id=doctor_id, specialization_id=spec_id)
        self._db.add(link)
        self._db.flush()
        return link

    def remove_specialization(self, link: ProviderSpecialization) -> None:
        self._db.delete(link)
        self._db.flush()

    # ── Organization relationships ─────────────────────────────────────────────

    def get_org_provider(self, org_id: UUID) -> Provider | None:
        return self._db.scalar(
            select(Provider)
            .where(
                Provider.id == org_id,
                Provider.provider_type.in_([ProviderType.HOSPITAL, ProviderType.CLINIC]),
            )
            .options(selectinload(Provider.photos))
        )

    def get_org_relationship(self, doctor_id: UUID, org_id: UUID) -> DoctorOrganization | None:
        return self._db.scalar(
            select(DoctorOrganization).where(
                DoctorOrganization.doctor_id == doctor_id,
                DoctorOrganization.organization_id == org_id,
            )
        )

    def get_org_relationship_by_id(self, rel_id: UUID) -> DoctorOrganization | None:
        return self._db.get(DoctorOrganization, rel_id)

    def add_org_relationship(
        self, doctor_id: UUID, org_id: UUID, **fields
    ) -> DoctorOrganization:
        rel = DoctorOrganization(doctor_id=doctor_id, organization_id=org_id, **fields)
        self._db.add(rel)
        self._db.flush()
        return rel

    def clear_primary_org(self, doctor_id: UUID) -> None:
        rels = self._db.scalars(
            select(DoctorOrganization).where(
                DoctorOrganization.doctor_id == doctor_id,
                DoctorOrganization.is_primary.is_(True),
            )
        ).all()
        for rel in rels:
            rel.is_primary = False
        self._db.flush()

    def delete_org_relationship(self, rel: DoctorOrganization) -> None:
        self._db.delete(rel)
        self._db.flush()
