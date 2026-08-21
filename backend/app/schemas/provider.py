"""
Pydantic schemas for the Healthcare Provider module.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)


def _strip(v: object) -> object:
    if isinstance(v, str):
        return v.strip()
    return v


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

    _strip_title = field_validator("professional_title", mode="before")(_strip)


class DoctorProfileOut(BaseModel):
    professional_title: str | None
    biography: str | None
    years_experience: int | None
    experience_description: str | None

    model_config = ConfigDict(from_attributes=True)


# ── Provider ──────────────────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
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
    # Doctor-only professional profile fields (ignored for other types).
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)

    _strip_name = field_validator("name", mode="before")(_strip)
    _strip_title = field_validator("professional_title", mode="before")(_strip)


class ProviderUpdate(BaseModel):
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

    _strip_name = field_validator("name", mode="before")(_strip)
    _strip_title = field_validator("professional_title", mode="before")(_strip)


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


class ProviderListItem(BaseModel):
    id: UUID
    provider_type: ProviderType
    name: str
    email: str | None
    phone: str | None
    visit_stability: VisitStability
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

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_provider(cls, provider) -> "ProviderResponse":
        return cls(
            doctor_profile=(
                DoctorProfileOut.model_validate(provider.doctor_profile)
                if getattr(provider, "doctor_profile", None) is not None
                else None
            ),
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
