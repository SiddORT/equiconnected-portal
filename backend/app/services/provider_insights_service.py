"""Owner-scoped, aggregate-only provider performance reporting."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select

from app.core.time_standards import local_midnight_utc, resolve_timezone
from app.models.analytics_traffic import (
    TrafficProviderProfileDaily,
    TrafficTrackingMetadata,
)
from app.models.messaging import ProviderConversation
from app.models.provider import Provider
from app.models.provider_favorite import ProviderFavorite
from app.models.provider_insights import (
    ProviderContactClickDaily,
    ProviderContactClickTrackingMetadata,
    ProviderInsightsConversationMetadata,
)
from app.repositories.review_repository import ReviewRepository


InsightPreset = Literal["last_7_days", "last_30_days", "this_month", "custom"]

PROFILE_VIEW_DEFINITION = (
    "Successfully loaded member profile pages for this listing; revisits count "
    "again and this is not an appointment or a unique-person count."
)
CONTACT_CLICK_DEFINITION = (
    "Activations of a listed phone, email, or website link. This does not mean "
    "a call, email, booking, or confirmed lead was completed."
)
CONVERSATION_DEFINITION = (
    "New durable conversations created for this listing and its currently "
    "authorized provider account; replies are not counted."
)
_ACTIONS = ("phone", "email", "website")
CONTACT_CLICK_RECEIPT_RETENTION = timedelta(hours=48)
CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE = 200
CONTACT_CLICK_RECEIPT_CLEANUP_INTERVAL_SECONDS = 60
CONTACT_CLICK_MAX_FUTURE_SKEW = timedelta(minutes=5)


class ProviderInsightsPeriodError(ValueError):
    """The requested inclusive system-calendar period is invalid."""


class InvalidContactClickEventError(ValueError):
    """A UUIDv7 event is outside its bounded retry window."""


class ContactClickTrackingUnavailableError(RuntimeError):
    """No durable contact-click collection boundary is available."""


def _uuid7_timestamp(event_key: UUID) -> datetime:
    if event_key.version != 7:
        raise InvalidContactClickEventError("The event key must be a UUIDv7 value.")
    milliseconds = event_key.int >> 80
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def record_contact_click(
    db,
    *,
    provider_id: UUID,
    action: str,
    event_key: UUID,
    timezone_name: str,
    now: datetime | None = None,
) -> bool:
    """Count once atomically while accepting only in-window UUIDv7 retries.

    UUIDv7 embeds the activation time, so old replays are rejected even after
    their temporary receipt has expired. Receipts expire at the event's
    48-hour retry deadline and retain no action, listing, account, or member.
    """
    from sqlalchemy import delete, select
    from sqlalchemy.dialects.postgresql import insert

    from app.models.provider_insights import (
        ProviderContactClickReceipt,
        ProviderContactClickTrackingMetadata,
    )

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    event_at = _uuid7_timestamp(event_key)
    if event_at > moment + CONTACT_CLICK_MAX_FUTURE_SKEW:
        raise InvalidContactClickEventError("The event key timestamp is in the future.")
    if event_at <= moment - CONTACT_CLICK_RECEIPT_RETENTION:
        raise InvalidContactClickEventError("The event key is outside the retry window.")
    if action not in _ACTIONS:
        raise ValueError("Contact action is not allowlisted.")
    tracking_started_at = db.scalar(
        select(ProviderContactClickTrackingMetadata.tracking_started_at).where(
            ProviderContactClickTrackingMetadata.id == 1
        )
    )
    if tracking_started_at is None:
        raise ContactClickTrackingUnavailableError()
    if tracking_started_at.tzinfo is None:
        tracking_started_at = tracking_started_at.replace(tzinfo=timezone.utc)
    if event_at < tracking_started_at.astimezone(timezone.utc):
        raise InvalidContactClickEventError(
            "The event key predates contact-click collection."
        )
    click_date = event_at.astimezone(resolve_timezone(timezone_name)).date()

    receipt_table = ProviderContactClickReceipt.__table__
    aggregate_table = ProviderContactClickDaily.__table__
    expiration = event_at + CONTACT_CLICK_RECEIPT_RETENTION
    try:
        accepted_key = db.execute(
            insert(ProviderContactClickReceipt)
            .values(
                event_key=event_key,
                created_at=moment,
                expires_at=expiration,
            )
            .on_conflict_do_update(
                index_elements=[receipt_table.c.event_key],
                set_={"created_at": moment, "expires_at": expiration},
                where=receipt_table.c.expires_at <= moment,
            )
            .returning(receipt_table.c.event_key)
        ).scalar_one_or_none()
        if accepted_key is None:
            db.rollback()
            return False
        db.execute(
            insert(ProviderContactClickDaily)
            .values(
                click_date=click_date,
                provider_id=provider_id,
                action=action,
                click_count=1,
                created_at=moment,
                updated_at=moment,
            )
            .on_conflict_do_update(
                index_elements=[
                    aggregate_table.c.click_date,
                    aggregate_table.c.provider_id,
                    aggregate_table.c.action,
                ],
                set_={
                    "click_count": aggregate_table.c.click_count + 1,
                    "updated_at": moment,
                },
            )
        )
        expired_keys = (
            select(receipt_table.c.event_key)
            .where(receipt_table.c.expires_at < moment)
            .order_by(receipt_table.c.expires_at)
            .limit(CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE)
        )
        db.execute(
            delete(receipt_table).where(
                receipt_table.c.event_key.in_(expired_keys)
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def purge_expired_contact_click_receipts(
    db,
    *,
    now: datetime | None = None,
    batch_size: int = CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE,
) -> int:
    """Delete one bounded batch of expired UUID-only receipts, without counting."""
    from sqlalchemy import delete, select

    from app.models.provider_insights import ProviderContactClickReceipt

    if not 1 <= batch_size <= CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE:
        raise ValueError(
            "Receipt cleanup batch_size must be between 1 and "
            f"{CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE}."
        )
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)

    receipt_table = ProviderContactClickReceipt.__table__
    expired_keys = (
        select(receipt_table.c.event_key)
        .where(receipt_table.c.expires_at <= moment)
        .order_by(receipt_table.c.expires_at)
        .limit(batch_size)
    )
    try:
        result = db.execute(
            delete(receipt_table).where(
                receipt_table.c.event_key.in_(expired_keys)
            )
        )
        deleted = max(int(result.rowcount or 0), 0)
        db.commit()
        return deleted
    except Exception:
        db.rollback()
        raise


def cleanup_expired_contact_click_receipts_once(
    *,
    batch_size: int = CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE,
) -> int:
    """Run one receipt-cleanup batch in an independently owned DB session."""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        return purge_expired_contact_click_receipts(db, batch_size=batch_size)


def resolve_insights_period(
    *,
    preset: InsightPreset,
    today: date,
    date_from: date | None,
    date_to: date | None,
) -> tuple[date, date]:
    if preset == "custom":
        if date_from is None or date_to is None:
            raise ProviderInsightsPeriodError(
                "Custom periods require both date_from and date_to."
            )
        first, last = date_from, date_to
    else:
        if date_from is not None or date_to is not None:
            raise ProviderInsightsPeriodError(
                "date_from and date_to may only be used with preset=custom."
            )
        last = today
        if preset == "last_7_days":
            first = today - timedelta(days=6)
        elif preset == "last_30_days":
            first = today - timedelta(days=29)
        else:
            first = date(today.year, today.month, 1)
    if first > last:
        raise ProviderInsightsPeriodError("date_from must not be after date_to.")
    if last > today:
        raise ProviderInsightsPeriodError("Future dates are not available.")
    if (last - first).days + 1 > 366:
        raise ProviderInsightsPeriodError(
            "Custom periods cannot be longer than 366 inclusive days."
        )
    return first, last


class ProviderInsightsService:
    """Queries only aggregate listing metrics and current public snapshots."""

    def __init__(self, db, review_repository: ReviewRepository) -> None:
        self.db = db
        self.review_repository = review_repository

    def _tracking_started_at(self, model) -> datetime | None:
        return self.db.scalar(
            select(model.tracking_started_at).where(model.id == 1)
        )

    @staticmethod
    def _coverage(
        start: date,
        end: date,
        started_at: datetime | None,
        timezone_name: str,
    ) -> dict:
        if started_at is None:
            return {
                "status": "unknown",
                "from": None,
                "note": "A durable collection boundary is not available.",
            }
        zone = resolve_timezone(timezone_name)
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        local_start = started_at.astimezone(zone)
        coverage_day = local_start.date()
        if end < coverage_day:
            return {
                "status": "unavailable",
                "from": coverage_day.isoformat(),
                "note": f"Collection began on {coverage_day.isoformat()}; earlier dates are unavailable.",
            }
        # Daily aggregates cannot certify a complete rollout calendar date;
        # conservatively call the entire first date partial even if the
        # recorded boundary happens to be exactly midnight.
        partial = start <= coverage_day <= end
        if partial:
            note = f"The rollout calendar date {coverage_day.isoformat()} has partial coverage."
            if start < coverage_day:
                note += " Earlier dates in this period are unavailable."
        else:
            note = "Collection is available for every date in this period."
        return {
            "status": "partial" if partial else "full",
            "from": coverage_day.isoformat(),
            "note": note,
        }

    @staticmethod
    def _utc_bounds(first: date, last: date, timezone_name: str):
        start = local_midnight_utc(first, timezone_name)
        end = local_midnight_utc(last + timedelta(days=1), timezone_name)
        return start, end

    def _profile_total(self, provider_id: UUID, first: date, last: date) -> int:
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(TrafficProviderProfileDaily.profile_views), 0))
                .where(
                    TrafficProviderProfileDaily.provider_id == provider_id,
                    TrafficProviderProfileDaily.visit_date >= first,
                    TrafficProviderProfileDaily.visit_date <= last,
                )
            )
            or 0
        )

    def _click_totals(
        self, provider_id: UUID, first: date, last: date
    ) -> dict[str, int]:
        rows = self.db.execute(
            select(
                ProviderContactClickDaily.action,
                func.sum(ProviderContactClickDaily.click_count),
            )
            .where(
                ProviderContactClickDaily.provider_id == provider_id,
                ProviderContactClickDaily.click_date >= first,
                ProviderContactClickDaily.click_date <= last,
            )
            .group_by(ProviderContactClickDaily.action)
        ).all()
        totals = {action: 0 for action in _ACTIONS}
        totals.update({action: int(value) for action, value in rows})
        return totals

    def _conversation_total(
        self,
        provider_id: UUID,
        provider_user_id: UUID,
        first: date,
        last: date,
        timezone_name: str,
        tracking_started_at: datetime | None = None,
    ) -> int:
        start, end = self._utc_bounds(first, last, timezone_name)
        if tracking_started_at is not None:
            if tracking_started_at.tzinfo is None:
                tracking_started_at = tracking_started_at.replace(
                    tzinfo=timezone.utc
                )
            start = max(start, tracking_started_at.astimezone(timezone.utc))
        return int(
            self.db.scalar(
                select(func.count(ProviderConversation.id)).where(
                    ProviderConversation.provider_id == provider_id,
                    ProviderConversation.provider_user_id == provider_user_id,
                    ProviderConversation.created_at >= start,
                    ProviderConversation.created_at < end,
                )
            )
            or 0
        )

    @staticmethod
    def _metric(
        *,
        value: int | None,
        definition: str,
        coverage: dict,
        previous_value: int | None,
        comparison_coverage: bool,
    ) -> dict:
        reason = None
        change_percent = None
        if value is None:
            reason = (
                "coverage_unknown"
                if coverage["status"] == "unknown"
                else "outside_collection_coverage"
            )
        elif coverage["status"] != "full":
            reason = "partial_coverage"
        elif previous_value is None or not comparison_coverage:
            reason = "previous_period_not_fully_covered"
        elif previous_value == 0:
            reason = "zero_previous_value"
        else:
            change_percent = round((value - previous_value) * 100 / previous_value, 1)
        return {
            "value": value,
            "definition": definition,
            "coverage": coverage,
            "comparison": {
                "change_percent": change_percent,
                "previous_value": previous_value,
                "reason": reason,
            },
        }

    def report(
        self,
        *,
        provider_id: UUID,
        provider_user_id: UUID,
        timezone_name: str,
        today: date,
        preset: InsightPreset,
        date_from: date | None,
        date_to: date | None,
    ) -> dict:
        first, last = resolve_insights_period(
            preset=preset,
            today=today,
            date_from=date_from,
            date_to=date_to,
        )
        provider_name = self.db.scalar(
            select(Provider.name).where(Provider.id == provider_id)
        )
        if provider_name is None:
            return None

        day_count = (last - first).days + 1
        previous_last = first - timedelta(days=1)
        previous_first = previous_last - timedelta(days=day_count - 1)
        tracking_boundaries = {
            "profile_views": self._tracking_started_at(TrafficTrackingMetadata),
            "contact_clicks": self._tracking_started_at(
                ProviderContactClickTrackingMetadata
            ),
            "new_conversations": self._tracking_started_at(
                ProviderInsightsConversationMetadata
            ),
        }
        sources = {
            "profile_views": self._coverage(
                first,
                last,
                tracking_boundaries["profile_views"],
                timezone_name,
            ),
            "contact_clicks": self._coverage(
                first,
                last,
                tracking_boundaries["contact_clicks"],
                timezone_name,
            ),
            "new_conversations": self._coverage(
                first,
                last,
                tracking_boundaries["new_conversations"],
                timezone_name,
            ),
        }
        current_firsts: dict[str, date | None] = {}
        for source, coverage in sources.items():
            if coverage["status"] == "unavailable":
                current_firsts[source] = None
            elif coverage["status"] == "unknown":
                current_firsts[source] = None
            else:
                current_firsts[source] = max(first, date.fromisoformat(coverage["from"]))

        values: dict[str, int | None] = {}
        previous_values: dict[str, int | None] = {}
        for source in sources:
            actual_first = current_firsts[source]
            if actual_first is None:
                values[source] = None
            elif source == "profile_views":
                values[source] = self._profile_total(provider_id, actual_first, last)
            elif source == "contact_clicks":
                values[source] = sum(
                    self._click_totals(provider_id, actual_first, last).values()
                )
            else:
                values[source] = self._conversation_total(
                    provider_id,
                    provider_user_id,
                    actual_first,
                    last,
                    timezone_name,
                    tracking_boundaries[source],
                )

            previous_coverage = self._coverage(
                previous_first,
                previous_last,
                tracking_boundaries[source],
                timezone_name,
            )
            if previous_coverage["status"] != "full":
                previous_values[source] = None
            elif source == "profile_views":
                previous_values[source] = self._profile_total(
                    provider_id, previous_first, previous_last
                )
            elif source == "contact_clicks":
                previous_values[source] = sum(
                    self._click_totals(
                        provider_id, previous_first, previous_last
                    ).values()
                )
            else:
                previous_values[source] = self._conversation_total(
                    provider_id,
                    provider_user_id,
                    previous_first,
                    previous_last,
                    timezone_name,
                    tracking_boundaries[source],
                )

        comparisons_are_covered = {
            source: previous_values[source] is not None
            for source in sources
        }
        metrics = {
            "profile_views": self._metric(
                value=values["profile_views"],
                definition=PROFILE_VIEW_DEFINITION,
                coverage=sources["profile_views"],
                previous_value=previous_values["profile_views"],
                comparison_coverage=comparisons_are_covered["profile_views"],
            ),
            "contact_clicks": self._metric(
                value=values["contact_clicks"],
                definition=CONTACT_CLICK_DEFINITION,
                coverage=sources["contact_clicks"],
                previous_value=previous_values["contact_clicks"],
                comparison_coverage=comparisons_are_covered["contact_clicks"],
            ),
            "new_conversations": self._metric(
                value=values["new_conversations"],
                definition=CONVERSATION_DEFINITION,
                coverage=sources["new_conversations"],
                previous_value=previous_values["new_conversations"],
                comparison_coverage=comparisons_are_covered["new_conversations"],
            ),
        }

        breakdown_totals = (
            self._click_totals(
                provider_id,
                current_firsts["contact_clicks"],
                last,
            )
            if current_firsts["contact_clicks"] is not None
            else {action: None for action in _ACTIONS}
        )

        average_rating, rating_count = self.review_repository.get_totals(provider_id)
        visible_review_count = self.review_repository.visible_review_count(provider_id)
        saved_count = int(
            self.db.scalar(
                select(func.count(ProviderFavorite.id)).where(
                    ProviderFavorite.provider_id == provider_id
                )
            )
            or 0
        )
        trend_profile_start = current_firsts["profile_views"]
        trend_click_start = current_firsts["contact_clicks"]
        profile_rows = {}
        if trend_profile_start is not None:
            profile_rows = dict(
                self.db.execute(
                    select(
                        TrafficProviderProfileDaily.visit_date,
                        func.sum(TrafficProviderProfileDaily.profile_views),
                    )
                    .where(
                        TrafficProviderProfileDaily.provider_id == provider_id,
                        TrafficProviderProfileDaily.visit_date >= trend_profile_start,
                        TrafficProviderProfileDaily.visit_date <= last,
                    )
                    .group_by(TrafficProviderProfileDaily.visit_date)
                ).all()
            )
        click_rows = {}
        if trend_click_start is not None:
            click_rows = dict(
                self.db.execute(
                    select(
                        ProviderContactClickDaily.click_date,
                        func.sum(ProviderContactClickDaily.click_count),
                    )
                    .where(
                        ProviderContactClickDaily.provider_id == provider_id,
                        ProviderContactClickDaily.click_date >= trend_click_start,
                        ProviderContactClickDaily.click_date <= last,
                    )
                    .group_by(ProviderContactClickDaily.click_date)
                ).all()
            )
        trends = [
            {
                "date": (first + timedelta(days=offset)).isoformat(),
                "profile_views": (
                    int(profile_rows.get(first + timedelta(days=offset), 0))
                    if trend_profile_start is not None
                    and first + timedelta(days=offset) >= trend_profile_start
                    else None
                ),
                "contact_clicks": (
                    int(click_rows.get(first + timedelta(days=offset), 0))
                    if trend_click_start is not None
                    and first + timedelta(days=offset) >= trend_click_start
                    else None
                ),
            }
            for offset in range(day_count)
        ]
        return {
            "provider_name": provider_name,
            "timezone": timezone_name,
            "today": today,
            "period": {
                "date_from": first.isoformat(),
                "date_to": last.isoformat(),
                "preset": preset,
            },
            "refreshed_at": datetime.now(timezone.utc),
            "metrics": metrics,
            "contact_breakdown": {
                action: breakdown_totals[action] for action in _ACTIONS
            },
            "snapshot": {
                "saved_members": saved_count,
                "rating_count": int(rating_count or 0),
                "visible_review_count": visible_review_count,
                "average_rating": (
                    round(float(average_rating), 2)
                    if average_rating is not None
                    else None
                ),
            },
            "trends": trends,
        }