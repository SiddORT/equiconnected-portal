"""
Authentication Pydantic schemas.
Passwords are NEVER included in response schemas.
"""
import re
import uuid
from datetime import datetime
from typing import Literal

from app.models.enums import ProviderType, VisitStability

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
    email_verified_at: datetime | None = None
    last_successful_login_at: datetime | None = None
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
    def trim_state_province(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

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


class ProviderRegistrationRequest(RegistrationRequest):
    """Public provider account registration; listing is created only after approval."""

    provider_type: ProviderType
    provider_name: str = Field(min_length=1, max_length=300)
    visit_stability: VisitStability
    state_province: str | None = Field(default=None, max_length=100)
    professional_title: str = Field(min_length=1, max_length=200)
    specialization_ids: list[uuid.UUID] = Field(min_length=1)
    language_ids: list[uuid.UUID] = Field(default_factory=list)
    years_experience: int = Field(ge=0, le=100)
    working_address: str = Field(min_length=1, max_length=300)
    stable_visit: bool = False
    maximum_working_radius_km: float | None = Field(default=None, gt=0, allow_inf_nan=False, le=99999999.99)
    emergency_services_available: bool
    emergency_contact_number: str | None = Field(default=None, max_length=50)
    role: Literal["PROVIDER"] = "PROVIDER"
    postal_code: str = Field(min_length=1, max_length=32)

    @field_validator("provider_name")
    @classmethod
    def trim_provider_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Provider or practice name is required.")
        return value

    @field_validator("postal_code")
    @classmethod
    def trim_postal_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Postal code is required.")
        return value

    @field_validator("professional_title", "working_address")
    @classmethod
    def trim_provider_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required.")
        return value

    @field_validator("specialization_ids")
    @classmethod
    def unique_specializations(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("specialization_ids must not contain duplicates.")
        return value

    @field_validator("language_ids")
    @classmethod
    def unique_languages(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("language_ids must not contain duplicates.")
        return value

    @model_validator(mode="after")
    def validate_provider_fields(self):
        expected = VisitStability.STABLE_VISIT if self.stable_visit else VisitStability.NOT_STABLE_VISIT
        if self.visit_stability != expected:
            raise ValueError("visit_stability must match stable_visit.")
        if self.stable_visit and self.maximum_working_radius_km is None:
            raise ValueError("maximum_working_radius_km is required for stable visits.")
        if not self.stable_visit:
            self.maximum_working_radius_km = None
        if self.emergency_services_available:
            contact = (self.emergency_contact_number or "").strip()
            if not re.fullmatch(r"[0-9+\-()\s]{6,32}", contact):
                raise ValueError("Enter a valid emergency contact number when emergency services are available.")
            self.emergency_contact_number = contact
        if not self.emergency_services_available:
            self.emergency_contact_number = None
        return self


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class VerificationResendRequest(BaseModel):
    email: EmailStr


class RegistrationResponse(BaseModel):
    message: str
    email_sent: bool


class EmailVerificationResponse(BaseModel):
    """The email is returned only after a verification token is redeemed."""

    message: str
    email: EmailStr
    redirect_to: Literal["/provider/login"] | None = None


class ProviderPortalPasswordSetupRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_password(self):
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
