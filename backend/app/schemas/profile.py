"""Contracts for the verified member profile workflow."""
import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

HorseSex = Literal["MARE", "GELDING", "STALLION", "FILLY", "COLT", "OTHER"]


def _trim_optional(value: str | None) -> str | None:
    return value.strip() if value is not None and value.strip() else None


class PersonalProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    mobile_number: str = Field(min_length=6, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    country: str = Field(min_length=1, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, max_length=32)

    @field_validator("first_name", "last_name", "mobile_number", "country", "city")
    @classmethod
    def trim_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required.")
        return value

    @field_validator("mobile_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9+\-()\s]{6,32}", value):
            raise ValueError("Enter a valid mobile number.")
        return value

    _trim_optional_fields = field_validator("address", "state_province", "postal_code")(_trim_optional)


class StableProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    address: str | None = Field(default=None, max_length=300)
    country: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=32)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Stable name is required.")
        return value

    _trim_optional_fields = field_validator(
        "description", "address", "country", "state_province", "city", "postal_code",
        "contact_name", "contact_phone", mode="before"
    )(_trim_optional)


class HorseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sex: HorseSex
    registered_name: str | None = Field(default=None, max_length=200)
    breed: str | None = Field(default=None, max_length=120)
    date_of_birth: str | None = Field(default=None, max_length=10)
    color: str | None = Field(default=None, max_length=80)
    primary_discipline: str | None = Field(default=None, max_length=120)
    registration_number: str | None = Field(default=None, max_length=120)
    microchip_number: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Horse name is required.")
        return value

    _trim_optional_fields = field_validator(
        "registered_name", "breed", "date_of_birth", "color", "primary_discipline",
        "registration_number", "microchip_number", "description", mode="before"
    )(_trim_optional)


class HorseUpdate(HorseCreate):
    pass


class StableProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    address: str | None
    country: str | None
    state_province: str | None
    city: str | None
    postal_code: str | None
    contact_name: str | None
    contact_phone: str | None
    contact_email: EmailStr | None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class HorseResponse(BaseModel):
    id: uuid.UUID
    name: str
    sex: HorseSex
    registered_name: str | None
    breed: str | None
    date_of_birth: str | None
    color: str | None
    primary_discipline: str | None
    registration_number: str | None
    microchip_number: str | None
    description: str | None
    photo_reference: str | None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MemberProfileResponse(BaseModel):
    first_name: str | None
    last_name: str | None
    email: EmailStr
    mobile_number: str | None
    address: str | None
    country: str | None
    state_province: str | None
    city: str | None
    postal_code: str | None
    roles: list[str]
    stable_profile: StableProfileResponse | None
    horses: list[HorseResponse]


class PostalLookupResponse(BaseModel):
    status: Literal["match", "no_match", "unavailable"]
    city: str | None = None
    state_province: str | None = None