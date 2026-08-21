"""UTC storage and system-timezone calendar helpers."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.system_settings import DEFAULT_TIMEZONE


UTC = timezone.utc


def resolve_timezone(timezone_name: str | None) -> ZoneInfo:
    """Return a valid IANA zone, falling back safely for a missing legacy row."""
    try:
        return ZoneInfo(timezone_name or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def system_today(timezone_name: str | None, now: datetime | None = None) -> date:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(resolve_timezone(timezone_name)).date()


def local_midnight_utc(calendar_day: date, timezone_name: str | None) -> datetime:
    """Convert the start of a system-local day to UTC, respecting DST changes."""
    return datetime.combine(
        calendar_day,
        time.min,
        tzinfo=resolve_timezone(timezone_name),
    ).astimezone(UTC)


def local_date_bounds(
    date_from: date | None,
    date_to: date | None,
    timezone_name: str | None,
) -> tuple[datetime | None, datetime | None]:
    """
    Return a UTC [start, end) interval for inclusive system-calendar dates.

    The endpoint is the next local midnight rather than 23:59:59.999 so it is
    precise in PostgreSQL and covers shortened/lengthened daylight-saving days.
    """
    start = local_midnight_utc(date_from, timezone_name) if date_from else None
    if date_to is None:
        return start, None
    if date_to == date.max:
        return start, datetime.max.replace(tzinfo=UTC)
    return start, local_midnight_utc(date_to + timedelta(days=1), timezone_name)


def local_month_bounds(
    year: int,
    month: int,
    timezone_name: str | None,
) -> tuple[datetime, datetime]:
    start_date = date(year, month, 1)
    if year == date.max.year and month == 12:
        return local_midnight_utc(start_date, timezone_name), datetime.max.replace(tzinfo=UTC)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return (
        local_midnight_utc(start_date, timezone_name),
        local_midnight_utc(next_month, timezone_name),
    )


def local_year_bounds(year: int, timezone_name: str | None) -> tuple[datetime, datetime]:
    if year == date.max.year:
        return (
            local_midnight_utc(date(year, 1, 1), timezone_name),
            datetime.max.replace(tzinfo=UTC),
        )
    return (
        local_midnight_utc(date(year, 1, 1), timezone_name),
        local_midnight_utc(date(year + 1, 1, 1), timezone_name),
    )