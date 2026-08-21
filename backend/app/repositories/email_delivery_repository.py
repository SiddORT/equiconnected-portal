"""Data access for administrator-only transactional email delivery history."""
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose


SAFE_FAILURE_MESSAGES = {
    "SMTP_HOST is not configured; email was not sent.",
    "Unable to load the EquiConnected email logo.",
    "Unable to deliver email.",
    "SMTP server rejected the recipient.",
}


def safe_failure_message(error: BaseException | str) -> str:
    """Return a short allow-listed explanation suitable for administrator display."""
    message = str(error)
    return message if message in SAFE_FAILURE_MESSAGES else "Unable to deliver email."


class EmailDeliveryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def record(
        self,
        *,
        recipient_email: str,
        purpose: EmailPurpose | str,
        status: EmailDeliveryStatus | str,
        failure_message: str | None = None,
    ) -> EmailDeliveryLog:
        purpose_value = purpose.value if isinstance(purpose, EmailPurpose) else purpose
        status_value = status.value if isinstance(status, EmailDeliveryStatus) else status
        entry = EmailDeliveryLog(
            recipient_email=recipient_email,
            purpose=purpose_value,
            status=status_value,
            failure_message=(
                safe_failure_message(failure_message)
                if status_value == EmailDeliveryStatus.FAILED.value
                else None
            ),
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    def record_durable_attempt(
        self, *, recipient_email: str, purpose: EmailPurpose | str
    ) -> uuid.UUID:
        """Commit an attempt before SMTP handoff, outside the caller's transaction."""
        independent_session = sessionmaker(
            bind=self._db.get_bind(), autocommit=False, autoflush=False
        )()
        try:
            entry = EmailDeliveryRepository(independent_session).record(
                recipient_email=recipient_email,
                purpose=purpose,
                status=EmailDeliveryStatus.PENDING,
            )
            independent_session.commit()
            return entry.id
        except Exception:
            independent_session.rollback()
            raise
        finally:
            independent_session.close()

    def complete_durable_attempt(
        self,
        attempt_id: uuid.UUID,
        *,
        status: EmailDeliveryStatus,
        failure_message: str | None = None,
    ) -> None:
        """Persist the SMTP outcome without relying on the caller's transaction."""
        independent_session = sessionmaker(
            bind=self._db.get_bind(), autocommit=False, autoflush=False
        )()
        try:
            entry = independent_session.get(EmailDeliveryLog, attempt_id)
            if entry is None:
                raise ValueError("Email delivery attempt was not found.")
            entry.status = status.value
            entry.failure_message = (
                safe_failure_message(failure_message)
                if status == EmailDeliveryStatus.FAILED
                else None
            )
            independent_session.commit()
        except Exception:
            independent_session.rollback()
            raise
        finally:
            independent_session.close()

    @staticmethod
    def _bounds(
        *,
        filter_mode: str | None,
        filter_date: date | None,
        filter_month: int | None,
        filter_year: int | None,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[datetime | None, datetime | None, bool]:
        if not filter_mode:
            return None, None, False
        if filter_mode == "day":
            start = datetime.combine(filter_date, time.min, tzinfo=timezone.utc)
            if filter_date == date.max:
                return start, datetime.max.replace(tzinfo=timezone.utc), True
            return start, start + timedelta(days=1), False
        if filter_mode == "month":
            start_date = date(filter_year, filter_month, 1)
            if filter_year == date.max.year and filter_month == 12:
                return (
                    datetime.combine(start_date, time.min, tzinfo=timezone.utc),
                    datetime.max.replace(tzinfo=timezone.utc),
                    True,
                )
            next_month = (
                date(filter_year + 1, 1, 1)
                if filter_month == 12
                else date(filter_year, filter_month + 1, 1)
            )
            return (
                datetime.combine(start_date, time.min, tzinfo=timezone.utc),
                datetime.combine(next_month, time.min, tzinfo=timezone.utc),
                False,
            )
        if filter_mode == "year":
            start_date = date(filter_year, 1, 1)
            if filter_year == date.max.year:
                return (
                    datetime.combine(start_date, time.min, tzinfo=timezone.utc),
                    datetime.max.replace(tzinfo=timezone.utc),
                    True,
                )
            return (
                datetime.combine(start_date, time.min, tzinfo=timezone.utc),
                datetime.combine(date(filter_year + 1, 1, 1), time.min, tzinfo=timezone.utc),
                False,
            )
        inclusive_end = date_to == date.max
        return (
            datetime.combine(date_from, time.min, tzinfo=timezone.utc),
            (
                datetime.max.replace(tzinfo=timezone.utc)
                if inclusive_end
                else datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
            ),
            inclusive_end,
        )

    def list(
        self,
        *,
        filter_mode: str | None = None,
        filter_date: date | None = None,
        filter_month: int | None = None,
        filter_year: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[EmailDeliveryLog], int]:
        start, end, inclusive_end = self._bounds(
            filter_mode=filter_mode,
            filter_date=filter_date,
            filter_month=filter_month,
            filter_year=filter_year,
            date_from=date_from,
            date_to=date_to,
        )
        filters: list[Any] = []
        if start is not None:
            filters.append(EmailDeliveryLog.created_at >= start)
        if end is not None:
            filters.append(
                EmailDeliveryLog.created_at <= end
                if inclusive_end
                else EmailDeliveryLog.created_at < end
            )
        total = self._db.scalar(
            select(func.count()).select_from(EmailDeliveryLog).where(*filters)
        ) or 0
        rows = self._db.scalars(
            select(EmailDeliveryLog)
            .where(*filters)
            .order_by(EmailDeliveryLog.created_at.desc(), EmailDeliveryLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total