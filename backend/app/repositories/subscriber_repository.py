"""Database access for public subscribers."""
from __future__ import annotations

from datetime import date
from typing import Any, Iterator

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time_standards import local_date_bounds
from app.models.enums import SubscriberRegistrationType
from app.models.subscriber import Subscriber
from app.repositories import matches_like_substring, page_filtered_candidates


class SubscriberRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_email(self, email: str) -> Subscriber | None:
        return self._db.scalar(
            select(Subscriber).where(Subscriber.email == email)
        )

    def create_or_get(
        self, *, email: str, registration_type: SubscriberRegistrationType
    ) -> tuple[Subscriber, bool]:
        """Commit the identity before SMTP so delivery cannot roll it back."""
        existing = self.get_by_email(email)
        if existing is not None:
            return existing, False

        subscriber = Subscriber(email=email, registration_type=registration_type.value)
        self._db.add(subscriber)
        try:
            self._db.commit()
            return subscriber, True
        except IntegrityError:
            # A concurrent request won the unique-email race.
            self._db.rollback()
            existing = self.get_by_email(email)
            if existing is None:
                raise
            return existing, False

    def list(
        self,
        *,
        search: str | None = None,
        registration_type: SubscriberRegistrationType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        timezone_name: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Subscriber], int]:
        filters = self._filters(
            registration_type=registration_type,
            date_from=date_from,
            date_to=date_to,
            timezone_name=timezone_name,
        )
        search_term = search.strip().lower() if search else ""
        if search_term:
            return page_filtered_candidates(
                self._db.scalars(
                    self._ordered_query(filters).execution_options(yield_per=250)
                ),
                lambda subscriber: matches_like_substring(subscriber.email, search_term),
                page=page,
                page_size=page_size,
            )
        total = self._db.scalar(
            select(func.count()).select_from(Subscriber).where(*filters)
        ) or 0
        rows = self._db.scalars(
            self._ordered_query(filters)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total

    def list_all(
        self,
        *,
        search: str | None = None,
        registration_type: SubscriberRegistrationType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        timezone_name: str | None = None,
    ) -> list[Subscriber]:
        """Return every matching subscriber in the directory's stable order."""
        return list(self.iter_all(
            search=search,
            registration_type=registration_type,
            date_from=date_from,
            date_to=date_to,
            timezone_name=timezone_name,
        ))

    def iter_all(
        self,
        *,
        search: str | None = None,
        registration_type: SubscriberRegistrationType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        timezone_name: str | None = None,
    ) -> Iterator[Subscriber]:
        """Yield every matching subscriber in stable order with bounded memory."""
        filters = self._filters(
            registration_type=registration_type,
            date_from=date_from,
            date_to=date_to,
            timezone_name=timezone_name,
        )
        search_term = search.strip().lower() if search else ""
        candidates = self._db.scalars(
            self._ordered_query(filters).execution_options(yield_per=250)
        )
        try:
            if search_term:
                for subscriber in candidates:
                    if matches_like_substring(subscriber.email, search_term):
                        yield subscriber
            else:
                yield from candidates
        finally:
            candidates.close()

    def _filters(
        self,
        *,
        registration_type: SubscriberRegistrationType | None,
        date_from: date | None,
        date_to: date | None,
        timezone_name: str | None,
    ) -> list[Any]:
        filters: list[Any] = []
        if registration_type is not None:
            filters.append(Subscriber.registration_type == registration_type.value)
        start, end = local_date_bounds(date_from, date_to, timezone_name)
        if start is not None:
            filters.append(Subscriber.submitted_at >= start)
        if end is not None:
            filters.append(Subscriber.submitted_at < end)
        return filters

    @staticmethod
    def _ordered_query(filters: list[Any]):
        return (
            select(Subscriber)
            .where(*filters)
            .order_by(Subscriber.submitted_at.desc(), Subscriber.id.desc())
        )