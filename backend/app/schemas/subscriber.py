"""Schemas for public subscriber registration and administrator listing."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.enums import SubscriberRegistrationType
from app.schemas.common import MessageResponse, PaginatedResponse


class SubscriberRegistrationRequest(BaseModel):
    email: EmailStr
    registration_type: SubscriberRegistrationType

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class SubscriberRegistrationResponse(MessageResponse):
    pass


class SubscriberResponse(BaseModel):
    id: UUID
    email: str
    registration_type: SubscriberRegistrationType
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriberListResponse(PaginatedResponse[SubscriberResponse]):
    pass