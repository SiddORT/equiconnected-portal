"""Privacy-minimal daily aggregates collected from successful route views."""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import TimestampMixin


class TrafficPageCategoryDaily(TimestampMixin, Base):
    """Successful eligible page-view totals by system-calendar date/category."""

    __tablename__ = "analytics_traffic_page_category_daily"

    visit_date: Mapped[date] = mapped_column(Date, primary_key=True)
    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    page_views: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    __table_args__ = (
        CheckConstraint("page_views >= 0", name="ck_analytics_traffic_category_nonnegative"),
        CheckConstraint(
            "category IN ('home', 'animation', 'signup', 'provider_signup', 'terms', "
            "'privacy', 'provider_directory', 'provider_profile')",
            name="ck_analytics_traffic_category_allowed",
        ),
        Index(
            "ix_analytics_traffic_category_date",
            "category",
            "visit_date",
        ),
    )


class TrafficProviderProfileDaily(TimestampMixin, Base):
    """Daily provider-profile views from authorized, discoverable member pages."""

    __tablename__ = "analytics_traffic_provider_profile_daily"

    visit_date: Mapped[date] = mapped_column(Date, primary_key=True)
    provider_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    profile_views: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    __table_args__ = (
        CheckConstraint(
            "profile_views >= 0", name="ck_analytics_traffic_provider_nonnegative"
        ),
        Index("ix_analytics_traffic_provider_date", "provider_id", "visit_date"),
    )


class TrafficVisitorDaily(TimestampMixin, Base):
    """Daily aggregate browser estimate; deliberately has no visitor identifier."""

    __tablename__ = "analytics_traffic_visitor_daily"

    visit_date: Mapped[date] = mapped_column(Date, primary_key=True)
    estimated_visitors: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    __table_args__ = (
        CheckConstraint(
            "estimated_visitors >= 0",
            name="ck_analytics_traffic_visitors_nonnegative",
        ),
    )


class TrafficTrackingMetadata(Base):
    """Persistent rollout boundary; exactly one row is installed by migration."""

    __tablename__ = "analytics_traffic_tracking_metadata"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    tracking_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_analytics_traffic_metadata_singleton"),
    )


class TrafficTrackingReceipt(Base):
    """Short-lived UUID-only retry receipt with no linked event or identity."""

    __tablename__ = "analytics_traffic_tracking_receipts"

    navigation_key: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_analytics_traffic_receipts_expiry", "expires_at"),
    )