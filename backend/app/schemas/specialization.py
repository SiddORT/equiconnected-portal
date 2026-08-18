"""
Pydantic schemas for the Specialization master-data module.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SpecializationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Specialization name (unique)")
    description: str | None = Field(None, max_length=2000, description="Optional description")
    is_active: bool = Field(True, description="Whether this specialization is active")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class SpecializationUpdate(BaseModel):
    """PATCH body — all fields are optional; only provided fields are updated."""
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class SpecializationStatusUpdate(BaseModel):
    """Body for the /status PATCH endpoint."""
    is_active: bool


class SpecializationResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
