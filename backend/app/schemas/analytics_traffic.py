"""Strict inputs for privacy-minimal traffic ingestion."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator


class PublicTrafficViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "home", "animation", "signup", "provider_signup", "terms", "privacy"
    ]
    navigation_key: UUID
    first_eligible_view_today: StrictBool


class MemberTrafficViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["provider_directory", "provider_profile"]
    navigation_key: UUID
    first_eligible_view_today: StrictBool
    provider_id: UUID | None = None

    @model_validator(mode="after")
    def validate_provider_reference(self):
        if self.category == "provider_profile" and self.provider_id is None:
            raise ValueError("A provider profile view requires a provider identifier.")
        if self.category == "provider_directory" and self.provider_id is not None:
            raise ValueError("A directory view must not include a provider identifier.")
        return self