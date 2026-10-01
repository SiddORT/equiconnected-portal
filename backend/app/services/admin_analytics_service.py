"""Metric contracts and timezone-aware reporting for the administrator analytics API."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.core.time_standards import local_date_bounds, system_today
from app.models.enums import InvitationStatus
from app.models.contact_enquiry import ContactEnquiry
from app.models.invitation import ProviderInvitation
from app.models.member_feedback import MemberFeedback
from app.models.provider import ProviderReview
from app.models.public_visit import PublicVisitDaily
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.subscriber import Subscriber
from app.models.user import User
from app.repositories.admin_analytics_repository import AdminAnalyticsRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.schemas.admin_analytics import (
    AnalyticsDomain,
    AnalyticsFilters,
    AnalyticsPreset,
)


class AnalyticsMetricNotFound(ValueError):
    """The requested analytics metric or domain is not supported."""


class AdminAnalyticsService:
    MAX_RANKING_EXPORT_ROWS = 5_000

    def __init__(self, repository: AdminAnalyticsRepository) -> None:
        self.repo = repository
        self.db = repository.db

    @staticmethod
    def _month_end(first: date) -> date:
        return date(first.year, first.month, monthrange(first.year, first.month)[1])

    def _coverage(self, timezone_name: str) -> dict[str, dict[str, Any]]:
        sources = {
            "member_registrations": (User, User.created_at),
            "provider_applications": (
                ProviderRegistrationApplication,
                ProviderRegistrationApplication.created_at,
            ),
            "invitations": (ProviderInvitation, ProviderInvitation.created_at),
            "provider_reviews": (ProviderReview, ProviderReview.created_at),
            "platform_feedback": (MemberFeedback, MemberFeedback.submitted_at),
            "contact_enquiries": (ContactEnquiry, ContactEnquiry.submitted_at),
            "subscribers": (Subscriber, Subscriber.submitted_at),
        }
        coverage = {}
        for source, (model, column) in sources.items():
            dates = self.repo.first_last_dates(model, column, timezone_name)
            coverage[source] = {
                "from": dates["from"].isoformat() if dates["from"] is not None else None,
                "through": dates["through"].isoformat() if dates["through"] is not None else None,
                "available": True,
                "coverage_start": None,
                "coverage_known": False,
                "note": "First/last retained event dates are not proof of complete historical coverage.",
            }
        legacy = self.repo.first_last_dates(
            PublicVisitDaily, PublicVisitDaily.visit_date, timezone_name
        )
        coverage["legacy_homepage_visits"] = {
            "from": legacy["from"].isoformat() if legacy["from"] is not None else None,
            "through": legacy["through"].isoformat() if legacy["through"] is not None else None,
            "available": True,
            "coverage_start": None,
            "coverage_known": False,
            "definition": "Legacy homepage-only aggregate; independent from sitewide page tracking.",
        }
        tracking_start = self.repo.traffic_tracking_start(timezone_name)
        today = system_today(timezone_name)
        for source in ("traffic_page_views", "traffic_provider_profiles", "estimated_visitors"):
            coverage[source] = {
                "from": tracking_start.isoformat() if tracking_start is not None else None,
                "through": today.isoformat() if tracking_start is not None else None,
                "available": tracking_start is not None,
                "coverage_start": tracking_start.isoformat() if tracking_start is not None else None,
                "coverage_known": tracking_start is not None,
            }
        return coverage

    def _resolve_period(
        self, filters: AnalyticsFilters, timezone_name: str
    ) -> tuple[date, date]:
        today = system_today(timezone_name)
        preset = filters.preset
        if preset != AnalyticsPreset.CUSTOM and (
            filters.date_from is not None or filters.date_to is not None
        ):
            raise ValueError("date_from and date_to are only valid with preset=custom.")
        if preset == AnalyticsPreset.TODAY:
            return today, today
        if preset == AnalyticsPreset.YESTERDAY:
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        if preset == AnalyticsPreset.LAST_7_DAYS:
            return today - timedelta(days=6), today
        if preset == AnalyticsPreset.LAST_30_DAYS:
            return today - timedelta(days=29), today
        if preset == AnalyticsPreset.THIS_MONTH:
            return today.replace(day=1), today
        if preset == AnalyticsPreset.LAST_MONTH:
            previous_month_last = today.replace(day=1) - timedelta(days=1)
            return previous_month_last.replace(day=1), previous_month_last
        if preset == AnalyticsPreset.CUSTOM:
            if filters.date_from is None or filters.date_to is None:
                raise ValueError(
                    "Custom analytics ranges require date_from and date_to."
                )
            if filters.date_from > filters.date_to:
                raise ValueError("date_from must be on or before date_to.")
            if (filters.date_to - filters.date_from).days >= 3660:
                raise ValueError("Custom analytics ranges are limited to 10 years.")
            if filters.date_to > today:
                raise ValueError("Analytics date_to cannot be in the future.")
            return filters.date_from, filters.date_to
        coverage = self._coverage(timezone_name)
        available_starts = [
            date.fromisoformat(item["from"])
            for item in coverage.values()
            if item["from"] is not None
        ]
        first = min(available_starts) if available_starts else today
        return first, today

    def _envelope(self, filters: AnalyticsFilters) -> dict[str, Any]:
        settings = SystemSettingsRepository(self.db).get_or_create()
        tz_name = settings.timezone
        start_day, end_day = self._resolve_period(filters, tz_name)
        start, end = local_date_bounds(start_day, end_day, tz_name)
        assert start is not None and end is not None
        coverage = self._coverage(tz_name)
        return {
            "timezone": tz_name,
            "period": {
                "preset": filters.preset.value,
                "date_from": start_day.isoformat(),
                "date_to": end_day.isoformat(),
                "group_by": filters.group_by.value,
            },
            "coverage": coverage,
            "tracking_started_date": coverage["traffic_page_views"]["from"],
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "_start_day": start_day,
            "_end_day": end_day,
            "_start": start,
            "_end": end,
        }

    @staticmethod
    def _clean(envelope: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in envelope.items() if not key.startswith("_")}

    @staticmethod
    def _bucket_start(day: date, group_by: str) -> date:
        if group_by == "weekly":
            return day - timedelta(days=day.weekday())
        if group_by == "monthly":
            return day.replace(day=1)
        return day

    @staticmethod
    def _next_bucket(day: date, group_by: str) -> date:
        if group_by == "weekly":
            return day + timedelta(days=7)
        if group_by == "monthly":
            return date(day.year + (day.month == 12), day.month % 12 + 1, 1)
        return day + timedelta(days=1)

    def _zero_filled_series(
        self,
        grouped: list[tuple[Any, int]],
        *,
        start_day: date,
        end_day: date,
        group_by: str,
    ) -> list[dict[str, Any]]:
        values: dict[str, int] = {}
        for bucket, value in grouped:
            if isinstance(bucket, datetime):
                bucket_day = bucket.date()
            elif isinstance(bucket, date):
                bucket_day = bucket
            else:
                bucket_day = date.fromisoformat(str(bucket)[:10])
            values[bucket_day.isoformat()] = int(value)
        current = self._bucket_start(start_day, group_by)
        last = self._bucket_start(end_day, group_by)
        result: list[dict[str, Any]] = []
        while current <= last:
            key = current.isoformat()
            result.append({"bucket": key, "value": values.get(key, 0)})
            current = self._next_bucket(current, group_by)
        return result

    @staticmethod
    def _percent_change(current: int, previous: int) -> dict[str, Any]:
        if previous == 0:
            return {
                "available": False,
                "previous_value": previous,
                "change_percent": None,
                "unavailable_reason": "zero_baseline",
            }
        return {
            "available": True,
            "previous_value": previous,
            "change_percent": round((current - previous) * 100 / previous, 2),
            "unavailable_reason": None,
        }

    def _metric(
        self,
        *,
        key: str,
        label: str,
        value: int | float | None,
        unit: str,
        basis: str,
        definition: str,
        comparison: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = {
            "key": key,
            "label": label,
            "value": value,
            "unit": unit,
            "basis": basis,
            "definition": definition,
        }
        if basis == "period":
            result["comparison"] = comparison or {
                "available": False,
                "previous_value": None,
                "change_percent": None,
                "unavailable_reason": "coverage_unknown",
            }
        return result

    def _period_metric(
        self,
        *,
        envelope: dict[str, Any],
        filters: AnalyticsFilters,
        key: str,
        label: str,
        unit: str,
        definition: str,
        count_fn,
        source: str,
    ) -> dict[str, Any]:
        count = int(count_fn(envelope["_start"], envelope["_end"]))
        days = (envelope["_end_day"] - envelope["_start_day"]).days + 1
        previous_to = envelope["_start_day"] - timedelta(days=1)
        previous_from = previous_to - timedelta(days=days - 1)
        coverage_start_value = envelope["coverage"].get(source, {}).get(
            "coverage_start"
        )
        comparison = {
            "available": False,
            "previous_value": None,
            "change_percent": None,
            "unavailable_reason": "coverage_unknown",
        }
        if coverage_start_value is not None and previous_from >= date.fromisoformat(coverage_start_value):
            previous_start, previous_end = local_date_bounds(
                previous_from, previous_to, envelope["timezone"]
            )
            previous = int(count_fn(previous_start, previous_end))
            comparison = self._percent_change(count, previous)
        metric = self._metric(
            key=key,
            label=label,
            value=count,
            unit=unit,
            basis="period",
            definition=definition,
            comparison=comparison,
        )
        metric["coverage"] = envelope["coverage"].get(source, {})
        return metric

    def _traffic_period_metric(
        self,
        *,
        envelope: dict[str, Any],
        key: str,
        label: str,
        unit: str,
        definition: str,
        count_fn,
        source: str,
    ) -> dict[str, Any]:
        coverage = envelope["coverage"].get(source, {})
        tracking_start = coverage.get("coverage_start")
        tracking_day = date.fromisoformat(tracking_start) if tracking_start else None
        if tracking_day is None or envelope["_end_day"] < tracking_day:
            metric = self._metric(
                key=key,
                label=label,
                value=None,
                unit=unit,
                basis="period",
                definition=definition,
                comparison={
                    "available": False,
                    "previous_value": None,
                    "change_percent": None,
                    "unavailable_reason": "outside_tracking_coverage",
                },
            )
            metric.update({"available": False, "partial_coverage": False, "coverage": coverage})
            return metric
        selected_start = max(envelope["_start_day"], tracking_day)
        current = int(count_fn(selected_start, envelope["_end_day"]))
        duration_days = (
            envelope["_end_day"] - envelope["_start_day"]
        ).days + 1
        previous_to = envelope["_start_day"] - timedelta(days=1)
        previous_from = previous_to - timedelta(days=duration_days - 1)
        if previous_from >= tracking_day:
            previous = int(count_fn(previous_from, previous_to))
            comparison = self._percent_change(current, previous)
        else:
            comparison = {
                "available": False,
                "previous_value": None,
                "change_percent": None,
                "unavailable_reason": "tracking_coverage_gap",
            }
        metric = self._metric(
            key=key,
            label=label,
            value=current,
            unit=unit,
            basis="period",
            definition=definition,
            comparison=comparison,
        )
        metric.update(
            {
                "available": True,
                "partial_coverage": envelope["_start_day"] < tracking_day,
                "coverage": coverage,
            }
        )
        return metric

    def summary(self, filters: AnalyticsFilters) -> dict[str, Any]:
        envelope = self._envelope(filters)
        start, end = envelope["_start"], envelope["_end"]
        tracked_from = (
            date.fromisoformat(envelope["tracking_started_date"])
            if envelope["tracking_started_date"]
            else None
        )
        traffic_available = (
            tracked_from is not None and envelope["_end_day"] >= tracked_from
        )
        traffic_partial = traffic_available and envelope["_start_day"] < tracked_from
        provider_inventory = self.repo.current_provider_inventory(filters)
        member_current = self.repo.member_cohort_breakdown(
            filters=filters, start=start, end=end
        )
        application_current = self.repo.application_status_breakdown(filters)
        invitation_current = self.repo.invitation_status_breakdown(filters)
        review_states, deleted_reviews = self.repo.review_state_breakdown(filters)
        ratings = self.repo.rating_summary(filters)
        feedback = self.repo.feedback_status_breakdown(filters)
        count_metrics = [
            self._period_metric(
                envelope=envelope,
                filters=filters,
                key="public_member_registrations",
                label="New member registrations",
                unit="accounts",
                definition="Newly created horse-owner and stable-manager accounts, counted once per account.",
                source="member_registrations",
                count_fn=lambda first, last: self.repo.registration_count(
                    start=first, end=last, filters=filters
                ),
            ),
            self._period_metric(
                envelope=envelope,
                filters=filters,
                key="provider_applications",
                label="Provider applications submitted",
                unit="applications",
                definition="Provider-account applications created in the selected period.",
                source="provider_applications",
                count_fn=lambda first, last: self.repo.application_count(
                    start=first, end=last, filters=filters
                ),
            ),
            self._period_metric(
                envelope=envelope,
                filters=filters,
                key="contact_enquiries",
                label="Contact enquiries",
                unit="enquiries",
                definition="Durably stored contact enquiries, independent of notification email delivery.",
                source="contact_enquiries",
                count_fn=lambda first, last: self.repo.enquiry_count(
                    start=first, end=last, filters=filters
                ),
            ),
            self._period_metric(
                envelope=envelope,
                filters=filters,
                key="new_subscribers",
                label="New subscribers",
                unit="subscriptions",
                definition="New unique stored subscriptions; repeated attempts for an existing email are not counted.",
                source="subscribers",
                count_fn=lambda first, last: self.repo.subscriber_count(
                    start=first, end=last, filters=filters
                ),
            ),
            self._period_metric(
                envelope=envelope,
                filters=filters,
                key="provider_review_submissions",
                label="Provider review submissions",
                unit="reviews",
                definition="Initial review records created in the period; edits and moderation actions are not submissions.",
                source="provider_reviews",
                count_fn=lambda first, last: self.repo.review_submission_count(
                    start=first, end=last, filters=filters
                ),
            ),
            self._period_metric(
                envelope=envelope,
                filters=filters,
                key="platform_feedback_submissions",
                label="Platform feedback submissions",
                unit="submissions",
                definition="Persisted private feedback records submitted in the period, including later-withdrawn submissions.",
                source="platform_feedback",
                count_fn=lambda first, last: self.repo.feedback_count(
                    start=first, end=last, filters=filters
                ),
            ),
            self._period_metric(
                envelope=envelope,
                filters=filters,
                key="provider_invitations_created",
                label="Provider invitations created",
                unit="invitations",
                definition="Invitation records created in the period; accepted/completed includes completion after acceptance.",
                source="invitations",
                count_fn=lambda first, last: self.repo.invitation_count(
                    start=first, end=last, filters=filters
                ),
            ),
        ]
        invitation_sent_metric = self._period_metric(
            envelope=envelope,
            filters=filters,
            key="provider_invitations_sent",
            label="Provider invitations sent",
            unit="invitations",
            definition="Persisted invitation sent timestamp in the selected period.",
            source="invitations",
            count_fn=lambda first, last: self.repo.invitation_sent_count(
                start=first, end=last, filters=filters
            ),
        )
        application_decisions_metric = self._period_metric(
            envelope=envelope,
            filters=filters,
            key="provider_application_decisions",
            label="Application decisions recorded",
            unit="decisions",
            definition="Approval/rejection decisions counted by their recorded reviewed_at timestamp.",
            source="provider_applications",
            count_fn=lambda first, last: self.repo.application_decision_count(
                start=first, end=last, filters=filters
            ),
        )
        legacy_count = self.repo.legacy_homepage_count(
            start_date=envelope["_start_day"], end_date=envelope["_end_day"]
        )
        legacy = self._metric(
            key="legacy_homepage_visits",
            label="Legacy homepage visits",
            value=legacy_count,
            unit="visits",
            basis="period",
            definition="The existing daily homepage-only counter. It is not combined with new page views or visitor estimates.",
        )
        legacy["coverage"] = envelope["coverage"]["legacy_homepage_visits"]
        traffic_metrics = [
            self._traffic_period_metric(
                envelope=envelope,
                key="website_page_views",
                label="Website page views",
                unit="views",
                source="traffic_page_views",
                count_fn=lambda first, last: self.repo.traffic_page_total(
                    start_date=first, end_date=last
                ),
                definition="Successful allowlisted route views since traffic tracking began.",
            ),
            self._traffic_period_metric(
                envelope=envelope,
                key="estimated_visitor_days",
                label="Estimated visitor-days",
                unit="visitor-days",
                source="estimated_visitors",
                count_fn=lambda first, last: self.repo.visitor_day_total(
                    start_date=first, end_date=last
                ),
                definition="Browser-deduplicated daily estimate summed as visitor-days, not unique people.",
            ),
            self._traffic_period_metric(
                envelope=envelope,
                key="directory_views",
                label="Member directory views",
                unit="views",
                source="traffic_page_views",
                count_fn=lambda first, last: self.repo.traffic_page_total(
                    start_date=first,
                    end_date=last,
                    categories=("provider_directory",),
                ),
                definition="Successful verified-member directory page views.",
            ),
            self._traffic_period_metric(
                envelope=envelope,
                key="provider_profile_views",
                label="Provider profile views",
                unit="views",
                source="traffic_provider_profiles",
                count_fn=lambda first, last: self.repo.profile_view_total(
                    start_date=first,
                    end_date=last,
                    provider_id=filters.provider_id,
                    filters=filters,
                ),
                definition="Successful accessible member profile views; applicable provider filters apply only to this metric.",
            ),
        ]
        latest_estimate = (
            self.repo.latest_visitor_estimate(through=envelope["_end_day"])
            if envelope["tracking_started_date"]
            and envelope["_end_day"] >= date.fromisoformat(envelope["tracking_started_date"])
            else None
        )
        # A covered day with no first-browser events is a genuine zero, not a
        # missing estimate. Always label the day rather than silently showing an
        # older nonzero day's count as the latest day in the selected range.
        if traffic_available and (
            latest_estimate is None or latest_estimate[0] < envelope["_end_day"]
        ):
            latest_estimate = (envelope["_end_day"], 0)
        return {
            **self._clean(envelope),
            "sections": {
                "traffic": {
                    "metrics": [
                        traffic_metrics[0],
                        traffic_metrics[1],
                        {
                            "key": "latest_daily_visitor_estimate",
                            "label": "Latest daily visitor estimate",
                            "value": latest_estimate[1] if latest_estimate else None,
                            "date": latest_estimate[0].isoformat() if latest_estimate else None,
                            "unit": "estimated visitors",
                            "basis": "current",
                            "definition": "Latest available browser-deduplicated daily estimate; devices/storage resets may overcount and unavailable storage may undercount.",
                        },
                        traffic_metrics[2],
                        traffic_metrics[3],
                        legacy,
                    ],
                    "coverage": {
                        "tracked_since": envelope["tracking_started_date"],
                        "available": traffic_available,
                        "partial": traffic_partial,
                    },
                },
                "registrations": {
                    "metrics": [
                        count_metrics[0],
                        self._metric(
                            key="verified_registrations",
                            label="Verified in selected cohort",
                            value=member_current["verified"].get("true", 0),
                            unit="accounts",
                            basis="current",
                            definition="Current email-verification state of selected-period public member accounts.",
                        ),
                    ],
                    "cohort_current_state": member_current,
                },
                "providers": {
                    "metrics": [
                        self._metric(
                            key="active_providers",
                            label="Active providers",
                            value=provider_inventory["active"],
                            unit="providers",
                            basis="current",
                            definition="Current provider status is ACTIVE, regardless of publication.",
                        ),
                        self._metric(
                            key="active_published_providers",
                            label="Published active providers",
                            value=provider_inventory["active_published"],
                            unit="providers",
                            basis="current",
                            definition="Current providers that are both ACTIVE and PUBLISHED.",
                        ),
                        self._metric(
                            key="total_providers",
                            label="Total providers",
                            value=provider_inventory["total"],
                            unit="providers",
                            basis="current",
                            definition="Current provider catalogue inventory.",
                        ),
                    ],
                    "inventory": provider_inventory,
                },
                "applications": {
                    "current_status": {
                        str(key.value): value for key, value in application_current.items()
                    },
                    "submitted_cohort_status": {
                        str(key.value): value
                        for key, value in self.repo.application_status_breakdown(
                            filters, start=start, end=end
                        ).items()
                    },
                    "invitation_status": {
                        str(key.value): value for key, value in invitation_current.items()
                    },
                    "invitation_cohort_status": {
                        str(key.value): value
                        for key, value in self.repo.invitation_status_breakdown(
                            filters, start=start, end=end
                        ).items()
                    },
                    "metrics": [
                        count_metrics[1],
                        application_decisions_metric,
                        count_metrics[6],
                        invitation_sent_metric,
                    ],
                    "legacy_compatible_invitation_totals": {
                        "accepted": (
                            invitation_current.get(InvitationStatus.ACCEPTED, 0)
                            + invitation_current.get(InvitationStatus.COMPLETED, 0)
                        ),
                        "cancelled_or_expired": (
                            invitation_current.get(InvitationStatus.CANCELLED, 0)
                            + invitation_current.get(InvitationStatus.EXPIRED, 0)
                        ),
                        "note": "Cancelled/expired invitations are not claims of recipient rejection.",
                    },
                    "application_decisions_by_recorded_status": {
                        str(key.value): value
                        for key, value in self.repo.application_decision_breakdown(
                            start=start, end=end, filters=filters
                        ).items()
                    },
                },
                "engagement": {
                    "metrics": [count_metrics[2], count_metrics[3]],
                    "enquiry_types": self.repo.enquiry_type_breakdown(
                        filters, start=start, end=end
                    ),
                    "subscriber_types": self.repo.subscriber_type_breakdown(
                        filters, start=start, end=end
                    ),
                },
                "reviews": {
                    "metrics": [
                        count_metrics[4],
                        self._metric(
                            key="eligible_review_rating_average",
                            label="Eligible average rating",
                            value=ratings["average"],
                            unit="stars",
                            basis="current",
                            definition="Average of undeleted PUBLISHED or HIDDEN provider ratings.",
                        ),
                        self._metric(
                            key="eligible_review_rating_count",
                            label="Eligible rating count",
                            value=ratings["count"],
                            unit="ratings",
                            basis="current",
                            definition="Undeleted PUBLISHED or HIDDEN reviews. Hidden ratings remain eligible; pending/rejected do not.",
                        ),
                    ],
                    "current_status": {
                        str(key.value): value for key, value in review_states.items()
                    },
                    "retained_deleted_history": deleted_reviews,
                    "star_distribution": {
                        str(star): ratings["stars"].get(star, 0)
                        for star in range(1, 6)
                    },
                },
                "feedback": {
                    "metrics": [
                        count_metrics[5],
                        self._metric(
                            key="feedback_rating_average",
                            label="Average platform feedback rating",
                            value=feedback["rating_average"],
                            unit="stars",
                            basis="current",
                            definition="Average optional rating among non-withdrawn feedback records with a rating.",
                        ),
                        self._metric(
                            key="feedback_rated_response_count",
                            label="Rated feedback responses",
                            value=feedback["rating_count"],
                            unit="responses",
                            basis="current",
                            definition="Non-withdrawn feedback submissions with an optional 1–5 rating.",
                        ),
                    ],
                    "current_status": {
                        str(key.value if hasattr(key, "value") else key): value
                        for key, value in feedback["status"].items()
                    },
                    "withdrawn": feedback["withdrawn"],
                    "categories": feedback["categories"],
                },
            },
        }

    def _series_grouped(
        self, metric: str, filters: AnalyticsFilters, envelope: dict[str, Any]
    ):
        start, end = envelope["_start"], envelope["_end"]
        common = {
            "start": start,
            "end": end,
            "timezone_name": envelope["timezone"],
            "group_by": filters.group_by.value,
            "filters": filters,
        }
        if metric == "public_member_registrations":
            source = "member_registrations"
            grouped = self.repo.registration_series(**common)
        elif metric == "provider_applications":
            source = "provider_applications"
            grouped = self.repo.application_series(**common)
        elif metric == "provider_invitations_created":
            source = "invitations"
            grouped = self.repo.invitation_series(**common)
        elif metric == "provider_invitations_sent":
            source = "invitations"
            grouped = self.repo.invitation_sent_series(**common)
        elif metric == "provider_application_decisions":
            source = "provider_applications"
            grouped = self.repo.application_decision_series(**common)
        elif metric == "contact_enquiries":
            source = "contact_enquiries"
            grouped = self.repo.enquiry_series(**common)
        elif metric == "new_subscribers":
            source = "subscribers"
            grouped = self.repo.subscriber_series(**common)
        elif metric == "provider_review_submissions":
            source = "provider_reviews"
            grouped = self.repo.review_submission_series(**common)
        elif metric == "platform_feedback_submissions":
            source = "platform_feedback"
            grouped = self.repo.feedback_series(**common)
        elif metric in {
            "website_page_views",
            "directory_views",
            "provider_profile_views",
            "estimated_visitor_days",
        }:
            source = (
                "traffic_provider_profiles"
                if metric == "provider_profile_views"
                else "estimated_visitors"
                if metric == "estimated_visitor_days"
                else "traffic_page_views"
            )
            tracking_from_value = envelope["coverage"].get(source, {}).get("from")
            tracking_from = (
                date.fromisoformat(tracking_from_value)
                if tracking_from_value
                else None
            )
            if tracking_from is None or envelope["_end_day"] < tracking_from:
                return None, source
            first_day = max(envelope["_start_day"], tracking_from)
            if metric == "website_page_views":
                grouped = self.repo.traffic_page_daily_series(
                    start_date=first_day,
                    end_date=envelope["_end_day"],
                )
            elif metric == "directory_views":
                grouped = self.repo.traffic_page_daily_series(
                    start_date=first_day,
                    end_date=envelope["_end_day"],
                    categories=("provider_directory",),
                )
            elif metric == "provider_profile_views":
                grouped = self.repo.profile_view_series(
                    provider_id=filters.provider_id,
                    start_date=first_day,
                    end_date=envelope["_end_day"],
                    filters=filters,
                )
            else:
                grouped = self.repo.visitor_daily_series(
                    start_date=first_day,
                    end_date=envelope["_end_day"],
                )
            if filters.group_by.value != "daily":
                aggregated: dict[date, int] = {}
                for day, value in grouped:
                    bucket = self._bucket_start(day, filters.group_by.value)
                    aggregated[bucket] = aggregated.get(bucket, 0) + int(value)
                grouped = list(aggregated.items())
            return (
                self._zero_filled_series(
                    grouped,
                    start_day=first_day,
                    end_day=envelope["_end_day"],
                    group_by=filters.group_by.value,
                ),
                source,
            )
        else:
            raise AnalyticsMetricNotFound(f"Unsupported analytics series metric: {metric}")
        coverage = envelope["coverage"].get(source, {})
        if (
            coverage.get("coverage_start")
            and envelope["_start_day"] < date.fromisoformat(coverage["coverage_start"])
        ):
            return None, source
        return (
            self._zero_filled_series(
                grouped,
                start_day=envelope["_start_day"],
                end_day=envelope["_end_day"],
                group_by=filters.group_by.value,
            ),
            source,
        )

    def series(self, metric: str, filters: AnalyticsFilters) -> dict[str, Any]:
        envelope = self._envelope(filters)
        if metric == "legacy_homepage_visits":
            daily = self.repo.legacy_homepage_series(
                start_date=envelope["_start_day"], end_date=envelope["_end_day"]
            )
            buckets: dict[date, int] = {}
            for day, count in daily:
                bucket = self._bucket_start(day, filters.group_by.value)
                buckets[bucket] = buckets.get(bucket, 0) + int(count)
            series = self._zero_filled_series(
                list(buckets.items()),
                start_day=envelope["_start_day"],
                end_day=envelope["_end_day"],
                group_by=filters.group_by.value,
            )
            source = "legacy_homepage_visits"
            envelope["coverage"][source] = {
                "from": None,
                "through": None,
                "available": True,
                "coverage_start": None,
                "coverage_known": False,
                "definition": "Legacy homepage-only count; never combined with new traffic.",
            }
        else:
            series, source = self._series_grouped(metric, filters, envelope)
        return {
            **self._clean(envelope),
            "metric": metric,
            "unit": {
                "public_member_registrations": "accounts",
                "provider_applications": "applications",
                "provider_invitations_created": "invitations",
                "contact_enquiries": "enquiries",
                "new_subscribers": "subscriptions",
                "provider_review_submissions": "reviews",
                "platform_feedback_submissions": "submissions",
                "legacy_homepage_visits": "visits",
                "website_page_views": "views",
                "directory_views": "views",
                "provider_profile_views": "views",
                "estimated_visitor_days": "visitor-days",
            }.get(metric, "count"),
            "coverage": envelope["coverage"].get(source, {}),
            "available": series is not None,
            "partial_coverage": bool(
                envelope["coverage"].get(source, {}).get("coverage_start")
                and envelope["_start_day"]
                < date.fromisoformat(envelope["coverage"][source]["coverage_start"])
                and envelope["_end_day"]
                >= date.fromisoformat(envelope["coverage"][source]["coverage_start"])
            ),
            "data": series,
            "definition": (
                "Legacy daily homepage visits only; separate from tracked route views."
                if metric == "legacy_homepage_visits"
                else f"Persisted {metric.replace('_', ' ')} grouped by system-timezone {filters.group_by.value}."
            ),
        }

    def breakdowns(self, domain: AnalyticsDomain, filters: AnalyticsFilters) -> dict[str, Any]:
        envelope = self._envelope(filters)
        start, end = envelope["_start"], envelope["_end"]
        groups: dict[str, Any]
        definitions: dict[str, str]
        if domain == AnalyticsDomain.REGISTRATIONS:
            groups = {
                "selected_cohort": self.repo.member_cohort_breakdown(
                    start=start, end=end, filters=filters
                )
            }
            definitions = {
                "selected_cohort": "New public-member registration cohort in the selected period, with current verification/account state."
            }
        elif domain == AnalyticsDomain.PROVIDERS:
            groups = {"current_inventory": self.repo.current_provider_inventory(filters)}
            definitions = {
                "current_inventory": "Current provider inventory; not a historical reconstruction."
            }
        elif domain == AnalyticsDomain.APPLICATIONS:
            groups = {
                "period_decisions": {
                    str(key.value): value
                    for key, value in self.repo.application_decision_breakdown(
                        filters=filters, start=start, end=end
                    ).items()
                },
                "submitted_cohort_current_status": {
                    str(key.value): value
                    for key, value in self.repo.application_status_breakdown(
                        filters, start=start, end=end
                    ).items()
                },
                "all_current_status": {
                    str(key.value): value
                    for key, value in self.repo.application_status_breakdown(filters).items()
                },
            }
            definitions = {
                "period_decisions": "Approval/rejection decisions recorded at reviewed_at in the selected period, regardless of submission date.",
                "submitted_cohort_current_status": "Current status of applications submitted in the selected date range.",
                "all_current_status": "Current application backlog/status snapshot.",
            }
        elif domain == AnalyticsDomain.INVITATIONS:
            groups = {
                "created_cohort_current_status": {
                    str(key.value): value
                    for key, value in self.repo.invitation_status_breakdown(
                        filters, start=start, end=end
                    ).items()
                },
                "all_current_status": {
                    str(key.value): value
                    for key, value in self.repo.invitation_status_breakdown(filters).items()
                },
            }
            definitions = {
                "created_cohort_current_status": "Current state of invitations created in the selected period. CANCELLED/EXPIRED are not recipient rejections.",
                "all_current_status": "Current invitation state snapshot. ACCEPTED and COMPLETED are combined only in the legacy-compatible accepted total.",
            }
        elif domain == AnalyticsDomain.REVIEWS:
            statuses, deleted = self.repo.review_state_breakdown(filters)
            cohort_statuses, cohort_deleted = self.repo.review_state_breakdown(
                filters, start=start, end=end
            )
            ratings = self.repo.rating_summary(filters)
            actions = self.repo.review_action_breakdown(
                start=start, end=end, filters=filters
            )
            top_reviewed, _ = self.repo.provider_ranking(
                filters=filters,
                start=start,
                end=end,
                start_date=envelope["_start_day"],
                end_date=envelope["_end_day"],
                page=1,
                page_size=10,
                sort="rating_count",
                direction="desc",
            )
            submission_leaders, _ = self.repo.provider_ranking(
                filters=filters,
                start=start,
                end=end,
                start_date=envelope["_start_day"],
                end_date=envelope["_end_day"],
                page=1,
                page_size=10,
                sort="review_submissions",
                direction="desc",
            )
            groups = {
                "active_moderation_status": {
                    str(key.value): value for key, value in statuses.items()
                },
                "submitted_cohort_current_status": {
                    str(key.value): value for key, value in cohort_statuses.items()
                },
                "star_distribution": {
                    str(star): ratings["stars"].get(star, 0) for star in range(1, 6)
                },
                "eligible_ratings": {
                    "average": ratings["average"],
                    "count": ratings["count"],
                },
                "retained_deleted_history": {"count": deleted},
                "submitted_cohort_retained_deleted_history": {"count": cohort_deleted},
                "period_actions": actions,
                "top_reviewed_providers": top_reviewed,
                "period_submission_leaders": submission_leaders,
            }
            definitions = {
                "active_moderation_status": "Undeleted provider reviews by moderation status.",
                "submitted_cohort_current_status": "Current moderation status of undeleted reviews originally submitted in the selected period.",
                "star_distribution": "Only undeleted PUBLISHED or HIDDEN ratings; HIDDEN ratings remain eligible.",
                "eligible_ratings": "Average and count over undeleted PUBLISHED or HIDDEN provider ratings.",
                "retained_deleted_history": "Retained soft-deleted review records, separate from active states.",
                "submitted_cohort_retained_deleted_history": "Retained soft-deleted review records whose original creation date is in the selected period.",
                "period_actions": "Recorded review actions in the selected period. Member edits and moderation actions do not increase initial submission counts.",
                "top_reviewed_providers": "Top providers by current eligible rating count, including published and hidden, undeleted ratings.",
                "period_submission_leaders": "Providers ordered by initial review records created in the selected period; ties resolve by name then ID.",
            }
        elif domain == AnalyticsDomain.FEEDBACK:
            data = self.repo.feedback_status_breakdown(filters, start=start, end=end)
            current_data = self.repo.feedback_status_breakdown(filters)
            groups = {
                "submitted_cohort_current_status": {
                    str(key.value if hasattr(key, "value") else key): value
                    for key, value in data["status"].items()
                },
                "categories": data["categories"],
                "ratings": {
                    "average": data["rating_average"],
                    "count": data["rating_count"],
                    "distribution": {
                        str(star): data["rating_distribution"].get(star, 0)
                        for star in range(1, 6)
                    },
                },
                "withdrawn": {"count": data["withdrawn"]},
                "current_status": {
                    str(key.value if hasattr(key, "value") else key): value
                    for key, value in current_data["status"].items()
                },
                "current_withdrawn": {"count": current_data["withdrawn"]},
            }
            definitions = {
                "submitted_cohort_current_status": "Current state of non-withdrawn feedback submitted during the selected period.",
                "categories": "Private feedback submission category counts; no messages or internal notes are included.",
                "ratings": "Average optional rating, response count, and star distribution among non-withdrawn feedback in the selected period.",
                "withdrawn": "Feedback withdrawn in the selected submission cohort, separate from current status totals.",
                "current_status": "Current non-withdrawn feedback backlog by moderation state.",
                "current_withdrawn": "All-time current withdrawn feedback count.",
            }
        elif domain == AnalyticsDomain.ENQUIRIES:
            groups = {
                "enquiry_type": self.repo.enquiry_type_breakdown(
                    filters, start=start, end=end
                )
            }
            definitions = {
                "enquiry_type": "Durably accepted contact enquiries by stored type; no resolution state is inferred."
            }
        elif domain == AnalyticsDomain.SUBSCRIBERS:
            groups = {
                "subscriber_type": self.repo.subscriber_type_breakdown(
                    filters, start=start, end=end
                )
            }
            definitions = {
                "subscriber_type": "Unique stored subscription records by original registration type."
            }
        elif domain == AnalyticsDomain.TRAFFIC:
            tracked_from_value = envelope["tracking_started_date"]
            tracked_from = (
                date.fromisoformat(tracked_from_value)
                if tracked_from_value
                else None
            )
            if tracked_from is None or envelope["_end_day"] < tracked_from:
                groups = {
                    "page_categories": None,
                    "top_providers": None,
                    "visitor_days": None,
                }
                definitions = {
                    "page_categories": "No tracked traffic is available before the instrumentation rollout date.",
                    "top_providers": "No tracked member provider-profile views are available.",
                    "visitor_days": "Browser-deduplicated estimate totals are unavailable before rollout.",
                }
            else:
                first_day = max(envelope["_start_day"], tracked_from)
                ranked, _ = self.repo.provider_ranking(
                    filters=filters,
                    start=start,
                    end=end,
                    start_date=first_day,
                    end_date=envelope["_end_day"],
                    page=1,
                    page_size=10,
                    sort="profile_views",
                    direction="desc",
                )
                groups = {
                    "page_categories": self.repo.traffic_category_breakdown(
                        start_date=first_day, end_date=envelope["_end_day"]
                    ),
                    "top_providers": ranked,
                    "visitor_days": self.repo.visitor_day_total(
                        start_date=first_day, end_date=envelope["_end_day"]
                    ),
                }
                definitions = {
                    "page_categories": "Allowlisted successful route views by fixed page category; member-only categories are not anonymous views.",
                    "top_providers": "Top provider profiles by verified-member profile views. Ranking is deterministic by provider name and ID for ties.",
                    "visitor_days": "Sum of daily browser estimates; not unique people across the selected period.",
                }
        else:
            raise AnalyticsMetricNotFound(f"Unsupported analytics breakdown domain: {domain.value}")
        return {
            **self._clean(envelope),
            "domain": domain.value,
            "definitions": definitions,
            "groups": groups,
        }

    def provider_ranking(
        self,
        filters: AnalyticsFilters,
        *,
        page: int,
        page_size: int,
        sort: str,
        direction: str,
    ) -> dict[str, Any]:
        envelope = self._envelope(filters)
        ranking_arguments = {
            "filters": filters,
            "start": envelope["_start"],
            "end": envelope["_end"],
            "start_date": envelope["_start_day"],
            "end_date": envelope["_end_day"],
            "page": page,
            "page_size": page_size,
            "sort": sort,
            "direction": direction,
        }
        tracking_date = envelope["tracking_started_date"]
        tracking_start = date.fromisoformat(tracking_date) if tracking_date else None
        if tracking_start is not None:
            ranking_arguments["start_date"] = max(
                envelope["_start_day"], tracking_start
            )
        rows, total = self.repo.provider_ranking(**ranking_arguments)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)
        if page != ranking_arguments["page"]:
            ranking_arguments["page"] = page
            rows, total = self.repo.provider_ranking(**ranking_arguments)
        profile_views_available = (
            tracking_start is not None and envelope["_end_day"] >= tracking_start
        )
        if not profile_views_available:
            for row in rows:
                row["profile_views"] = None
        return {
            **self._clean(envelope),
            "data": rows,
            "meta": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
            "sort": sort,
            "sort_direction": direction,
            "profile_views_available": profile_views_available,
            "profile_views_partial_coverage": bool(
                profile_views_available and envelope["_start_day"] < tracking_start
            ),
            "profile_views_coverage": envelope["coverage"]["traffic_provider_profiles"],
        }