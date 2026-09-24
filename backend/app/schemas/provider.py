"""
Pydantic schemas for the Healthcare Provider module.
"""
from datetime import datetime
from math import isfinite
import re
from decimal import Decimal
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

from app.models.enums import (
    ProviderStatus,
    ProviderType,
    ProviderProfileUpdateStatus,
    PublicationStatus,
    VisitStability,
)
from app.schemas.doctor import QualificationCreate, QualificationResponse

class AdminQualificationCreate(QualificationCreate):
    id: UUID | None = None


def _strip(v: object) -> object:
    if isinstance(v, str):
        return v.strip()
    return v

def _valid_email(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()))


# ── Location ──────────────────────────────────────────────────────────────────

class LocationCreate(BaseModel):
    name: str | None = Field(None, max_length=200)
    address_line_1: str = Field(..., min_length=1, max_length=300)
    address_line_2: str | None = Field(None, max_length=300)
    city: str = Field(..., min_length=1, max_length=150)
    state_province: str | None = Field(None, max_length=150)
    country: str | None = Field(None, max_length=150)
    postal_code: str | None = Field(None, max_length=30)
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)
    is_primary: bool = False

    _strip_addr = field_validator("address_line_1", "city", mode="before")(_strip)


class LocationUpdate(BaseModel):
    """PATCH body — all fields optional; only provided fields are updated."""
    name: str | None = Field(None, max_length=200)
    address_line_1: str | None = Field(None, min_length=1, max_length=300)
    address_line_2: str | None = Field(None, max_length=300)
    city: str | None = Field(None, min_length=1, max_length=150)
    state_province: str | None = Field(None, max_length=150)
    country: str | None = Field(None, max_length=150)
    postal_code: str | None = Field(None, max_length=30)
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)
    is_primary: bool | None = None

    _strip_addr = field_validator("address_line_1", "city", mode="before")(_strip)


class LocationResponse(BaseModel):
    id: UUID
    provider_id: UUID
    name: str | None
    address_line_1: str
    address_line_2: str | None
    city: str
    state_province: str | None
    country: str | None
    postal_code: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Photo ─────────────────────────────────────────────────────────────────────

class PhotoCreate(BaseModel):
    storage_reference: str = Field(..., min_length=1, max_length=1000)
    alt_text: str | None = Field(None, max_length=300)
    caption: str | None = Field(None, max_length=500)
    display_order: int = Field(0, ge=0)
    is_thumbnail: bool = False

    _strip_ref = field_validator("storage_reference", mode="before")(_strip)


class PhotoUpdate(BaseModel):
    """PATCH body — all fields optional; only provided fields are updated."""
    storage_reference: str | None = Field(None, min_length=1, max_length=1000)
    alt_text: str | None = Field(None, max_length=300)
    caption: str | None = Field(None, max_length=500)
    display_order: int | None = Field(None, ge=0)

    _strip_ref = field_validator("storage_reference", mode="before")(_strip)


class PhotoResponse(BaseModel):
    id: UUID
    provider_id: UUID
    storage_reference: str
    alt_text: str | None
    caption: str | None
    display_order: int
    is_thumbnail: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Phone ─────────────────────────────────────────────────────────────────────

class PhoneCreate(BaseModel):
    country_code: str = Field(..., min_length=1, max_length=10)
    number: str = Field(..., min_length=1, max_length=50)
    is_primary: bool = False

    _strip_phone = field_validator("country_code", "number", mode="before")(_strip)


class PhoneUpdate(BaseModel):
    """PATCH body — all fields optional; only provided fields are updated."""
    country_code: str | None = Field(None, min_length=1, max_length=10)
    number: str | None = Field(None, min_length=1, max_length=50)
    is_primary: bool | None = None

    _strip_phone = field_validator("country_code", "number", mode="before")(_strip)


class PhoneResponse(BaseModel):
    id: UUID
    provider_id: UUID
    country_code: str
    number: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Email ─────────────────────────────────────────────────────────────────────

class EmailCreate(BaseModel):
    email: str = Field(..., min_length=1, max_length=254)
    is_primary: bool = False

    _strip_email = field_validator("email", mode="before")(_strip)


class EmailUpdate(BaseModel):
    """PATCH body — all fields optional; only provided fields are updated."""
    email: str | None = Field(None, min_length=1, max_length=254)
    is_primary: bool | None = None

    _strip_email = field_validator("email", mode="before")(_strip)


