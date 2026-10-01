"""Request and response schemas for provider invitations."""
from datetime import datetime
from math import isfinite
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import InvitationStatus, ProviderType, VisitStability
from app.schemas.common import PaginatedResponse
from app.schemas.doctor import QualificationCreate
from app.schemas.provider import EmailCreate, LocationCreate, PhoneCreate, PhotoCreate


class InvitationCreate(BaseModel):
    recipient_email: EmailStr
    provider_type: ProviderType
    provider_id: UUID | None = None
    provider_name: str | None = Field(None, min_length=1, max_length=300)
    first_name: str | None = Field(None, max_length=150)
    last_name: str | None = Field(None, max_length=150)
    visit_stability: VisitStability = VisitStability.STABLE_VISIT

    @field_validator("provider_name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def require_doctor_names(self):
        if self.provider_id is None and self.provider_type == ProviderType.DOCTOR and (
            "first_name" in self.model_fields_set or "last_name" in self.model_fields_set
        ):
            if not self.first_name or not self.first_name.strip() or not self.last_name or not self.last_name.strip():
                raise ValueError("First name and last name are required for a doctor invitation.")
            if len(self.first_name.strip()) + len(self.last_name.strip()) + 1 > 300:
                raise ValueError("Doctor full name must be 300 characters or fewer.")
        return self


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
    portal_user_id: UUID | None = None
    portal_access_sent_at: datetime | None = None
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
    recipient_email: EmailStr
    emails_edited: bool
    provider: dict


class DraftSaveRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    first_name: str | None = Field(None, max_length=150)
    last_name: str | None = Field(None, max_length=150)
    description: str | None = Field(None, max_length=5000)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=500)
    visit_stability: VisitStability | None = None
    maximum_working_radius_km: float | None = None
    emergency_services_available: bool | None = None
    emergency_contact_number: str | None = Field(None, max_length=50)
    specialization_ids: list[UUID] | None = None
    language_ids: list[UUID] | None = None
    locations: list[LocationCreate] | None = None
    phones: list[PhoneCreate] | None = None
    emails: list[EmailCreate] | None = None
    photos: list[PhotoCreate] | None = None
    professional_title: str | None = Field(None, max_length=200)
    biography: str | None = Field(None, max_length=10000)
    years_experience: int | None = Field(None, ge=0, le=100)
    experience_description: str | None = Field(None, max_length=5000)
    qualifications: list[QualificationCreate] | None = None

    @field_validator("maximum_working_radius_km")
    @classmethod
    def radius_must_be_finite(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("maximum working radius must be finite")
        return value


class SubmitRequest(DraftSaveRequest):
    name: str = Field(..., min_length=1, max_length=300)
    visit_stability: VisitStability
    password: str = Field(..., min_length=8, max_length=128)
    password_confirmation: str = Field(..., min_length=8, max_length=128)
    # Doctor invitations only: the final set of organizations to associate.
    # Reconciled atomically with the submit — PENDING relationships are created
    # (or removed) in the same transaction so nothing persists on a failed submit.
    organization_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def validate_portal_password(self):
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match.")
        if not (
            re.search(r"[a-z]", self.password)
            and re.search(r"[A-Z]", self.password)
            and re.search(r"\d", self.password)
        ):
            raise ValueError(
                "Password must include an uppercase letter, a lowercase letter, and a number."
            )
        return self