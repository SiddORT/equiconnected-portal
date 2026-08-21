"""Data access for administrator-only transactional email delivery history."""
from datetime import date, datetime
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.core.time_standards import (
    local_date_bounds,
    local_month_bounds,
    local_year_bounds,
)


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
        timezone_name: str | None = None,
    ) -> tuple[datetime | None, datetime | None]:
        if not filter_mode:
            return None, None
        if filter_mode == "day":
            return local_date_bounds(filter_date, filter_date, timezone_name)
        if filter_mode == "month":
            return local_month_bounds(filter_year, filter_month, timezone_name)
        if filter_mode == "year":
            return local_year_bounds(filter_year, timezone_name)
        return local_date_bounds(date_from, date_to, timezone_name)

    def list(
        self,
        *,
        filter_mode: str | None = None,
        filter_date: date | None = None,
        filter_month: int | None = None,
        filter_year: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        timezone_name: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[EmailDeliveryLog], int]:
        start, end = self._bounds(
            filter_mode=filter_mode,
            filter_date=filter_date,
            filter_month=filter_month,
            filter_year=filter_year,
            date_from=date_from,
            date_to=date_to,
            timezone_name=timezone_name,
        )
        filters: list[Any] = []
        if start is not None:
            filters.append(EmailDeliveryLog.created_at >= start)
        if end is not None:
            filters.append(EmailDeliveryLog.created_at < end)
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