"""Contracts for provider account registration and administrator review."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ProviderApplicationStatus, ProviderType, VisitStability


class ProviderApplicationDecisionRequest(BaseModel):
    rejection_reason: str | None = Field(default=None, max_length=500)

    @field_validator("rejection_reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class ProviderApplicationResponse(BaseModel):
    id: UUID
    user_id: UUID
    provider_id: UUID | None
    provider_type: ProviderType
    provider_name: str
    visit_stability: VisitStability
    review_status: ProviderApplicationStatus
    first_name: str | None
    last_name: str | None
    full_name: str
    email: str
    mobile_number: str | None
    country: str | None
    state_province: str | None
    city: str | None
    email_verified_at: datetime | None
    reviewed_by_user_id: UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)