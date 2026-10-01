"""Schemas for the verified-member provider directory and review moderation."""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import DoctorAvailability, ProviderReviewStatus, ProviderType, VisitStability


class DirectoryLocation(BaseModel):
    city: str
    state_province: str | None
    country: str | None


class MemberProviderLocation(DirectoryLocation):
    is_primary: bool


class MemberProviderQualification(BaseModel):
    title: str
    institution: str | None
    year_obtained: int | None
    description: str | None
    display_order: int


class MemberProviderPhoto(BaseModel):
    url: str
    alt_text: str | None
    caption: str | None
    display_order: int
    is_thumbnail: bool


class MemberProviderLanguage(BaseModel):
    name: str
    code: str


class MemberProviderVisit(BaseModel):
    start_date: date
    end_date: date
    location: DirectoryLocation


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
    status: ProviderReviewStatus
    member_note: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class MemberReviewUpsert(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field("", max_length=2000)
    expected_version: int | None = Field(None, ge=1)

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: object) -> str:
        return value.strip() if isinstance(value, str) else value  # type: ignore[return-value]


class MemberProviderListItem(BaseModel):
    id: UUID
    is_saved: bool = False
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
    specializations: list[str] = Field(default_factory=list)
    emergency_services_available: bool = False


class MemberProviderDetail(MemberProviderListItem):
    biography: str | None = None
    professional_title: str | None = None
    experience_description: str | None = None
    years_experience: int | None = None
    qualifications: list[MemberProviderQualification] = Field(default_factory=list)
    photos: list[MemberProviderPhoto] = Field(default_factory=list)
    languages: list[MemberProviderLanguage] = Field(default_factory=list)
    locations: list[MemberProviderLocation] = Field(default_factory=list)
    maximum_working_radius_km: float | None = None
    clinic_hospital_visit: bool | None = None
    doctor_availability: DoctorAvailability | None = None
    doctor_visits: list[MemberProviderVisit] = Field(default_factory=list)
    visible_reviews: list[PublicProviderReview]
    own_review: MemberReviewResponse | None


class PublicProviderLocation(BaseModel):
    city: str
    state_province: str | None
    country: str | None
    latitude: float
    longitude: float


class PublicProviderDiscovery(BaseModel):
    id: UUID
    provider_type: ProviderType
    name: str
    specializations: list[str] = Field(default_factory=list)
    location: PublicProviderLocation
    thumbnail_url: str | None = None
    average_rating: float | None
    review_count: int
    distance_km: float | None = None


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
    status: ProviderReviewStatus
    member_note: str | None = None
    internal_note: str | None = None
    version: int
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CommentVisibilityUpdate(BaseModel):
    comment_visible: bool
    expected_version: int = Field(..., ge=1)


class MemberReviewItem(MemberReviewResponse):
    provider_id: UUID
    provider_name: str


class AdminReviewStatusUpdate(BaseModel):
    status: ProviderReviewStatus
    expected_version: int = Field(..., ge=1)
    member_note: str | None = Field(None, max_length=2000)
    internal_note: str | None = Field(None, max_length=4000)


class ProviderReviewActionResponse(BaseModel):
    id: UUID
    actor_id: UUID | None
    actor_name: str | None
    actor_email: str
    actor_type: str
    action: str
    from_status: ProviderReviewStatus | None
    to_status: ProviderReviewStatus | None
    version: int
    content_snapshot: dict
    created_at: datetime


class AdminReviewDetail(AdminReviewListItem):
    history: list[ProviderReviewActionResponse]