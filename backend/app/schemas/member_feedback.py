"""Request and response schemas for member feedback and browsing history."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import MemberFeedbackCategory, MemberFeedbackStatus


class MemberFeedbackCreate(BaseModel):
    category: MemberFeedbackCategory
    subject: str | None = Field(None, max_length=200)
    rating: int | None = Field(None, ge=1, le=5)
    message: str = Field(..., min_length=1, max_length=5000)
    idempotency_key: UUID

    @field_validator("subject", "message", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class MemberFeedbackUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    category: MemberFeedbackCategory | None = None
    subject: str | None = Field(None, max_length=200)
    rating: int | None = Field(None, ge=1, le=5)
    message: str | None = Field(None, min_length=1, max_length=5000)

    @field_validator("subject", "message", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def has_editable_fields(self):
        if not (self.model_fields_set - {"expected_version"}):
            raise ValueError("At least one feedback field must be supplied.")
        if "category" in self.model_fields_set and self.category is None:
            raise ValueError("category cannot be cleared.")
        if "message" in self.model_fields_set and self.message is None:
            raise ValueError("message cannot be cleared.")
        return self


class MemberFeedbackItem(BaseModel):
    id: UUID
    category: MemberFeedbackCategory
    subject: str | None
    rating: int | None
    message: str
    status: MemberFeedbackStatus
    member_response: str | None
    submitted_at: datetime
    updated_at: datetime
    version: int
    withdrawn_at: datetime | None


class MemberFeedbackActionItem(BaseModel):
    action: str
    from_status: MemberFeedbackStatus | None
    to_status: MemberFeedbackStatus | None
    version: int
    created_at: datetime
    actor_name: str
    member_response: str | None = None


class MemberFeedbackDetail(MemberFeedbackItem):
    history: list[MemberFeedbackActionItem]


class AdminFeedbackItem(MemberFeedbackItem):
    member_id: UUID | None
    submitter_name: str
    submitter_email: str
    internal_note: str | None


class AdminFeedbackActionItem(BaseModel):
    id: UUID
    actor_id: UUID | None
    actor_name: str
    actor_email: str
    actor_type: str
    action: str
    from_status: MemberFeedbackStatus | None
    to_status: MemberFeedbackStatus | None
    version: int
    content_snapshot: dict
    created_at: datetime


class AdminFeedbackDetail(AdminFeedbackItem):
    history: list[AdminFeedbackActionItem]


class AdminFeedbackUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    status: MemberFeedbackStatus | None = None
    member_response: str | None = Field(None, max_length=5000)
    internal_note: str | None = Field(None, max_length=5000)

    @field_validator("member_response", "internal_note", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def has_changes(self):
        if not (self.model_fields_set - {"expected_version"}):
            raise ValueError("At least one moderation field must be supplied.")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be cleared.")
        return self


class FeedbackCounts(BaseModel):
    total: int
    pending: int
    in_review: int
    resolved: int
    rejected: int


class MemberHistoryFilters(BaseModel):
    name: str | None = Field(None, max_length=200)
    provider_type: Literal["DOCTOR", "CLINIC", "HOSPITAL"] | None = None
    visit_stability: Literal["STABLE_VISIT", "NOT_STABLE_VISIT"] | None = None
    specialization_id: UUID | None = None
    region: str | None = Field(None, max_length=200)
    minimum_rating: float | None = Field(None, ge=1, le=5)
    emergency_only: bool | None = None
    saved: bool | None = None
    sort: Literal["relevance", "name"] | None = None

    @field_validator("name", "region", mode="before")
    @classmethod
    def normalize_filter_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class MemberHistoryCreate(BaseModel):
    event_key: str = Field(..., min_length=1, max_length=100)
    type: Literal["search", "provider"]
    provider_id: UUID | None = None
    filters: MemberHistoryFilters | None = None

    @model_validator(mode="after")
    def validate_event(self):
        if self.type == "provider" and self.provider_id is None:
            raise ValueError("provider_id is required for provider history.")
        if self.type == "search":
            if self.provider_id is not None:
                raise ValueError("provider_id is not valid for search history.")
            if self.filters is None or not self.filters.model_dump(exclude_none=True):
                raise ValueError("Search history requires at least one applied filter.")
        elif self.filters is not None:
            raise ValueError("filters are only valid for search history.")
        return self


class MemberHistoryItem(BaseModel):
    id: UUID
    event_key: str
    type: Literal["search", "provider"]
    provider_id: UUID | None
    provider_name: str | None
    provider_available: bool | None
    filters: dict | None
    occurred_at: datetime


class MemberHistoryResponse(MemberHistoryItem):
    pass