class EmailResponse(BaseModel):
    id: UUID
    provider_id: UUID
    email: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Doctor professional info (1:1 DoctorProfile extension) ───────────────────

class DoctorProfileFields(BaseModel):
    """Shared limits with the doctor-module profile schemas."""
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)
    first_name: str | None = Field(None, max_length=150)
    last_name: str | None = Field(None, max_length=150)

    _strip_title = field_validator("professional_title", mode="before")(_strip)


class DoctorProfileOut(BaseModel):
    professional_title: str | None
    biography: str | None
    years_experience: int | None
    experience_description: str | None
    first_name: str | None
    last_name: str | None

    model_config = ConfigDict(from_attributes=True)

    @model_serializer
    def serialize_compat(self):
        data = {
            "professional_title": self.professional_title,
            "biography": self.biography,
            "years_experience": self.years_experience,
            "experience_description": self.experience_description,
        }
        # Keep legacy response shape for profiles that predate admin names.
        if self.first_name is not None:
            data["first_name"] = self.first_name
        if self.last_name is not None:
            data["last_name"] = self.last_name
        return data


# ── Provider ──────────────────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    admin_form_version: Literal[2] | None = None
    provider_type: ProviderType
    name: str = Field(..., min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=500)
    visit_stability: VisitStability
    status: ProviderStatus = ProviderStatus.ACTIVE
    publication_status: PublicationStatus = PublicationStatus.UNPUBLISHED
    specialization_ids: list[UUID] = Field(default_factory=list)
    primary_location: LocationCreate | None = None
    phones: list[PhoneCreate] = Field(default_factory=list)
    emails: list[EmailCreate] = Field(default_factory=list)
    language_ids: list[UUID] = Field(default_factory=list)
    maximum_working_radius_km: float | None = Field(None, gt=0)
    clinic_hospital_visit: bool = False
    emergency_services_available: bool = False
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_number: str | None = Field(None, max_length=50)
    # Doctor-only professional profile fields (ignored for other types).
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)
    first_name: str | None = Field(None, max_length=150)
    last_name: str | None = Field(None, max_length=150)
    qualifications: list[QualificationCreate] = Field(default_factory=list)

    _strip_name = field_validator("name", mode="before")(_strip)
    _strip_title = field_validator("professional_title", mode="before")(_strip)

    @field_validator("maximum_working_radius_km")
    @classmethod
    def radius_must_be_finite(cls, value):
        if value is not None and not isfinite(value):
            raise ValueError("maximum working radius must be finite")
        return value

    @model_validator(mode="after")
    def validate_admin_requirements(self):
        if self.admin_form_version == 2 and (self.primary_location is None or not self.primary_location.country):
            raise ValueError("primary_location with country is required")
        if self.admin_form_version == 2 and not (
            _valid_email(self.email) or any(_valid_email(item.email) for item in self.emails)
        ):
            raise ValueError("at least one email is required")
        if self.admin_form_version == 2 and self.visit_stability == VisitStability.STABLE_VISIT and (
            self.maximum_working_radius_km is None or self.maximum_working_radius_km <= 0
        ):
            raise ValueError("stable visits require a positive radius")
        if self.admin_form_version == 2 and self.visit_stability == VisitStability.NOT_STABLE_VISIT:
            self.maximum_working_radius_km = None
        if self.admin_form_version == 2 and self.emergency_services_available and not (self.emergency_contact_number or "").strip():
            raise ValueError("emergency contact number is required")
        if self.admin_form_version == 2 and not self.emergency_services_available:
            self.emergency_contact_name = self.emergency_contact_number = None
        return self


class ProviderUpdate(BaseModel):
    admin_form_version: Literal[2] | None = None
    """PATCH body — all fields optional; only provided fields are updated."""
    provider_type: ProviderType | None = None
    name: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=500)
    visit_stability: VisitStability | None = None
    # Doctor-only professional profile fields (ignored for other types).
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)
    first_name: str | None = Field(None, max_length=150)
    last_name: str | None = Field(None, max_length=150)
    language_ids: list[UUID] | None = None
    qualifications: list[AdminQualificationCreate] | None = None
    maximum_working_radius_km: float | None = Field(None, gt=0)
    clinic_hospital_visit: bool | None = None
    emergency_services_available: bool | None = None
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_number: str | None = Field(None, max_length=50)

    _strip_name = field_validator("name", mode="before")(_strip)
    _strip_title = field_validator("professional_title", mode="before")(_strip)

    @field_validator("maximum_working_radius_km")
    @classmethod
    def radius_must_be_finite(cls, value):
        if value is not None and not isfinite(value):
            raise ValueError("maximum working radius must be finite")
        return value


