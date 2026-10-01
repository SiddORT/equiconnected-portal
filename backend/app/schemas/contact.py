"""Public contact enquiry fields."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import ContactEnquiryType
from app.schemas.common import PaginatedResponse

class ContactMessageRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    enquiry_type: Literal["general", "listing", "partnership", "other"]
    phone: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("name", "message")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("This field is required.")
        return trimmed

    @field_validator("phone")
    @classmethod
    def trim_phone(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ContactEnquiryResponse(BaseModel):
    id: UUID
    name: str
    email: str
    enquiry_type: ContactEnquiryType
    phone: str | None
    message: str
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactEnquiryListResponse(PaginatedResponse[ContactEnquiryResponse]):
    pass