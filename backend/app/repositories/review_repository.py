"""Database reads and writes for provider-directory reviews."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Float, case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ProviderStatus, ProviderType, PublicationStatus
from app.models.provider import Provider, ProviderLocation, ProviderReview
from app.models.user import User


class ReviewRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _rating_totals():
        return (
            select(
                ProviderReview.provider_id.label("provider_id"),
                func.avg(ProviderReview.rating).cast(Float).label("average_rating"),
                func.count(ProviderReview.id).label("review_count"),
            )
            .group_by(ProviderReview.provider_id)
            .subquery()
        )

    @staticmethod
    def _coordinate_subqueries():
        location_conditions = (
            ProviderLocation.provider_id == Provider.id,
            ProviderLocation.latitude.is_not(None),
            ProviderLocation.longitude.is_not(None),
        )
        latitude = (
            select(ProviderLocation.latitude)
            .where(*location_conditions)
            .order_by(ProviderLocation.is_primary.desc(), ProviderLocation.id)
            .limit(1)
            .scalar_subquery()
        )
        longitude = (
            select(ProviderLocation.longitude)
            .where(*location_conditions)
            .order_by(ProviderLocation.is_primary.desc(), ProviderLocation.id)
            .limit(1)
            .scalar_subquery()
        )
        return latitude, longitude

    def list_discoverable(
        self,
        *,
        provider_type: ProviderType | None,
        minimum_rating: float | None,
        page: int,
        page_size: int,
        latitude: float | None,
        longitude: float | None,
    ) -> tuple[list[Any], int]:
        totals = self._rating_totals()
        conditions = [
            Provider.status == ProviderStatus.ACTIVE,
            Provider.publication_status == PublicationStatus.PUBLISHED,
        ]
        if provider_type is not None:
            conditions.append(Provider.provider_type == provider_type)
        if minimum_rating is not None:
            conditions.append(totals.c.average_rating >= minimum_rating)

        count_stmt = (
            select(func.count())
            .select_from(Provider)
            .outerjoin(totals, totals.c.provider_id == Provider.id)
            .where(*conditions)
        )
        total = self._db.scalar(count_stmt) or 0

        distance = None
        if latitude is not None and longitude is not None:
            provider_latitude, provider_longitude = self._coordinate_subqueries()
            haversine = (
                6371.0088
                * 2
                * func.asin(
                    func.sqrt(
                        func.power(func.sin(func.radians(provider_latitude - latitude) / 2), 2)
                        + func.cos(func.radians(latitude))
                        * func.cos(func.radians(provider_latitude))
                        * func.power(func.sin(func.radians(provider_longitude - longitude) / 2), 2)
                    )
                )
            )
            distance = case(
                (
                    provider_latitude.is_not(None) & provider_longitude.is_not(None),
                    haversine,
                ),
                else_=None,
            ).label("distance_km")

        columns = [
            Provider,
            totals.c.average_rating,
            func.coalesce(totals.c.review_count, 0).label("review_count"),
        ]
        if distance is not None:
            columns.append(distance)
        stmt = (
            select(*columns)
            .outerjoin(totals, totals.c.provider_id == Provider.id)
            .where(*conditions)
            .options(
                selectinload(Provider.locations),
                selectinload(Provider.photos),
                selectinload(Provider.phones),
                selectinload(Provider.emails),
            )
        )
        if distance is not None:
            stmt = stmt.order_by(
                distance.asc().nulls_last(),
                totals.c.average_rating.desc().nulls_last(),
                Provider.name,
                Provider.id,
            )
        else:
            stmt = stmt.order_by(
                totals.c.average_rating.desc().nulls_last(), Provider.name, Provider.id
            )
        rows = self._db.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        ).unique().all()
        return rows, total

    def get_discoverable(self, provider_id: UUID) -> Provider | None:
        return self._db.scalar(
            select(Provider)
            .where(
                Provider.id == provider_id,
                Provider.status == ProviderStatus.ACTIVE,
                Provider.publication_status == PublicationStatus.PUBLISHED,
            )
            .options(
                selectinload(Provider.locations),
                selectinload(Provider.photos),
                selectinload(Provider.phones),
                selectinload(Provider.emails),
            )
        )

    def get_totals(self, provider_id: UUID) -> tuple[float | None, int]:
        average, count = self._db.execute(
            select(
                func.avg(ProviderReview.rating).cast(Float),
                func.count(ProviderReview.id),
            ).where(ProviderReview.provider_id == provider_id)
        ).one()
        return average, count

    def list_visible_reviews(self, provider_id: UUID) -> list[tuple[ProviderReview, User]]:
        return list(
            self._db.execute(
                select(ProviderReview, User)
                .join(User, User.id == ProviderReview.member_id)
                .where(
                    ProviderReview.provider_id == provider_id,
                    ProviderReview.comment_visible.is_(True),
                    ProviderReview.comment != "",
                )
                .order_by(ProviderReview.created_at.desc(), ProviderReview.id)
            ).all()
        )

    def get_member_review(
        self, provider_id: UUID, member_id: UUID
    ) -> ProviderReview | None:
        return self._db.scalar(
            select(ProviderReview).where(
                ProviderReview.provider_id == provider_id,
                ProviderReview.member_id == member_id,
            )
        )

    def save_member_review(
        self, provider_id: UUID, member_id: UUID, *, rating: int, comment: str
    ) -> tuple[ProviderReview, bool]:
        # A read-then-insert leaves simultaneous first submissions vulnerable to
        # a unique-constraint race. PostgreSQL's atomic upsert preserves the
        # one-review rule while retaining PUT's idempotent behavior.
        existing = self.get_member_review(provider_id, member_id)
        now = datetime.now(timezone.utc)
        statement = insert(ProviderReview).values(
            provider_id=provider_id,
            member_id=member_id,
            rating=rating,
            comment=comment,
            comment_visible=True,
            created_at=now,
            updated_at=now,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[ProviderReview.provider_id, ProviderReview.member_id],
            set_={
                "rating": statement.excluded.rating,
                "comment": statement.excluded.comment,
                # Moderation state intentionally survives a member edit.
                "updated_at": now,
            },
        ).returning(ProviderReview.id)
        review_id = self._db.scalar(statement)
        review = self._db.get(ProviderReview, review_id)
        assert review is not None
        return review, existing is None

    def get_review(self, review_id: UUID) -> ProviderReview | None:
        return self._db.scalar(
            select(ProviderReview)
            .where(ProviderReview.id == review_id)
            .options(selectinload(ProviderReview.provider), selectinload(ProviderReview.member))
        )

    def list_admin_reviews(
        self,
        *,
        provider_id: UUID | None,
        comment_visible: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[ProviderReview, Provider, User]], int]:
        conditions = []
        if provider_id is not None:
            conditions.append(ProviderReview.provider_id == provider_id)
        if comment_visible is not None:
            conditions.append(ProviderReview.comment_visible == comment_visible)
        total = self._db.scalar(
            select(func.count()).select_from(ProviderReview).where(*conditions)
        ) or 0
        items = list(
            self._db.execute(
                select(ProviderReview, Provider, User)
                .join(Provider, Provider.id == ProviderReview.provider_id)
                .join(User, User.id == ProviderReview.member_id)
                .where(*conditions)
                .order_by(ProviderReview.created_at.desc(), ProviderReview.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