class ProviderStatusUpdate(BaseModel):
    status: ProviderStatus


class ProviderPublicationUpdate(BaseModel):
    publication_status: PublicationStatus


class ProviderSpecializationAdd(BaseModel):
    specialization_id: UUID


class ProviderSpecializationBrief(BaseModel):
    id: UUID
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ProviderLanguageBrief(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ProviderListItem(BaseModel):
    id: UUID
    provider_type: ProviderType
    name: str
    email: str | None
    phone: str | None
    visit_stability: VisitStability
    emergency_services_available: bool
    status: ProviderStatus
    publication_status: PublicationStatus
    created_at: datetime
    updated_at: datetime
    thumbnail_url: str | None = None
    average_rating: float | None = None
    review_count: int = 0

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_provider_row(
        cls,
        provider,
        *,
        average_rating: float | None = None,
        review_count: int = 0,
    ) -> "ProviderListItem":
        """Build a list item, preferring the primary phone/email entries over
        the legacy single-value columns (which are null going forward)."""
        primary_email = next(
            (e.email for e in provider.emails if e.is_primary),
            next((e.email for e in provider.emails), None),
        )
        primary_phone = next(
            (f"{p.country_code} {p.number}" for p in provider.phones if p.is_primary),
            next((f"{p.country_code} {p.number}" for p in provider.phones), None),
        )
        thumbnail = next(
            (ph.storage_reference for ph in provider.photos if ph.is_thumbnail),
            next((ph.storage_reference for ph in provider.photos), None),
        )
        return cls(
            id=provider.id,
            provider_type=provider.provider_type,
            name=provider.name,
            email=primary_email or provider.email,
            phone=primary_phone or provider.phone,
            visit_stability=provider.visit_stability,
            emergency_services_available=provider.emergency_services_available is True,
            status=provider.status,
            publication_status=provider.publication_status,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            thumbnail_url=thumbnail,
            average_rating=average_rating,
            review_count=review_count,
        )


class ProviderResponse(ProviderListItem):
    description: str | None
    website: str | None
    specializations: list[ProviderSpecializationBrief] = []
    locations: list[LocationResponse] = []
    photos: list[PhotoResponse] = []
    phones: list[PhoneResponse] = []
    emails: list[EmailResponse] = []
    doctor_profile: DoctorProfileOut | None = None
    doctor_fields_available: bool = False
    maximum_working_radius_km: float | None = None
    clinic_hospital_visit: bool | None = None
    emergency_services_available: bool | None = None
    emergency_contact_name: str | None = None
    emergency_contact_number: str | None = None
    languages: list[ProviderLanguageBrief] = []
    qualifications: list[QualificationResponse] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_provider(cls, provider) -> "ProviderResponse":
        return cls(
            doctor_profile=(
                DoctorProfileOut.model_validate(provider.doctor_profile)
                if getattr(provider, "doctor_profile", None) is not None
                else None
            ),
            doctor_fields_available=provider.provider_type == ProviderType.DOCTOR,
            maximum_working_radius_km=float(provider.maximum_working_radius_km) if provider.maximum_working_radius_km is not None else None,
            clinic_hospital_visit=provider.clinic_hospital_visit,
            emergency_services_available=provider.emergency_services_available,
            emergency_contact_name=provider.emergency_contact_name,
            emergency_contact_number=provider.emergency_contact_number,
            languages=[ProviderLanguageBrief.model_validate(x.language) for x in provider.provider_languages],
            qualifications=[QualificationResponse.model_validate(x) for x in provider.qualifications],
            id=provider.id,
            provider_type=provider.provider_type,
            name=provider.name,
            description=provider.description,
            email=provider.email,
            phone=provider.phone,
            website=provider.website,
            visit_stability=provider.visit_stability,
            status=provider.status,
            publication_status=provider.publication_status,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            specializations=[
                ProviderSpecializationBrief.model_validate(ps.specialization)
                for ps in provider.provider_specializations
            ],
            locations=[
                LocationResponse.model_validate(loc) for loc in provider.locations
            ],
            photos=[
                PhotoResponse.model_validate(p)
                for p in sorted(provider.photos, key=lambda p: (p.display_order, p.created_at))
            ],
            phones=[
                PhoneResponse.model_validate(ph)
                for ph in sorted(provider.phones, key=lambda ph: (not ph.is_primary, ph.created_at))
            ],
            emails=[
                EmailResponse.model_validate(em)
                for em in sorted(provider.emails, key=lambda em: (not em.is_primary, em.created_at))
            ],
        )


class ProviderPortalUpdate(BaseModel):
    """Editable fields for the account owner of a completed invitation.

    Administrative lifecycle fields deliberately do not appear here.
    """

    name: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=500)
    visit_stability: VisitStability | None = None
    specialization_ids: list[UUID] | None = None
    locations: list[LocationCreate] | None = None
    phones: list[PhoneCreate] | None = None
    emails: list[EmailCreate] | None = None
    photos: list[PhotoCreate] | None = None
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)
    qualifications: list[QualificationCreate] | None = None

    _strip_name = field_validator("name", mode="before")(_strip)
    _strip_title = field_validator("professional_title", mode="before")(_strip)


