"""Schemas for the verified-member provider directory and review moderation."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ProviderType, VisitStability


class DirectoryLocation(BaseModel):
    city: str
    state_province: str | None
    country: str | None


class PublicProviderReview(BaseModel):
    id: UUID
    rating: int
    comment: str
    reviewer_name: str
    created_at: datetime


class MemberReviewResponse(BaseModel):
    id: UUID
    rating: int
    comment: str
    comment_visible: bool
    created_at: datetime
    updated_at: datetime


class MemberReviewUpsert(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field("", max_length=2000)

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: object) -> str:
        return value.strip() if isinstance(value, str) else value  # type: ignore[return-value]


class MemberProviderListItem(BaseModel):
    id: UUID
    provider_type: ProviderType
    name: str
    description: str | None
    thumbnail_url: str | None = None
    thumbnail_alt_text: str | None = None
    website: str | None
    email: str | None
    phone: str | None
    visit_stability: VisitStability
    location: DirectoryLocation | None
    average_rating: float | None
    review_count: int
    distance_km: float | None = None


class MemberProviderDetail(MemberProviderListItem):
    visible_reviews: list[PublicProviderReview]
    own_review: MemberReviewResponse | None


class AdminReviewListItem(BaseModel):
    id: UUID
    provider_id: UUID
    provider_name: str
    reviewer_id: UUID
    reviewer_name: str
    reviewer_email: str
    rating: int
    comment: str
    comment_visible: bool
    created_at: datetime
    updated_at: datetime


class CommentVisibilityUpdate(BaseModel):
    comment_visible: bool