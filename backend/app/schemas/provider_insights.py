"""Strict request/response contracts for provider performance insights."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


ContactAction = Literal["phone", "email", "website"]


class ProviderContactClickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ContactAction
    event_key: UUID

    @model_validator(mode="after")
    def validate_event_key(self):
        if self.event_key.version != 7:
            raise ValueError("The event key must be a UUIDv7 value.")
        return self


class ProviderInsightsReport(BaseModel):
    provider_name: str
    timezone: str
    today: date
    period: dict[str, str]
    refreshed_at: datetime
    metrics: dict[str, dict]
    contact_breakdown: dict[str, int | None]
    snapshot: dict[str, int | float | None]
    trends: list[dict[str, date | int | None]] = Field(default_factory=list)