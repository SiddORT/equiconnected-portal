"""Validated query and response shapes for administrator analytics."""
from datetime import date
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    ContactEnquiryType,
    InvitationStatus,
    MemberFeedbackCategory,
    ProviderApplicationStatus,
    ProviderReviewStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    SubscriberRegistrationType,
)


class AnalyticsPreset(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    ALL = "all"
    CUSTOM = "custom"


class AnalyticsGrouping(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AnalyticsDomain(str, Enum):
    TRAFFIC = "traffic"
    REGISTRATIONS = "registrations"
    PROVIDERS = "providers"
    APPLICATIONS = "applications"
    INVITATIONS = "invitations"
    REVIEWS = "reviews"
    FEEDBACK = "feedback"
    ENQUIRIES = "enquiries"
    SUBSCRIBERS = "subscribers"


class AnalyticsDataset(str, Enum):
    SERIES = "series"
    BREAKDOWNS = "breakdowns"
    PROVIDER_RANKING = "provider-ranking"


class AnalyticsFilters(BaseModel):
    """Shared query string filters; irrelevant filters are ignored per metric."""

    preset: AnalyticsPreset = AnalyticsPreset.LAST_30_DAYS
    date_from: date | None = None
    date_to: date | None = None
    group_by: AnalyticsGrouping = AnalyticsGrouping.DAILY

    provider_type: ProviderType | None = None
    provider_status: ProviderStatus | None = None
    publication_status: PublicationStatus | None = None
    provider_id: UUID | None = None
    provider_search: str | None = Field(default=None, max_length=100)
    specialization_id: UUID | None = None
    country: str | None = Field(default=None, min_length=1, max_length=150)
    city: str | None = Field(default=None, min_length=1, max_length=150)

    member_role: Literal["horse_owner", "stable_manager", "both"] | None = None
    member_verified: bool | None = None
    member_active: bool | None = None

    application_status: ProviderApplicationStatus | None = None
    invitation_status: InvitationStatus | None = None
    review_status: ProviderReviewStatus | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    feedback_category: MemberFeedbackCategory | None = None
    feedback_status: Literal["Pending", "In review", "Resolved", "Rejected", "withdrawn"] | None = None
    enquiry_type: ContactEnquiryType | None = None
    subscriber_type: SubscriberRegistrationType | None = None

class AnalyticsSort(str, Enum):
    PROFILE_VIEWS = "profile_views"
    REVIEW_SUBMISSIONS = "review_submissions"
    AVERAGE_RATING = "average_rating"
    RATING_COUNT = "rating_count"
    SAVED_COUNT = "saved_count"
    NAME = "name"


class AnalyticsPagination(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    sort: AnalyticsSort = AnalyticsSort.PROFILE_VIEWS
    sort_direction: Literal["asc", "desc"] = "desc"


class AnalyticsReport(BaseModel):
    """A stable metadata envelope; payload keys vary by analytics endpoint."""

    timezone: str
    period: dict[str, Any]
    coverage: dict[str, Any]
    refreshed_at: str
    data: Any