"""Database reads and writes for provider-directory reviews."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Float, case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models.enums import (
    ProviderReviewStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.language import ProviderLanguage
from app.models.provider import Provider, ProviderLocation, ProviderReview, ProviderSpecialization
from app.models.provider_favorite import ProviderFavorite
from app.models.provider_review_action import ProviderReviewAction
from app.models.specialization import Specialization
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
            .where(
                ProviderReview.deleted_at.is_(None),
                ProviderReview.status.in_(
                    [ProviderReviewStatus.PUBLISHED, ProviderReviewStatus.HIDDEN]
                ),
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
            ProviderLocation.latitude.between(-90, 90),
            ProviderLocation.longitude.between(-180, 180),
        )
        latitude = (
            select(ProviderLocation.latitude)
            .where(*location_conditions)
            .order_by(
                ProviderLocation.is_primary.desc(),
                ProviderLocation.created_at,
                ProviderLocation.id,
            )
            .limit(1)
            .scalar_subquery()
        )
        longitude = (
            select(ProviderLocation.longitude)
            .where(*location_conditions)
            .order_by(
                ProviderLocation.is_primary.desc(),
                ProviderLocation.created_at,
                ProviderLocation.id,
            )
            .limit(1)
            .scalar_subquery()
        )
        return latitude, longitude

    def list_discoverable(
        self,
        *,
        name: str | None = None,
        provider_type: ProviderType | None,
        minimum_rating: float | None,
        page: int,
        page_size: int,
        latitude: float | None,
        longitude: float | None,
        closest_first: bool = False,
        within_working_radius: bool = False,
        visit_stability: VisitStability | None = None,
        specialization_id: UUID | None = None,
        region: str | None = None,
        emergency_only: bool = False,
        sort: str = "relevance",
        saved_only_member_id: UUID | None = None,
    ) -> tuple[list[Any], int]:
        totals = self._rating_totals()
        conditions = [
            Provider.status == ProviderStatus.ACTIVE,
            Provider.publication_status == PublicationStatus.PUBLISHED,
        ]
        if name and (term := name.strip()):
            # Treat wildcard characters as literal name characters.
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(Provider.name.ilike(f"%{escaped}%", escape="\\"))
        if saved_only_member_id is not None:
            conditions.append(
                select(ProviderFavorite.id).where(
                    ProviderFavorite.provider_id == Provider.id,
                    ProviderFavorite.member_id == saved_only_member_id,
                ).exists()
            )
        if provider_type is not None:
            conditions.append(Provider.provider_type == provider_type)
        if minimum_rating is not None:
            conditions.append(totals.c.average_rating >= minimum_rating)
        if visit_stability is not None:
            conditions.append(Provider.visit_stability == visit_stability)
        if emergency_only:
            conditions.append(Provider.emergency_services_available.is_(True))
        if specialization_id is not None:
            conditions.append(
                select(ProviderSpecialization.provider_id).where(
                    ProviderSpecialization.provider_id == Provider.id,
                    ProviderSpecialization.specialization_id == specialization_id,
                ).exists()
            )
        if region is not None:
            conditions.append(
                select(ProviderLocation.id).where(
                    ProviderLocation.provider_id == Provider.id,
                    func.lower(ProviderLocation.state_province) == region.lower(),
                ).exists()
            )

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
            if within_working_radius:
                # A working-radius match is meaningful only for stable-visit
                # providers with a configured radius.  Apply this predicate
                # to both count and item statements so pagination is accurate.
                conditions.extend(
                    [
                        Provider.visit_stability == VisitStability.STABLE_VISIT,
                        Provider.maximum_working_radius_km.is_not(None),
                        Provider.maximum_working_radius_km > 0,
                        Provider.maximum_working_radius_km >= distance,
                    ]
                )

        count_stmt = (
            select(func.count())
            .select_from(Provider)
            .outerjoin(totals, totals.c.provider_id == Provider.id)
            .where(*conditions)
        )
        total = self._db.scalar(count_stmt) or 0

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
                selectinload(Provider.provider_specializations).selectinload(
                    ProviderSpecialization.specialization
                ),
            )
        )
        if distance is not None and closest_first:
            stmt = stmt.order_by(
                distance.asc().nulls_last(),
                totals.c.average_rating.desc().nulls_last(),
                Provider.name,
                Provider.id,
            )
        elif sort == "name":
            stmt = stmt.order_by(Provider.name, Provider.id)
        else:
            stmt = stmt.order_by(
                totals.c.average_rating.desc().nulls_last(), Provider.name, Provider.id
            )
        rows = self._db.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        ).unique().all()
        return rows, total

    def directory_facets(self) -> dict:
        visible = (
            Provider.status == ProviderStatus.ACTIVE,
            Provider.publication_status == PublicationStatus.PUBLISHED,
        )
        specs = self._db.execute(
            select(Specialization.id, Specialization.name)
            .join(ProviderSpecialization, ProviderSpecialization.specialization_id == Specialization.id)
            .join(Provider, Provider.id == ProviderSpecialization.provider_id)
            .where(*visible)
            .distinct().order_by(Specialization.name)
        ).all()
        regions = self._db.scalars(
            select(ProviderLocation.state_province)
            .join(Provider, Provider.id == ProviderLocation.provider_id)
            .where(*visible, ProviderLocation.state_province.is_not(None))
            .distinct().order_by(ProviderLocation.state_province)
        ).all()
        return {
            "specializations": [{"id": str(id), "name": name} for id, name in specs],
            "regions": [name for name in regions if name],
        }

    def list_public_discoverable(
        self,
        *,
        provider_type: ProviderType | None,
        latitude: float | None,
        longitude: float | None,
        limit: int,
    ) -> list[Any]:
        """Return a bounded, coordinate-backed provider set for public discovery."""
        totals = self._rating_totals()
        provider_latitude, provider_longitude = self._coordinate_subqueries()
        conditions = [
            Provider.status == ProviderStatus.ACTIVE,
            Provider.publication_status == PublicationStatus.PUBLISHED,
            provider_latitude.is_not(None),
            provider_longitude.is_not(None),
        ]
        if provider_type is not None:
            conditions.append(Provider.provider_type == provider_type)

        distance = None
        if latitude is not None and longitude is not None:
            haversine = (
                6371.0088
                * 2
                * func.asin(
                    func.sqrt(
                        func.power(func.sin(func.radians(provider_latitude - latitude) / 2), 2)
                        + func.cos(func.radians(latitude))
                        * func.cos(func.radians(provider_latitude))
                        * func.power(
                            func.sin(func.radians(provider_longitude - longitude) / 2), 2
                        )
                    )
                )
            )
            distance = haversine.label("distance_km")

        columns = [
            Provider,
            totals.c.average_rating,
            func.coalesce(totals.c.review_count, 0).label("review_count"),
            provider_latitude.label("latitude"),
            provider_longitude.label("longitude"),
            distance if distance is not None else func.cast(None, Float).label("distance_km"),
        ]
        stmt = (
            select(*columns)
            .outerjoin(totals, totals.c.provider_id == Provider.id)
            .where(*conditions)
            .options(
                selectinload(Provider.locations),
                selectinload(Provider.photos),
                selectinload(Provider.provider_specializations).selectinload(
                    ProviderSpecialization.specialization
                ),
            )
        )
        if distance is not None:
            stmt = stmt.order_by(
                distance.asc(),
                totals.c.average_rating.desc().nulls_last(),
                Provider.name,
                Provider.id,
            )
        else:
            stmt = stmt.order_by(
                totals.c.average_rating.desc().nulls_last(), Provider.name, Provider.id
            )
        return self._db.execute(stmt.limit(limit)).unique().all()

    def get_discoverable(self, provider_id: UUID, *, include_profile: bool = False) -> Provider | None:
        stmt = (
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
                selectinload(Provider.provider_specializations).selectinload(
                    ProviderSpecialization.specialization
                ),
            )
        )
        if include_profile:
            stmt = stmt.options(
                selectinload(Provider.doctor_profile),
                selectinload(Provider.qualifications),
                selectinload(Provider.provider_languages).selectinload(ProviderLanguage.language),
                selectinload(Provider.doctor_visits),
            )
        return self._db.scalar(stmt)

    def get_totals(self, provider_id: UUID) -> tuple[float | None, int]:
        average, count = self._db.execute(
            select(
                func.avg(ProviderReview.rating).cast(Float),
                func.count(ProviderReview.id),
            ).where(
                ProviderReview.provider_id == provider_id,
                ProviderReview.deleted_at.is_(None),
                ProviderReview.status.in_(
                    [ProviderReviewStatus.PUBLISHED, ProviderReviewStatus.HIDDEN]
                ),
            )
        ).one()
        return average, count

    def list_visible_reviews(self, provider_id: UUID) -> list[tuple[ProviderReview, User]]:
        return list(
            self._db.execute(
                select(ProviderReview, User)
                .join(User, User.id == ProviderReview.member_id)
                .where(*self._visible_review_conditions(provider_id))
                .order_by(ProviderReview.created_at.desc(), ProviderReview.id)
            ).all()
        )

    @staticmethod
    def _visible_review_conditions(provider_id: UUID):
        """Single moderation predicate shared by public reviews and snapshots."""
        return (
            ProviderReview.provider_id == provider_id,
            ProviderReview.deleted_at.is_(None),
            ProviderReview.status == ProviderReviewStatus.PUBLISHED,
            ProviderReview.comment_visible.is_(True),
            ProviderReview.comment != "",
        )

    def visible_review_count(self, provider_id: UUID) -> int:
        return int(
            self._db.scalar(
                select(func.count(ProviderReview.id)).where(
                    *self._visible_review_conditions(provider_id)
                )
            )
            or 0
        )

    def get_member_review(
        self, provider_id: UUID, member_id: UUID
    ) -> ProviderReview | None:
        return self._db.scalar(
            select(ProviderReview).where(
                ProviderReview.provider_id == provider_id,
                ProviderReview.member_id == member_id,
                ProviderReview.deleted_at.is_(None),
            )
        )

    def save_member_review(
        self,
        provider_id: UUID,
        member_id: UUID,
        *,
        rating: int,
        comment: str,
        expected_version: int | None,
    ) -> tuple[ProviderReview | None, bool]:
        existing = self.get_member_review(provider_id, member_id)
        now = datetime.now(timezone.utc)
        if existing is not None:
            if expected_version is None:
                if existing.rating == rating and existing.comment == comment:
                    return existing, False
                return None, False
            return self.update_member_review(
                existing.id,
                member_id,
                rating=rating,
                comment=comment,
                expected_version=expected_version,
            ), False

        # A version identifies an edit, never a first submission. A deleted
        # target must not be recreated by a stale edit.
        if expected_version is not None:
            return None, False

        statement = insert(ProviderReview).values(
            provider_id=provider_id,
            member_id=member_id,
            rating=rating,
            comment=comment,
            comment_visible=True,
            status=ProviderReviewStatus.PENDING,
            version=1,
            created_at=now,
            updated_at=now,
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=[ProviderReview.provider_id, ProviderReview.member_id],
            index_where=ProviderReview.deleted_at.is_(None),
        ).returning(ProviderReview.id, ProviderReview.version)
        inserted = self._db.execute(statement).one_or_none()
        review_id = inserted[0] if inserted else None
        if review_id is None:
            # Concurrent first submissions are idempotent only when service
            # validation confirms that the payload matches this exact retry.
            # Crucially, this does not overwrite an admin's moderation update.
            existing = self.get_member_review(provider_id, member_id)
            return existing, False
        self._db.flush()
        return self.get_review(review_id), inserted[1] == 1

    def update_member_review(
        self,
        review_id: UUID,
        member_id: UUID,
        *,
        rating: int,
        comment: str,
        expected_version: int,
    ) -> ProviderReview | None:
        changed = self._db.execute(
            update(ProviderReview)
            .where(
                ProviderReview.id == review_id,
                ProviderReview.member_id == member_id,
                ProviderReview.version == expected_version,
                ProviderReview.status != ProviderReviewStatus.HIDDEN,
                ProviderReview.deleted_at.is_(None),
            )
            .values(
                rating=rating,
                comment=comment,
                status=ProviderReviewStatus.PENDING,
                comment_visible=True,
                member_note=None,
                version=ProviderReview.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(ProviderReview.id)
        ).scalar_one_or_none()
        if changed is None:
            return None
        self._db.flush()
        return self.get_review(changed)

    def get_review(self, review_id: UUID) -> ProviderReview | None:
        return self._db.scalar(
            select(ProviderReview)
            .where(ProviderReview.id == review_id)
            .execution_options(populate_existing=True)
            .options(selectinload(ProviderReview.provider), selectinload(ProviderReview.member))
        )

    def list_member_reviews(
        self, member_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[tuple[ProviderReview, Provider]], int]:
        conditions = [
            ProviderReview.member_id == member_id,
            ProviderReview.deleted_at.is_(None),
        ]
        total = self._db.scalar(
            select(func.count()).select_from(ProviderReview).where(*conditions)
        ) or 0
        rows = self._db.execute(
            select(ProviderReview, Provider)
            .join(Provider, Provider.id == ProviderReview.provider_id)
            .where(*conditions)
            .order_by(ProviderReview.updated_at.desc(), ProviderReview.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total

    def member_review_counts(self, member_id: UUID) -> dict[str, int]:
        rows = self._db.execute(
            select(ProviderReview.status, func.count(ProviderReview.id))
            .where(
                ProviderReview.member_id == member_id,
                ProviderReview.deleted_at.is_(None),
            )
            .group_by(ProviderReview.status)
        ).all()
        counts = {status.value.lower(): int(count) for status, count in rows}
        counts["all"] = sum(counts.values())
        return counts

    def delete_member_review(
        self, review_id: UUID, member_id: UUID, expected_version: int
    ) -> ProviderReview | None:
        review = self._db.scalar(
            select(ProviderReview).where(
                ProviderReview.id == review_id,
                ProviderReview.member_id == member_id,
                ProviderReview.deleted_at.is_(None),
                ProviderReview.version == expected_version,
            )
        )
        if review is None:
            return None
        now = datetime.now(timezone.utc)
        changed = self._db.execute(
            update(ProviderReview)
            .where(
                ProviderReview.id == review_id,
                ProviderReview.member_id == member_id,
                ProviderReview.deleted_at.is_(None),
                ProviderReview.version == expected_version,
            )
            .values(deleted_at=now, version=ProviderReview.version + 1, updated_at=now)
            .returning(ProviderReview.id)
        ).scalar_one_or_none()
        if changed is None:
            return None
        self._db.flush()
        return self.get_review(review_id)

    def set_review_status(
        self,
        review_id: UUID,
        *,
        expected_version: int,
        new_status: ProviderReviewStatus,
        member_note: str | None = None,
        internal_note: str | None = None,
        update_member_note: bool = False,
        update_internal_note: bool = False,
    ) -> ProviderReview | None:
        review = self.get_review(review_id)
        if (
            review is None
            or review.deleted_at is not None
            or review.version != expected_version
            or not self._valid_status_transition(review.status, new_status)
        ):
            return None
        now = datetime.now(timezone.utc)
        values = {
            "status": new_status,
            "comment_visible": new_status != ProviderReviewStatus.HIDDEN,
            "version": ProviderReview.version + 1,
            "updated_at": now,
        }
        if update_member_note:
            values["member_note"] = member_note
        if update_internal_note:
            values["internal_note"] = internal_note
        changed_id = self._db.execute(
            update(ProviderReview)
            .where(
                ProviderReview.id == review_id,
                ProviderReview.version == expected_version,
                ProviderReview.deleted_at.is_(None),
            )
            .values(**values)
            .returning(ProviderReview.id)
        ).scalar_one_or_none()
        if changed_id is None:
            return None
        self._db.flush()
        return self.get_review(changed_id)

    @staticmethod
    def _valid_status_transition(
        old: ProviderReviewStatus, new: ProviderReviewStatus
    ) -> bool:
        valid = {
            ProviderReviewStatus.PENDING: {
                ProviderReviewStatus.PENDING,
                ProviderReviewStatus.PUBLISHED,
                ProviderReviewStatus.REJECTED,
            },
            ProviderReviewStatus.PUBLISHED: {
                ProviderReviewStatus.PUBLISHED,
                ProviderReviewStatus.REJECTED,
                ProviderReviewStatus.HIDDEN,
            },
            ProviderReviewStatus.REJECTED: {
                ProviderReviewStatus.REJECTED,
                ProviderReviewStatus.PUBLISHED,
            },
            ProviderReviewStatus.HIDDEN: {
                ProviderReviewStatus.HIDDEN,
                ProviderReviewStatus.PUBLISHED,
            },
        }
        return new in valid[old]

    def record_action(
        self,
        *,
        review_id: UUID,
        actor_id: UUID | None,
        action: str,
        from_status: ProviderReviewStatus | None,
        to_status: ProviderReviewStatus | None,
        version: int,
        actor_type: str,
    ) -> ProviderReviewAction:
        actor = self._db.get(User, actor_id) if actor_id is not None else None
        review = self.get_review(review_id)
        if review is None:
            raise ValueError("Cannot snapshot a missing provider review.")
        actor_name = "Unavailable account"
        if actor:
            actor_name = " ".join(
                part.strip()
                for part in (actor.first_name, actor.last_name)
                if part and part.strip()
            )[:200] or "Account holder"
        entry = ProviderReviewAction(
            review_id=review_id,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_email=actor.email[:254] if actor else "",
            actor_type=actor_type,
            action=action,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value if to_status else None,
            version=version,
            content_snapshot={
                "rating": review.rating,
                "comment": review.comment,
                "status": review.status.value,
                "comment_visible": review.comment_visible,
                "member_note": review.member_note,
                "internal_note": review.internal_note,
                "deleted_at": review.deleted_at.isoformat() if review.deleted_at else None,
            },
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    def list_review_actions(self, review_id: UUID):
        return list(
            self._db.execute(
                select(ProviderReviewAction)
                .options(selectinload(ProviderReviewAction.actor))
                .where(ProviderReviewAction.review_id == review_id)
                .order_by(ProviderReviewAction.created_at, ProviderReviewAction.id)
            ).scalars().all()
        )

    def list_admin_reviews(
        self,
        *,
        provider_id: UUID | None,
        comment_visible: bool | None,
        review_status: ProviderReviewStatus | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[ProviderReview, Provider, User]], int]:
        conditions = []
        if provider_id is not None:
            conditions.append(ProviderReview.provider_id == provider_id)
        if comment_visible is not None:
            conditions.append(ProviderReview.comment_visible == comment_visible)
        if review_status is not None:
            conditions.append(ProviderReview.status == review_status)
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
