"""Grouped, bounded database reads for administrator analytics."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, exists, func, or_, select, union_all
from sqlalchemy.orm import Session

from app.models.contact_enquiry import ContactEnquiry
from app.models.analytics_traffic import (
    TrafficPageCategoryDaily,
    TrafficProviderProfileDaily,
    TrafficTrackingMetadata,
    TrafficVisitorDaily,
)
from app.models.enums import (
    InvitationStatus,
    MemberFeedbackStatus,
    ProviderApplicationStatus,
    ProviderReviewStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
)
from app.models.invitation import ProviderInvitation
from app.models.member_feedback import MemberFeedback
from app.models.provider import Provider, ProviderLocation, ProviderReview, ProviderSpecialization
from app.models.provider_favorite import ProviderFavorite
from app.models.provider_review_action import ProviderReviewAction
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.public_visit import PublicVisitDaily
from app.models.role import Role
from app.models.specialization import Specialization
from app.models.subscriber import Subscriber
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User, UserRole


class AdminAnalyticsRepository:
    """Keeps analytics aggregation in SQL and avoids relationship join fanout."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def bucket_expression(timestamp_column, timezone_name: str, group_by: str):
        local_timestamp = func.timezone(timezone_name, timestamp_column)
        sql_unit = {"daily": "day", "weekly": "week", "monthly": "month"}[group_by]
        return func.date_trunc(sql_unit, local_timestamp).label("bucket")

    def count(
        self,
        model,
        timestamp_column,
        *,
        start: datetime,
        end: datetime,
        conditions: tuple[Any, ...] = (),
    ) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(model)
                .where(timestamp_column >= start, timestamp_column < end, *conditions)
            )
            or 0
        )

    def grouped_count(
        self,
        model,
        timestamp_column,
        *,
        start: datetime,
        end: datetime,
        timezone_name: str,
        group_by: str,
        conditions: tuple[Any, ...] = (),
    ) -> list[tuple[datetime, int]]:
        bucket = self.bucket_expression(timestamp_column, timezone_name, group_by)
        return [
            (row.bucket, int(row.value))
            for row in self.db.execute(
                select(bucket, func.count().label("value"))
                .select_from(model)
                .where(timestamp_column >= start, timestamp_column < end, *conditions)
                .group_by(bucket)
                .order_by(bucket)
            )
        ]

    def first_last_dates(self, model, timestamp_column, timezone_name: str) -> dict[str, date | None]:
        first, last = self.db.execute(
            select(func.min(timestamp_column), func.max(timestamp_column))
            .select_from(model)
        ).one()
        if first is None or last is None:
            return {"from": None, "through": None}
        if isinstance(first, date) and not isinstance(first, datetime):
            return {"from": first, "through": last}
        from app.core.time_standards import resolve_timezone

        return {
            "from": first.astimezone(resolve_timezone(timezone_name)).date(),
            "through": last.astimezone(resolve_timezone(timezone_name)).date(),
        }

    def traffic_tracking_start(self, timezone_name: str) -> date | None:
        from app.core.time_standards import resolve_timezone

        started_at = self.db.scalar(
            select(TrafficTrackingMetadata.tracking_started_at).where(
                TrafficTrackingMetadata.id == 1
            )
        )
        if started_at is None:
            return None
        return started_at.astimezone(resolve_timezone(timezone_name)).date()

    def traffic_page_total(
        self, *, start_date: date, end_date: date, categories: tuple[str, ...] | None = None
    ) -> int:
        conditions = [
            TrafficPageCategoryDaily.visit_date >= start_date,
            TrafficPageCategoryDaily.visit_date <= end_date,
        ]
        if categories is not None:
            conditions.append(TrafficPageCategoryDaily.category.in_(categories))
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(TrafficPageCategoryDaily.page_views), 0))
                .where(*conditions)
            )
            or 0
        )

    def traffic_page_daily_series(
        self, *, start_date: date, end_date: date, categories: tuple[str, ...] | None = None
    ) -> list[tuple[date, int]]:
        conditions = [
            TrafficPageCategoryDaily.visit_date >= start_date,
            TrafficPageCategoryDaily.visit_date <= end_date,
        ]
        if categories is not None:
            conditions.append(TrafficPageCategoryDaily.category.in_(categories))
        return [
            (visit_date, int(value))
            for visit_date, value in self.db.execute(
                select(
                    TrafficPageCategoryDaily.visit_date,
                    func.sum(TrafficPageCategoryDaily.page_views),
                )
                .where(*conditions)
                .group_by(TrafficPageCategoryDaily.visit_date)
                .order_by(TrafficPageCategoryDaily.visit_date)
            )
        ]

    def traffic_category_breakdown(self, *, start_date: date, end_date: date):
        return {
            str(category): int(count)
            for category, count in self.db.execute(
                select(
                    TrafficPageCategoryDaily.category,
                    func.sum(TrafficPageCategoryDaily.page_views),
                )
                .where(
                    TrafficPageCategoryDaily.visit_date >= start_date,
                    TrafficPageCategoryDaily.visit_date <= end_date,
                )
                .group_by(TrafficPageCategoryDaily.category)
            )
        }

    def visitor_day_total(self, *, start_date: date, end_date: date) -> int:
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(TrafficVisitorDaily.estimated_visitors), 0))
                .where(
                    TrafficVisitorDaily.visit_date >= start_date,
                    TrafficVisitorDaily.visit_date <= end_date,
                )
            )
            or 0
        )

    def visitor_daily_series(self, *, start_date: date, end_date: date):
        return [
            (visit_date, int(value))
            for visit_date, value in self.db.execute(
                select(TrafficVisitorDaily.visit_date, TrafficVisitorDaily.estimated_visitors)
                .where(
                    TrafficVisitorDaily.visit_date >= start_date,
                    TrafficVisitorDaily.visit_date <= end_date,
                )
                .order_by(TrafficVisitorDaily.visit_date)
            )
        ]

    def latest_visitor_estimate(self, *, through: date) -> tuple[date, int] | None:
        row = self.db.execute(
            select(TrafficVisitorDaily.visit_date, TrafficVisitorDaily.estimated_visitors)
            .where(TrafficVisitorDaily.visit_date <= through)
            .order_by(TrafficVisitorDaily.visit_date.desc())
            .limit(1)
        ).first()
        return (row[0], int(row[1])) if row is not None else None

    def provider_profile_view_count(self, *, provider_id: UUID, start_date: date, end_date: date):
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(TrafficProviderProfileDaily.profile_views), 0))
                .where(
                    TrafficProviderProfileDaily.provider_id == provider_id,
                    TrafficProviderProfileDaily.visit_date >= start_date,
                    TrafficProviderProfileDaily.visit_date <= end_date,
                )
            )
            or 0
        )

    def profile_view_series(
        self,
        *,
        provider_id: UUID | None,
        start_date: date,
        end_date: date,
        filters=None,
    ) -> list[tuple[date, int]]:
        conditions = [
            TrafficProviderProfileDaily.visit_date >= start_date,
            TrafficProviderProfileDaily.visit_date <= end_date,
        ]
        if provider_id is not None:
            conditions.append(TrafficProviderProfileDaily.provider_id == provider_id)
        query = select(
            TrafficProviderProfileDaily.visit_date,
            func.sum(TrafficProviderProfileDaily.profile_views),
        ).where(*conditions)
        if filters is not None:
            provider_conditions = self.provider_conditions(filters)
            query = query.join(
                Provider,
                Provider.id == TrafficProviderProfileDaily.provider_id,
            ).where(*provider_conditions)
        return [
            (visit_date, int(value))
            for visit_date, value in self.db.execute(
                query.group_by(TrafficProviderProfileDaily.visit_date)
                .order_by(TrafficProviderProfileDaily.visit_date)
            )
        ]

    def profile_view_total(
        self,
        *,
        start_date: date,
        end_date: date,
        provider_id: UUID | None = None,
        filters=None,
    ) -> int:
        conditions = [
            TrafficProviderProfileDaily.visit_date >= start_date,
            TrafficProviderProfileDaily.visit_date <= end_date,
        ]
        if provider_id is not None:
            conditions.append(TrafficProviderProfileDaily.provider_id == provider_id)
        query = select(
            func.coalesce(func.sum(TrafficProviderProfileDaily.profile_views), 0)
        ).where(*conditions)
        if filters is not None:
            query = query.join(
                Provider,
                Provider.id == TrafficProviderProfileDaily.provider_id,
            ).where(*self.provider_conditions(filters))
        return int(self.db.scalar(query) or 0)

    def earliest_event_date(self, timezone_name: str) -> date | None:
        expressions = [
            select(func.min(User.created_at).label("occurred_at"))
            .where(self.public_member_condition()),
            select(func.min(ProviderRegistrationApplication.created_at)),
            select(func.min(ProviderInvitation.created_at)),
            select(func.min(ProviderReview.created_at)),
            select(func.min(MemberFeedback.submitted_at)),
            select(func.min(ContactEnquiry.submitted_at)),
            select(func.min(Subscriber.submitted_at)),
        ]
        statement = select(func.min(events.c.occurred_at)).select_from(
            union_all(*expressions).subquery("events")
        )
        earliest = self.db.scalar(statement)
        if earliest is None:
            return None
        from app.core.time_standards import resolve_timezone

        return earliest.astimezone(resolve_timezone(timezone_name)).date()

    @staticmethod
    def _assignment_has(role_name: str):
        return (
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == User.id, Role.name == role_name)
            .exists()
        )

    @classmethod
    def _user_has_role(cls, role_name: str):
        return or_(User.role.has(Role.name == role_name), cls._assignment_has(role_name))

    @classmethod
    def _user_has_any_role(cls, role_names: tuple[str, ...]):
        return or_(
            User.role.has(Role.name.in_(role_names)),
            exists(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(UserRole.user_id == User.id, Role.name.in_(role_names))
            ),
        )

    @classmethod
    def public_member_condition(cls):
        return or_(*(cls._user_has_role(role) for role in PUBLIC_ACCOUNT_ROLE_NAMES))

    @classmethod
    def member_conditions(cls, filters) -> tuple[Any, ...]:
        conditions: list[Any] = [
            cls.public_member_condition(),
            ~cls._user_has_any_role(("admin", "provider")),
        ]
        horse_owner = cls._user_has_role("horse_owner")
        stable_manager = cls._user_has_role("stable_manager")
        if filters.member_role == "horse_owner":
            conditions.append(horse_owner & ~stable_manager)
        elif filters.member_role == "stable_manager":
            conditions.append(stable_manager & ~horse_owner)
        elif filters.member_role == "both":
            conditions.extend([horse_owner, stable_manager])
        if filters.member_verified is not None:
            conditions.append(
                User.email_verified_at.is_not(None)
                if filters.member_verified
                else User.email_verified_at.is_(None)
            )
        if filters.member_active is not None:
            conditions.append(User.is_active.is_(filters.member_active))
        return tuple(conditions)

    @staticmethod
    def provider_conditions(filters, *, include_search: bool = True) -> tuple[Any, ...]:
        conditions: list[Any] = []
        if filters.provider_type is not None:
            conditions.append(Provider.provider_type == filters.provider_type)
        if filters.provider_status is not None:
            conditions.append(Provider.status == filters.provider_status)
        if filters.publication_status is not None:
            conditions.append(Provider.publication_status == filters.publication_status)
        if filters.provider_id is not None:
            conditions.append(Provider.id == filters.provider_id)
        if include_search and filters.provider_search and filters.provider_search.strip():
            escaped = filters.provider_search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(Provider.name.ilike(f"%{escaped}%", escape="\\"))
        if filters.specialization_id is not None:
            conditions.append(
                exists(
                    select(ProviderSpecialization.provider_id).where(
                        ProviderSpecialization.provider_id == Provider.id,
                        ProviderSpecialization.specialization_id == filters.specialization_id,
                    )
                )
            )
        if filters.country or filters.city:
            location_conditions = [ProviderLocation.provider_id == Provider.id]
            if filters.country:
                location_conditions.append(
                    func.lower(ProviderLocation.country) == filters.country.strip().lower()
                )
            if filters.city:
                location_conditions.append(
                    func.lower(ProviderLocation.city) == filters.city.strip().lower()
                )
            conditions.append(
                exists(select(ProviderLocation.id).where(*location_conditions))
            )
        return tuple(conditions)

    def registration_count(self, *, start, end, filters) -> int:
        return self.count(
            User,
            User.created_at,
            start=start,
            end=end,
            conditions=self.member_conditions(filters),
        )

    def registration_series(self, *, start, end, timezone_name, group_by, filters):
        return self.grouped_count(
            User,
            User.created_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=self.member_conditions(filters),
        )

    def application_count(self, *, start, end, filters) -> int:
        conditions: list[Any] = []
        if filters.provider_type is not None:
            conditions.append(
                ProviderRegistrationApplication.provider_type == filters.provider_type
            )
        if filters.application_status is not None:
            conditions.append(
                ProviderRegistrationApplication.review_status == filters.application_status
            )
        return self.count(
            ProviderRegistrationApplication,
            ProviderRegistrationApplication.created_at,
            start=start,
            end=end,
            conditions=tuple(conditions),
        )

    def application_series(self, *, start, end, timezone_name, group_by, filters):
        conditions: list[Any] = []
        if filters.provider_type is not None:
            conditions.append(
                ProviderRegistrationApplication.provider_type == filters.provider_type
            )
        if filters.application_status is not None:
            conditions.append(
                ProviderRegistrationApplication.review_status == filters.application_status
            )
        return self.grouped_count(
            ProviderRegistrationApplication,
            ProviderRegistrationApplication.created_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=tuple(conditions),
        )

    def application_decision_count(self, *, start, end, filters) -> int:
        conditions: list[Any] = [
            ProviderRegistrationApplication.reviewed_at.is_not(None),
            ProviderRegistrationApplication.review_status.in_(
                [
                    ProviderApplicationStatus.APPROVED,
                    ProviderApplicationStatus.REJECTED,
                ]
            ),
        ]
        if filters.provider_type is not None:
            conditions.append(
                ProviderRegistrationApplication.provider_type == filters.provider_type
            )
        if filters.application_status is not None:
            conditions.append(
                ProviderRegistrationApplication.review_status == filters.application_status
            )
        return self.count(
            ProviderRegistrationApplication,
            ProviderRegistrationApplication.reviewed_at,
            start=start,
            end=end,
            conditions=tuple(conditions),
        )

    def application_decision_series(
        self, *, start, end, timezone_name, group_by, filters
    ):
        conditions: list[Any] = [
            ProviderRegistrationApplication.reviewed_at.is_not(None),
            ProviderRegistrationApplication.review_status.in_(
                [
                    ProviderApplicationStatus.APPROVED,
                    ProviderApplicationStatus.REJECTED,
                ]
            ),
        ]
        if filters.provider_type is not None:
            conditions.append(
                ProviderRegistrationApplication.provider_type == filters.provider_type
            )
        if filters.application_status is not None:
            conditions.append(
                ProviderRegistrationApplication.review_status == filters.application_status
            )
        return self.grouped_count(
            ProviderRegistrationApplication,
            ProviderRegistrationApplication.reviewed_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=tuple(conditions),
        )

    def enquiry_count(self, *, start, end, filters) -> int:
        conditions = (
            (ContactEnquiry.enquiry_type == filters.enquiry_type.value,)
            if filters.enquiry_type is not None
            else ()
        )
        return self.count(
            ContactEnquiry,
            ContactEnquiry.submitted_at,
            start=start,
            end=end,
            conditions=conditions,
        )

    def enquiry_series(self, *, start, end, timezone_name, group_by, filters):
        conditions = (
            (ContactEnquiry.enquiry_type == filters.enquiry_type.value,)
            if filters.enquiry_type is not None
            else ()
        )
        return self.grouped_count(
            ContactEnquiry,
            ContactEnquiry.submitted_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=conditions,
        )

    def subscriber_count(self, *, start, end, filters) -> int:
        conditions = (
            (Subscriber.registration_type == filters.subscriber_type.value,)
            if filters.subscriber_type is not None
            else ()
        )
        return self.count(
            Subscriber,
            Subscriber.submitted_at,
            start=start,
            end=end,
            conditions=conditions,
        )

    def subscriber_series(self, *, start, end, timezone_name, group_by, filters):
        conditions = (
            (Subscriber.registration_type == filters.subscriber_type.value,)
            if filters.subscriber_type is not None
            else ()
        )
        return self.grouped_count(
            Subscriber,
            Subscriber.submitted_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=conditions,
        )

    def legacy_homepage_count(self, *, start_date: date, end_date: date) -> int:
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(PublicVisitDaily.visit_count), 0))
                .where(
                    PublicVisitDaily.visit_date >= start_date,
                    PublicVisitDaily.visit_date <= end_date,
                )
            )
            or 0
        )

    def legacy_homepage_series(self, *, start_date: date, end_date: date):
        return [
            (visit_date, int(count))
            for visit_date, count in self.db.execute(
                select(PublicVisitDaily.visit_date, PublicVisitDaily.visit_count)
                .where(
                    PublicVisitDaily.visit_date >= start_date,
                    PublicVisitDaily.visit_date <= end_date,
                )
                .order_by(PublicVisitDaily.visit_date)
            )
        ]

    def review_submission_count(self, *, start, end, filters) -> int:
        conditions = self._review_filters(filters, include_deleted=True)
        return self.count(
            ProviderReview,
            ProviderReview.created_at,
            start=start,
            end=end,
            conditions=conditions,
        )

    def review_submission_series(self, *, start, end, timezone_name, group_by, filters):
        return self.grouped_count(
            ProviderReview,
            ProviderReview.created_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=self._review_filters(filters, include_deleted=True),
        )

    def _review_filters(self, filters, *, include_deleted: bool) -> tuple[Any, ...]:
        conditions: list[Any] = []
        if not include_deleted:
            conditions.append(ProviderReview.deleted_at.is_(None))
        if filters.review_status is not None:
            conditions.append(ProviderReview.status == filters.review_status)
        if filters.rating is not None:
            conditions.append(ProviderReview.rating == filters.rating)
        if filters.provider_id is not None:
            conditions.append(ProviderReview.provider_id == filters.provider_id)
        provider_conditions = self.provider_conditions(filters)
        if provider_conditions:
            conditions.append(
                exists(
                    select(Provider.id)
                    .where(Provider.id == ProviderReview.provider_id, *provider_conditions)
                )
            )
        return tuple(conditions)

    def feedback_count(self, *, start, end, filters) -> int:
        return self.count(
            MemberFeedback,
            MemberFeedback.submitted_at,
            start=start,
            end=end,
            conditions=self._feedback_filters(filters),
        )

    def feedback_series(self, *, start, end, timezone_name, group_by, filters):
        return self.grouped_count(
            MemberFeedback,
            MemberFeedback.submitted_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=self._feedback_filters(filters),
        )

    @staticmethod
    def _feedback_filters(filters) -> tuple[Any, ...]:
        conditions: list[Any] = []
        if filters.feedback_category is not None:
            conditions.append(MemberFeedback.category == filters.feedback_category.value)
        if filters.feedback_status == "withdrawn":
            conditions.append(MemberFeedback.withdrawn_at.is_not(None))
        elif filters.feedback_status is not None:
            conditions.extend(
                [
                    MemberFeedback.withdrawn_at.is_(None),
                    MemberFeedback.status == filters.feedback_status,
                ]
            )
        return tuple(conditions)

    def invitation_count(self, *, start, end, filters) -> int:
        conditions = (
            (ProviderInvitation.status == filters.invitation_status,)
            if filters.invitation_status is not None
            else ()
        )
        if filters.provider_type is not None:
            conditions += (ProviderInvitation.provider_type == filters.provider_type,)
        return self.count(
            ProviderInvitation,
            ProviderInvitation.created_at,
            start=start,
            end=end,
            conditions=conditions,
        )

    def invitation_series(self, *, start, end, timezone_name, group_by, filters):
        conditions = (
            (ProviderInvitation.status == filters.invitation_status,)
            if filters.invitation_status is not None
            else ()
        )
        if filters.provider_type is not None:
            conditions += (ProviderInvitation.provider_type == filters.provider_type,)
        return self.grouped_count(
            ProviderInvitation,
            ProviderInvitation.created_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=conditions,
        )

    def invitation_sent_count(self, *, start, end, filters) -> int:
        conditions: list[Any] = []
        if filters.invitation_status is not None:
            conditions.append(ProviderInvitation.status == filters.invitation_status)
        if filters.provider_type is not None:
            conditions.append(ProviderInvitation.provider_type == filters.provider_type)
        return self.count(
            ProviderInvitation,
            ProviderInvitation.sent_at,
            start=start,
            end=end,
            conditions=tuple(conditions),
        )

    def invitation_sent_series(self, *, start, end, timezone_name, group_by, filters):
        conditions: list[Any] = []
        if filters.invitation_status is not None:
            conditions.append(ProviderInvitation.status == filters.invitation_status)
        if filters.provider_type is not None:
            conditions.append(ProviderInvitation.provider_type == filters.provider_type)
        return self.grouped_count(
            ProviderInvitation,
            ProviderInvitation.sent_at,
            start=start,
            end=end,
            timezone_name=timezone_name,
            group_by=group_by,
            conditions=tuple(conditions),
        )

    def application_decision_breakdown(self, *, start, end, filters):
        conditions: list[Any] = [
            ProviderRegistrationApplication.reviewed_at.is_not(None),
            ProviderRegistrationApplication.reviewed_at >= start,
            ProviderRegistrationApplication.reviewed_at < end,
            ProviderRegistrationApplication.review_status.in_(
                [
                    ProviderApplicationStatus.APPROVED,
                    ProviderApplicationStatus.REJECTED,
                ]
            ),
        ]
        if filters.provider_type is not None:
            conditions.append(
                ProviderRegistrationApplication.provider_type == filters.provider_type
            )
        if filters.application_status is not None:
            conditions.append(
                ProviderRegistrationApplication.review_status == filters.application_status
            )
        rows = self.db.execute(
            select(
                ProviderRegistrationApplication.review_status,
                func.count(ProviderRegistrationApplication.id),
            )
            .where(*conditions)
            .group_by(ProviderRegistrationApplication.review_status)
        ).all()
        return {status: int(count) for status, count in rows}

    def review_action_breakdown(self, *, start, end, filters):
        conditions: list[Any] = [
            ProviderReviewAction.created_at >= start,
            ProviderReviewAction.created_at < end,
            exists(
                select(ProviderReview.id).where(
                    ProviderReview.id == ProviderReviewAction.review_id,
                    *self._review_filters(filters, include_deleted=True),
                )
            ),
        ]
        rows = self.db.execute(
            select(ProviderReviewAction.action, func.count(ProviderReviewAction.id))
            .where(*conditions)
            .group_by(ProviderReviewAction.action)
        ).all()
        return {str(action): int(count) for action, count in rows}

    def current_provider_inventory(self, filters) -> dict[str, Any]:
        conditions = self.provider_conditions(filters)
        rows = self.db.execute(
            select(Provider.status, func.count(Provider.id))
            .where(*conditions)
            .group_by(Provider.status)
        ).all()
        status_counts = {status: int(count) for status, count in rows}
        type_rows = self.db.execute(
            select(Provider.provider_type, func.count(Provider.id))
            .where(*conditions)
            .group_by(Provider.provider_type)
        ).all()
        type_counts = {provider_type: int(count) for provider_type, count in type_rows}
        publication_rows = self.db.execute(
            select(Provider.publication_status, func.count(Provider.id))
            .where(*conditions)
            .group_by(Provider.publication_status)
        ).all()
        publication_counts = {
            publication: int(count) for publication, count in publication_rows
        }
        active = status_counts.get(ProviderStatus.ACTIVE, 0)
        published = self.db.scalar(
            select(func.count(Provider.id)).where(
                *conditions,
                Provider.status == ProviderStatus.ACTIVE,
                Provider.publication_status == PublicationStatus.PUBLISHED,
            )
        ) or 0
        return {
            "total": sum(status_counts.values()),
            "status": status_counts,
            "type": type_counts,
            "publication": publication_counts,
            "active": active,
            "active_published": int(published),
        }

    def application_status_breakdown(self, filters, *, start=None, end=None):
        conditions: list[Any] = []
        if filters.provider_type is not None:
            conditions.append(ProviderRegistrationApplication.provider_type == filters.provider_type)
        if filters.application_status is not None:
            conditions.append(
                ProviderRegistrationApplication.review_status == filters.application_status
            )
        if start is not None:
            conditions.append(ProviderRegistrationApplication.created_at >= start)
        if end is not None:
            conditions.append(ProviderRegistrationApplication.created_at < end)
        rows = self.db.execute(
            select(
                ProviderRegistrationApplication.review_status,
                func.count(ProviderRegistrationApplication.id),
            )
            .where(*conditions)
            .group_by(ProviderRegistrationApplication.review_status)
        ).all()
        return {status: int(count) for status, count in rows}

    def invitation_status_breakdown(self, filters, *, start=None, end=None):
        conditions: list[Any] = []
        if filters.provider_type is not None:
            conditions.append(ProviderInvitation.provider_type == filters.provider_type)
        if filters.invitation_status is not None:
            conditions.append(ProviderInvitation.status == filters.invitation_status)
        if start is not None:
            conditions.append(ProviderInvitation.created_at >= start)
        if end is not None:
            conditions.append(ProviderInvitation.created_at < end)
        rows = self.db.execute(
            select(ProviderInvitation.status, func.count(ProviderInvitation.id))
            .where(*conditions)
            .group_by(ProviderInvitation.status)
        ).all()
        return {status: int(count) for status, count in rows}

    def review_state_breakdown(self, filters, *, start=None, end=None):
        conditions = list(self._review_filters(filters, include_deleted=False))
        if start is not None:
            conditions.append(ProviderReview.created_at >= start)
        if end is not None:
            conditions.append(ProviderReview.created_at < end)
        rows = self.db.execute(
            select(ProviderReview.status, func.count(ProviderReview.id))
            .where(*conditions)
            .group_by(ProviderReview.status)
        ).all()
        # Build a separate deleted cohort query rather than allowing deleted
        # reviews to leak into the moderation-state totals.
        deleted = [ProviderReview.deleted_at.is_not(None)]
        if filters.review_status is not None:
            deleted.append(ProviderReview.status == filters.review_status)
        if filters.rating is not None:
            deleted.append(ProviderReview.rating == filters.rating)
        if filters.provider_id is not None:
            deleted.append(ProviderReview.provider_id == filters.provider_id)
        provider_conditions = self.provider_conditions(filters)
        if provider_conditions:
            deleted.append(
                exists(
                    select(Provider.id)
                    .where(Provider.id == ProviderReview.provider_id, *provider_conditions)
                )
            )
        if start is not None:
            deleted.append(ProviderReview.created_at >= start)
        if end is not None:
            deleted.append(ProviderReview.created_at < end)
        deleted_count = int(
            self.db.scalar(
                select(func.count()).select_from(ProviderReview).where(*deleted)
            )
            or 0
        )
        return {status: int(count) for status, count in rows}, deleted_count

    def rating_summary(self, filters, *, start=None, end=None):
        eligible = [
            ProviderReview.deleted_at.is_(None),
            ProviderReview.status.in_(
                [ProviderReviewStatus.PUBLISHED, ProviderReviewStatus.HIDDEN]
            ),
        ]
        if start is not None:
            eligible.append(ProviderReview.created_at >= start)
        if end is not None:
            eligible.append(ProviderReview.created_at < end)
        if filters.provider_id is not None:
            eligible.append(ProviderReview.provider_id == filters.provider_id)
        if filters.rating is not None:
            eligible.append(ProviderReview.rating == filters.rating)
        if filters.review_status is not None:
            eligible.append(ProviderReview.status == filters.review_status)
        provider_conditions = self.provider_conditions(filters)
        if provider_conditions:
            eligible.append(
                exists(
                    select(Provider.id)
                    .where(Provider.id == ProviderReview.provider_id, *provider_conditions)
                )
            )
        average, count = self.db.execute(
            select(func.avg(ProviderReview.rating), func.count(ProviderReview.id))
            .where(*eligible)
        ).one()
        stars = self.db.execute(
            select(ProviderReview.rating, func.count(ProviderReview.id))
            .where(*eligible)
            .group_by(ProviderReview.rating)
        ).all()
        return {
            "average": float(average) if average is not None else None,
            "count": int(count or 0),
            "stars": {int(star): int(number) for star, number in stars},
        }

    def feedback_status_breakdown(self, filters, *, start=None, end=None):
        conditions: list[Any] = []
        if filters.feedback_category is not None:
            conditions.append(MemberFeedback.category == filters.feedback_category.value)
        if filters.feedback_status == "withdrawn":
            conditions.append(MemberFeedback.withdrawn_at.is_not(None))
        elif filters.feedback_status is not None:
            conditions.extend(
                [
                    MemberFeedback.withdrawn_at.is_(None),
                    MemberFeedback.status == filters.feedback_status,
                ]
            )
        if start is not None:
            conditions.append(MemberFeedback.submitted_at >= start)
        if end is not None:
            conditions.append(MemberFeedback.submitted_at < end)
        active = list(conditions) + [MemberFeedback.withdrawn_at.is_(None)]
        statuses = self.db.execute(
            select(MemberFeedback.status, func.count(MemberFeedback.id))
            .where(*active)
            .group_by(MemberFeedback.status)
        ).all()
        withdrawn = int(
            self.db.scalar(
                select(func.count()).select_from(MemberFeedback).where(
                    *conditions, MemberFeedback.withdrawn_at.is_not(None)
                )
            )
            or 0
        )
        rating_conditions = active + [MemberFeedback.rating.is_not(None)]
        average, count = self.db.execute(
            select(func.avg(MemberFeedback.rating), func.count(MemberFeedback.id))
            .where(*rating_conditions)
        ).one()
        rating_distribution = self.db.execute(
            select(MemberFeedback.rating, func.count(MemberFeedback.id))
            .where(*rating_conditions)
            .group_by(MemberFeedback.rating)
        ).all()
        categories = self.db.execute(
            select(MemberFeedback.category, func.count(MemberFeedback.id))
            .where(*active)
            .group_by(MemberFeedback.category)
        ).all()
        return {
            "status": {status: int(count) for status, count in statuses},
            "withdrawn": withdrawn,
            "rating_average": float(average) if average is not None else None,
            "rating_count": int(count or 0),
            "rating_distribution": {
                int(rating): int(number) for rating, number in rating_distribution
            },
            "categories": {str(category): int(count) for category, count in categories},
        }

    def enquiry_type_breakdown(self, filters, *, start=None, end=None):
        conditions: list[Any] = []
        if filters.enquiry_type is not None:
            conditions.append(ContactEnquiry.enquiry_type == filters.enquiry_type.value)
        if start is not None:
            conditions.append(ContactEnquiry.submitted_at >= start)
        if end is not None:
            conditions.append(ContactEnquiry.submitted_at < end)
        return {
            str(key): int(value)
            for key, value in self.db.execute(
                select(ContactEnquiry.enquiry_type, func.count(ContactEnquiry.id))
                .where(*conditions)
                .group_by(ContactEnquiry.enquiry_type)
            )
        }

    def subscriber_type_breakdown(self, filters, *, start=None, end=None):
        conditions: list[Any] = []
        if filters.subscriber_type is not None:
            conditions.append(Subscriber.registration_type == filters.subscriber_type.value)
        if start is not None:
            conditions.append(Subscriber.submitted_at >= start)
        if end is not None:
            conditions.append(Subscriber.submitted_at < end)
        return {
            str(key): int(value)
            for key, value in self.db.execute(
                select(Subscriber.registration_type, func.count(Subscriber.id))
                .where(*conditions)
                .group_by(Subscriber.registration_type)
            )
        }

    def member_cohort_breakdown(self, *, start=None, end=None, filters):
        conditions = list(self.member_conditions(filters))
        if start is not None:
            conditions.append(User.created_at >= start)
        if end is not None:
            conditions.append(User.created_at < end)
        owner = self._user_has_role("horse_owner")
        manager = self._user_has_role("stable_manager")
        role = case(
            (owner & manager, "both"),
            (owner, "horse_owner"),
            (manager, "stable_manager"),
            else_="unknown",
        )
        role_counts = {
            str(name): int(count)
            for name, count in self.db.execute(
                select(role, func.count(User.id)).where(*conditions).group_by(role)
            )
        }
        verified = self.db.execute(
            select(User.email_verified_at.is_not(None), func.count(User.id))
            .where(*conditions)
            .group_by(User.email_verified_at.is_not(None))
        ).all()
        active = self.db.execute(
            select(User.is_active, func.count(User.id))
            .where(*conditions)
            .group_by(User.is_active)
        ).all()
        assignment_counts = {
            str(name): int(count)
            for name, count in self.db.execute(
                select(Role.name, func.count(func.distinct(UserRole.user_id)))
                .join(UserRole, UserRole.role_id == Role.id)
                .join(User, User.id == UserRole.user_id)
                .where(
                    *conditions,
                    Role.name.in_(PUBLIC_ACCOUNT_ROLE_NAMES),
                )
                .group_by(Role.name)
            )
        }
        return {
            "total": self.db.scalar(
                select(func.count(User.id)).where(*conditions)
            ) or 0,
            "roles": role_counts,
            "verified": {str(bool(key)).lower(): int(value) for key, value in verified},
            "active": {str(bool(key)).lower(): int(value) for key, value in active},
            "role_assignments": assignment_counts,
        }

    def provider_ranking(
        self,
        *,
        filters,
        start,
        end,
        start_date: date,
        end_date: date,
        page: int,
        page_size: int,
        sort: str,
        direction: str,
    ) -> tuple[list[dict[str, Any]], int]:
        # Each aggregate is computed before joining to providers, avoiding
        # fanout from locations, specializations, reviews, or favorites.
        review_predicates: list[Any] = [
            ProviderReview.deleted_at.is_(None),
            ProviderReview.status.in_(
                [ProviderReviewStatus.PUBLISHED, ProviderReviewStatus.HIDDEN]
            ),
        ]
        if filters.rating is not None:
            review_predicates.append(ProviderReview.rating == filters.rating)
        if filters.review_status is not None:
            review_predicates.append(ProviderReview.status == filters.review_status)
        ratings = (
            select(
                ProviderReview.provider_id.label("provider_id"),
                func.avg(ProviderReview.rating).label("average_rating"),
                func.count(ProviderReview.id).label("rating_count"),
            )
            .where(*review_predicates)
            .group_by(ProviderReview.provider_id)
            .subquery()
        )
        review_submissions = (
            select(
                ProviderReview.provider_id.label("provider_id"),
                func.count(ProviderReview.id).label("review_submissions"),
            )
            .where(
                ProviderReview.created_at >= start,
                ProviderReview.created_at < end,
                *self._review_filters(filters, include_deleted=True),
            )
            .group_by(ProviderReview.provider_id)
            .subquery()
        )
        saved = (
            select(
                ProviderFavorite.provider_id.label("provider_id"),
                func.count(ProviderFavorite.id).label("saved_count"),
            )
            .group_by(ProviderFavorite.provider_id)
            .subquery()
        )
        profile_views = (
            select(
                TrafficProviderProfileDaily.provider_id.label("provider_id"),
                func.sum(TrafficProviderProfileDaily.profile_views).label("profile_views"),
            )
            .where(
                TrafficProviderProfileDaily.visit_date >= start_date,
                TrafficProviderProfileDaily.visit_date <= end_date,
            )
            .group_by(TrafficProviderProfileDaily.provider_id)
            .subquery()
        )
        predicates = self.provider_conditions(filters)
        # Deliberately independent of publication/status filters by default:
        # the entire provider catalogue, including zero-view providers, is
        # available for administration and comparison.
        total = int(
            self.db.scalar(
                select(func.count(Provider.id)).where(*predicates)
            )
            or 0
        )
        metric = {
            "profile_views": func.coalesce(profile_views.c.profile_views, 0),
            "review_submissions": func.coalesce(
                review_submissions.c.review_submissions, 0
            ),
            "average_rating": ratings.c.average_rating,
            "rating_count": func.coalesce(ratings.c.rating_count, 0),
            "saved_count": func.coalesce(saved.c.saved_count, 0),
        }[sort] if sort != "name" else None
        sort_expr = (
            Provider.name
            if sort == "name"
            else metric if metric is not None
            else func.coalesce(profile_views.c.profile_views, 0)
        )
        order = sort_expr.asc().nulls_last() if direction == "asc" else sort_expr.desc().nulls_last()
        rows = self.db.execute(
            select(
                Provider.id,
                Provider.name,
                Provider.provider_type,
                Provider.status,
                Provider.publication_status,
                func.coalesce(profile_views.c.profile_views, 0).label("profile_views"),
                func.coalesce(review_submissions.c.review_submissions, 0),
                ratings.c.average_rating,
                func.coalesce(ratings.c.rating_count, 0),
                func.coalesce(saved.c.saved_count, 0),
            )
            .outerjoin(ratings, ratings.c.provider_id == Provider.id)
            .outerjoin(
                review_submissions,
                review_submissions.c.provider_id == Provider.id,
            )
            .outerjoin(saved, saved.c.provider_id == Provider.id)
            .outerjoin(profile_views, profile_views.c.provider_id == Provider.id)
            .where(*predicates)
            .order_by(order, Provider.name.asc(), Provider.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        data = [
            {
                "provider_id": str(row[0]),
                "name": row[1],
                "provider_type": row[2].value,
                "provider_status": row[3].value,
                "publication_status": row[4].value,
                "profile_views": int(row[5]),
                "review_submissions": int(row[6]),
                "average_rating": float(row[7]) if row[7] is not None else None,
                "rating_count": int(row[8]),
                "saved_count": int(row[9]),
            }
            for row in rows
        ]
        return data, total