"""Contracts for the verified member profile workflow."""
import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

HorseSex = Literal["MARE", "GELDING", "STALLION", "FILLY", "COLT", "OTHER"]


def _trim_optional(value: str | None) -> str | None:
    return value.strip() if value is not None and value.strip() else None


class PersonalProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    mobile_number: str = Field(min_length=6, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    address_line_2: str | None = Field(default=None, max_length=300)
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

    _trim_optional_fields = field_validator(
        "address", "address_line_2", "state_province", "postal_code"
    )(_trim_optional)


class LocationCoordinates(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Enter both latitude and longitude, or leave both blank.")
        if ("latitude" in self.model_fields_set) != ("longitude" in self.model_fields_set):
            raise ValueError("Send latitude and longitude together.")
        return self


class HorseLocation(LocationCoordinates):
    location_mode: Literal["custom", "stable"] = "custom"
    address: str | None = Field(default=None, max_length=300)
    address_line_2: str | None = Field(default=None, max_length=300)
    country: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=32)

    _trim_location = field_validator(
        "address", "address_line_2", "country", "state_province", "city", "postal_code",
        mode="before",
    )(_trim_optional)


class StableProfileUpdate(LocationCoordinates):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    address: str | None = Field(default=None, max_length=300)
    address_line_2: str | None = Field(default=None, max_length=300)
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
        "description", "address", "address_line_2", "country", "state_province", "city", "postal_code",
        "contact_name", "contact_phone", mode="before"
    )(_trim_optional)


class HorseCreate(HorseLocation):
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
    latitude: float | None = None
    longitude: float | None = None
    id: uuid.UUID
    name: str
    description: str | None
    address: str | None
    address_line_2: str | None
    country: str | None
    state_province: str | None
    city: str | None
    postal_code: str | None
    contact_name: str | None
    contact_phone: str | None
    contact_email: EmailStr | None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EffectiveHorseLocation(BaseModel):
    address: str | None = None
    address_line_2: str | None = None
    country: str | None = None
    state_province: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    available: bool
    reason: str | None


class HorseResponse(HorseLocation):
    effective_location: EffectiveHorseLocation
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
    address_line_2: str | None
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