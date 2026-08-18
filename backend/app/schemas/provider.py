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

    _strip_name = field_validator("name", mode="before")(_strip)


class ProviderUpdate(BaseModel):
    """PATCH body — all fields optional; only provided fields are updated."""
    provider_type: ProviderType | None = None
    name: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=500)
    visit_stability: VisitStability | None = None

    _strip_name = field_validator("name", mode="before")(_strip)


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

    model_config = ConfigDict(from_attributes=True)


class ProviderResponse(ProviderListItem):
    description: str | None
    website: str | None
    specializations: list[ProviderSpecializationBrief] = []
    locations: list[LocationResponse] = []
    photos: list[PhotoResponse] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_provider(cls, provider) -> "ProviderResponse":
        return cls(
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
        )
