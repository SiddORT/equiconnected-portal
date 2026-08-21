"""
Authentication Pydantic schemas.
Passwords are NEVER included in response schemas.
"""
import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserProfile(BaseModel):
    """Safe user representation — never includes password_hash."""
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    full_name: str
    role: str
    roles: list[str] = []
    approval_status: str | None = None
    email_verified_at: datetime | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


PublicRoleSelection = Literal["HORSE_OWNER", "STABLE_MANAGER", "BOTH"]


class RegistrationRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    mobile_number: str = Field(min_length=6, max_length=32)
    country: str = Field(min_length=1, max_length=100)
    state_province: str = Field(max_length=100)
    city: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)
    role: PublicRoleSelection
    accept_terms: bool
    accept_privacy: bool

    @field_validator("email")
    @classmethod
    def normalise_registration_email(cls, value: str) -> str:
        return value.lower().strip()

    @field_validator("first_name", "last_name", "country", "city")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required.")
        return value

    @field_validator("state_province")
    @classmethod
    def trim_state_province(cls, value: str) -> str:
        return value.strip()

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile_number(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[0-9+\-()\s]{6,32}", value):
            raise ValueError("Enter a valid mobile number.")
        return value

    @model_validator(mode="after")
    def validate_registration(self):
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
        if not self.accept_terms:
            raise ValueError("You must accept the Terms & Conditions.")
        if not self.accept_privacy:
            raise ValueError("You must accept the Privacy Policy.")
        return self


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