class ProviderPortalEditableProfile(ProviderPortalUpdate):
    """Complete provider-editable profile used for draft snapshots and review."""

    name: str = Field(..., min_length=1, max_length=300)
    visit_stability: VisitStability
    specialization_ids: list[UUID] = Field(default_factory=list)
    locations: list[LocationCreate] = Field(default_factory=list)
    phones: list[PhoneCreate] = Field(default_factory=list)
    emails: list[EmailCreate] = Field(default_factory=list)
    photos: list[PhotoCreate] = Field(default_factory=list)
    qualifications: list[QualificationCreate] = Field(default_factory=list)


class ProviderProfileUpdateState(BaseModel):
    id: UUID
    review_status: ProviderProfileUpdateStatus
    submitted_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by_name: str | None = None
    rejection_reason: str | None = None


class ProviderPortalResponse(BaseModel):
    """Provider-owned profile data, excluding admin-only lifecycle attributes."""

    id: UUID
    name: str
    description: str | None
    email: str | None
    phone: str | None
    website: str | None
    visit_stability: VisitStability
    specializations: list[ProviderSpecializationBrief] = []
    locations: list[LocationResponse] = []
    photos: list[PhotoResponse] = []
    phones: list[PhoneResponse] = []
    emails: list[EmailResponse] = []
    doctor_profile: DoctorProfileOut | None = None
    # This capability flag lets the portal render clinical fields without
    # exposing the provider's administrative provider_type.
    doctor_fields_available: bool = False
    qualifications: list[QualificationCreate] = []
    average_rating: float | None = None
    review_count: int = 0
    visible_reviews: list[dict] = []
    editable_profile: ProviderPortalEditableProfile
    profile_update: ProviderProfileUpdateState | None = None

    @classmethod
    def from_provider(
        cls,
        provider,
        *,
        average_rating: float | None,
        review_count: int,
        visible_reviews: list[dict],
        editable_profile: ProviderPortalEditableProfile,
        profile_update: ProviderProfileUpdateState | None = None,
    ) -> "ProviderPortalResponse":
        return cls(
            id=provider.id,
            name=provider.name,
            description=provider.description,
            email=provider.email,
            phone=provider.phone,
            website=provider.website,
            visit_stability=provider.visit_stability,
            specializations=[
                ProviderSpecializationBrief.model_validate(link.specialization)
                for link in provider.provider_specializations
            ],
            locations=[LocationResponse.model_validate(row) for row in provider.locations],
            photos=[PhotoResponse.model_validate(row) for row in provider.photos],
            phones=[PhoneResponse.model_validate(row) for row in provider.phones],
            emails=[EmailResponse.model_validate(row) for row in provider.emails],
            doctor_profile=(
                DoctorProfileOut.model_validate(provider.doctor_profile)
                if provider.doctor_profile is not None
                else None
            ),
            doctor_fields_available=provider.provider_type == ProviderType.DOCTOR,
            qualifications=[
                QualificationCreate(
                    title=row.title,
                    institution=row.institution,
                    year_obtained=row.year_obtained,
                    description=row.description,
                    display_order=row.display_order,
                )
                for row in provider.qualifications
            ],
            average_rating=average_rating,
            review_count=review_count,
            visible_reviews=visible_reviews,
            editable_profile=editable_profile,
            profile_update=profile_update,
        )


class ProviderProfileUpdateAdminResponse(BaseModel):
    id: UUID
    provider_id: UUID
    provider_name: str
    provider_type: ProviderType
    review_status: ProviderProfileUpdateStatus
    proposed_profile: ProviderPortalEditableProfile
    current_profile: ProviderPortalEditableProfile
    submitted_at: datetime
    reviewed_by_user_id: UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
