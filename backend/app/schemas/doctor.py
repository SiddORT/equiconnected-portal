"""
Pydantic schemas for the Doctor module.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    DoctorOrganizationStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)


def _strip(v: object) -> object:
    if isinstance(v, str):
        return v.strip()
    return v


# ── Doctor Profile ─────────────────────────────────────────────────────────────

class DoctorProfileCreate(BaseModel):
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)


class DoctorProfileUpdate(BaseModel):
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)


class DoctorProfileResponse(BaseModel):
    professional_title: str | None
    biography: str | None
    years_experience: int | None
    experience_description: str | None

    model_config = ConfigDict(from_attributes=True)


# ── Qualifications ─────────────────────────────────────────────────────────────

class QualificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    institution: str | None = Field(None, max_length=300)
    year_obtained: int | None = Field(None, ge=1900, le=2100)
    description: str | None = Field(None, max_length=2000)
    display_order: int = Field(0, ge=0)

    _strip_title = field_validator("title", mode="before")(_strip)


class QualificationUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    institution: str | None = Field(None, max_length=300)
    year_obtained: int | None = Field(None, ge=1900, le=2100)
    description: str | None = Field(None, max_length=2000)
    display_order: int | None = Field(None, ge=0)

    _strip_title = field_validator("title", mode="before")(_strip)


class QualificationResponse(BaseModel):
    id: UUID
    provider_id: UUID
    title: str
    institution: str | None
    year_obtained: int | None
    description: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Organization relationships ─────────────────────────────────────────────────

class DoctorOrgCreate(BaseModel):
    organization_id: UUID
    status: DoctorOrganizationStatus = DoctorOrganizationStatus.ACTIVE
    is_primary: bool = False


class DoctorOrgUpdate(BaseModel):
    status: DoctorOrganizationStatus | None = None
    is_primary: bool | None = None


class OrgBriefResponse(BaseModel):
    """Minimal provider fields for org references in doctor responses."""
    id: UUID
    provider_type: ProviderType
    name: str
    thumbnail_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DoctorOrgResponse(BaseModel):
    id: UUID
    organization_id: UUID
    status: DoctorOrganizationStatus
    is_primary: bool
    created_at: datetime
    updated_at: datetime
    organization: OrgBriefResponse

    model_config = ConfigDict(from_attributes=True)


# ── Doctor create/update ───────────────────────────────────────────────────────

class DoctorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    visit_stability: VisitStability
    status: ProviderStatus = ProviderStatus.ACTIVE
    publication_status: PublicationStatus = PublicationStatus.UNPUBLISHED
    website: str | None = Field(None, max_length=500)
    # Doctor profile fields (inline for convenience)
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)
    # Relationships
    specialization_ids: list[UUID] = []
    organization_ids: list[UUID] = []
    primary_organization_id: UUID | None = None
    # Contacts
    phones: list[dict] = []
    emails: list[dict] = []

    _strip_name = field_validator("name", mode="before")(_strip)


class DoctorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    visit_stability: VisitStability | None = None
    status: ProviderStatus | None = None
    publication_status: PublicationStatus | None = None
    website: str | None = Field(None, max_length=500)
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)

    _strip_name = field_validator("name", mode="before")(_strip)


# ── Doctor responses ───────────────────────────────────────────────────────────

class SpecBriefResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class DoctorListItem(BaseModel):
    id: UUID
    name: str
    visit_stability: VisitStability
    status: ProviderStatus
    publication_status: PublicationStatus
    created_at: datetime
    updated_at: datetime
    thumbnail_url: str | None = None
    professional_title: str | None = None
    specializations: list[SpecBriefResponse] = []
    primary_organization: OrgBriefResponse | None = None
    organization_count: int = 0

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_doctor(cls, provider) -> "DoctorListItem":
        profile = provider.doctor_profile
        # Derive thumbnail from photos
        thumbnail = next(
            (ph.storage_reference for ph in provider.photos if ph.is_thumbnail),
            next((ph.storage_reference for ph in provider.photos), None),
        )
        specializations = [
            SpecBriefResponse(
                id=ps.specialization.id,
                name=ps.specialization.name,
                is_active=ps.specialization.is_active,
            )
            for ps in provider.provider_specializations
        ]
        primary_org = next(
            (rel for rel in provider.doctor_organizations if rel.is_primary), None
        )
        return cls(
            id=provider.id,
            name=provider.name,
            visit_stability=provider.visit_stability,
            status=provider.status,
            publication_status=provider.publication_status,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            thumbnail_url=thumbnail,
            professional_title=profile.professional_title if profile else None,
            specializations=specializations,
            primary_organization=OrgBriefResponse(
                id=primary_org.organization.id,
                provider_type=primary_org.organization.provider_type,
                name=primary_org.organization.name,
                thumbnail_url=next(
                    (ph.storage_reference for ph in primary_org.organization.photos if ph.is_thumbnail),
                    next((ph.storage_reference for ph in primary_org.organization.photos), None),
                ) if primary_org else None,
            ) if primary_org else None,
            organization_count=len(provider.doctor_organizations),
        )


class DoctorResponse(BaseModel):
    id: UUID
    name: str
    visit_stability: VisitStability
    status: ProviderStatus
    publication_status: PublicationStatus
    website: str | None
    created_at: datetime
    updated_at: datetime
    thumbnail_url: str | None = None
    # Profile
    professional_title: str | None = None
    biography: str | None = None
    years_experience: int | None = None
    experience_description: str | None = None
    # Related collections
    specializations: list[SpecBriefResponse] = []
    qualifications: list[QualificationResponse] = []
    organizations: list[DoctorOrgResponse] = []
    # Reuse provider sub-resources (locations, photos, phones, emails)
    # These are included via provider relationships — serialized by response builder
    phones: list[dict] = []
    emails: list[dict] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_doctor(cls, provider) -> "DoctorResponse":
        profile = provider.doctor_profile
        thumbnail = next(
            (ph.storage_reference for ph in provider.photos if ph.is_thumbnail),
            next((ph.storage_reference for ph in provider.photos), None),
        )
        specializations = [
            SpecBriefResponse(
                id=ps.specialization.id,
                name=ps.specialization.name,
                is_active=ps.specialization.is_active,
            )
            for ps in provider.provider_specializations
        ]
        qualifications = [
            QualificationResponse.model_validate(q)
            for q in sorted(provider.qualifications, key=lambda q: (q.display_order, q.created_at))
        ]
        organizations = []
        for rel in provider.doctor_organizations:
            org = rel.organization
            org_thumbnail = next(
                (ph.storage_reference for ph in org.photos if ph.is_thumbnail),
                next((ph.storage_reference for ph in org.photos), None),
            )
            organizations.append(DoctorOrgResponse(
                id=rel.id,
                organization_id=rel.organization_id,
                status=rel.status,
                is_primary=rel.is_primary,
                created_at=rel.created_at,
                updated_at=rel.updated_at,
                organization=OrgBriefResponse(
                    id=org.id,
                    provider_type=org.provider_type,
                    name=org.name,
                    thumbnail_url=org_thumbnail,
                ),
            ))
        phones = [
            {"id": str(p.id), "country_code": p.country_code, "number": p.number, "is_primary": p.is_primary}
            for p in provider.phones
        ]
        emails = [
            {"id": str(e.id), "email": e.email, "is_primary": e.is_primary}
            for e in provider.emails
        ]
        return cls(
            id=provider.id,
            name=provider.name,
            visit_stability=provider.visit_stability,
            status=provider.status,
            publication_status=provider.publication_status,
            website=provider.website,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            thumbnail_url=thumbnail,
            professional_title=profile.professional_title if profile else None,
            biography=profile.biography if profile else None,
            years_experience=profile.years_experience if profile else None,
            experience_description=profile.experience_description if profile else None,
            specializations=specializations,
            qualifications=qualifications,
            organizations=organizations,
            phones=phones,
            emails=emails,
        )
