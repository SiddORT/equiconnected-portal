"""
User Pydantic schemas.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import PublicAccountApprovalStatus


class UserCreate(BaseModel):
    """Used only by the seed script — never exposed as a public endpoint."""
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role_name: str = "admin"

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class UserResponse(BaseModel):
    """Safe user representation — never exposes password_hash."""
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class PublicRegistrantResponse(BaseModel):
    """Administrator-safe view of a public account registration."""

    id: uuid.UUID
    first_name: str | None
    last_name: str | None
    full_name: str
    email: str
    mobile_number: str | None
    country: str | None
    city: str | None
    roles: list[str]
    email_verified_at: datetime | None
    approval_status: PublicAccountApprovalStatus
    approval_decided_at: datetime | None
    approval_decided_by: uuid.UUID | None
    created_at: datetime
