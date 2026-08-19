"""Request and response schemas for provider invitations."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import InvitationStatus, ProviderType, VisitStability
from app.schemas.common import PaginatedResponse
from app.schemas.doctor import QualificationCreate
from app.schemas.provider import EmailCreate, LocationCreate, PhoneCreate, PhotoCreate


class InvitationCreate(BaseModel):
    recipient_email: EmailStr
    provider_type: ProviderType
    provider_id: UUID | None = None
    provider_name: str | None = Field(None, min_length=1, max_length=300)
    visit_stability: VisitStability = VisitStability.STABLE_VISIT

    @field_validator("provider_name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class InvitationResponse(BaseModel):
    id: UUID
    provider_id: UUID | None
    provider_name: str | None = None
    is_new_provider: bool = False
    provider_type: ProviderType
    recipient_email: EmailStr
    status: InvitationStatus
    expires_at: datetime
    sent_at: datetime
    accepted_at: datetime | None
    completed_at: datetime | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    # Populated only on create/resend responses, where the raw token is known.
    # It is never persisted or recoverable from the list endpoint.
    invitation_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class InvitationListResponse(PaginatedResponse[InvitationResponse]):
    pass


class InvitationTokenResponse(BaseModel):
    id: UUID
    provider_type: ProviderType
    provider: dict


class DraftSaveRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    email: EmailStr | None = None
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


class SubmitRequest(DraftSaveRequest):
    name: str = Field(..., min_length=1, max_length=300)
    visit_stability: VisitStability