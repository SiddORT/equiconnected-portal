"""Shared system-calendar month bounds for visiting-provider feeds."""
from datetime import date, timedelta
import re

from fastapi import HTTPException


def visiting_calendar_month_range(
    month: str | None, today: date
) -> tuple[str, date, date]:
    """Return the normalized month and inclusive first/last dates."""
    if month is None:
        first = today.replace(day=1)
    else:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise HTTPException(status_code=422, detail="Month must be YYYY-MM.")
        try:
            first = date(int(month[:4]), int(month[5:]), 1)
        except ValueError:
            raise HTTPException(status_code=422, detail="Month must be YYYY-MM.") from None

    if first.year == 9999 and first.month == 12:
        last = date.max
    else:
        next_month = date(
            first.year + (first.month == 12),
            first.month % 12 + 1,
            1,
        )
        last = next_month - timedelta(days=1)

    return f"{first.year:04d}-{first.month:02d}", first, last