"""Schemas for doctor organization lookup and requests."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import OrganizationRequestStatus, ProviderType
from app.schemas.common import PaginatedResponse


class OrganizationSearchResult(BaseModel):
    id: UUID
    name: str
    provider_type: ProviderType
    city: str | None = None


class OrganizationSearchResponse(PaginatedResponse[OrganizationSearchResult]):
    pass


class OrgAssociateRequest(BaseModel):
    organization_id: UUID


class OrgRequestCreate(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=300)
    organization_type: ProviderType
    contact_email: EmailStr | None = None
    location_hint: str | None = Field(None, max_length=500)
    confirm_no_match: bool = False

    @field_validator("organization_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class OrgRequestResponse(BaseModel):
    id: UUID
    doctor_provider_id: UUID
    organization_name: str
    organization_type: ProviderType
    contact_email: EmailStr | None
    location_hint: str | None
    status: OrganizationRequestStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrgRequestListResponse(PaginatedResponse[OrgRequestResponse]):
    pass