"""
User Pydantic schemas.
"""
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


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
