"""Database access for public subscribers."""
from typing import Any
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import SubscriberRegistrationType
from app.models.subscriber import Subscriber


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
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Subscriber], int]:
        filters: list[Any] = []
        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            filters.append(func.lower(Subscriber.email).like(pattern))
        if registration_type is not None:
            filters.append(Subscriber.registration_type == registration_type.value)

        total = self._db.scalar(
            select(func.count()).select_from(Subscriber).where(*filters)
        ) or 0
        rows = self._db.scalars(
            select(Subscriber)
            .where(*filters)
            .order_by(Subscriber.submitted_at.desc(), Subscriber.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total