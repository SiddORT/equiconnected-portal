"""Persistence helpers for provider-owned profile update requests."""
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import ProviderProfileUpdateStatus
from app.models.provider import Provider, ProviderProfileUpdate


class ProviderProfileUpdateRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_provider(self, provider_id: UUID) -> ProviderProfileUpdate | None:
        return self._db.scalar(
            select(ProviderProfileUpdate)
            .options(joinedload(ProviderProfileUpdate.reviewer))
            .where(ProviderProfileUpdate.provider_id == provider_id)
        )

    def get_for_update(self, update_id: UUID) -> ProviderProfileUpdate | None:
        return self._db.scalar(
            select(ProviderProfileUpdate)
            .options(joinedload(ProviderProfileUpdate.provider))
            .where(ProviderProfileUpdate.id == update_id)
            .with_for_update(of=ProviderProfileUpdate)
        )

    def get(self, update_id: UUID) -> ProviderProfileUpdate | None:
        return self._db.scalar(
            select(ProviderProfileUpdate)
            .options(
                joinedload(ProviderProfileUpdate.provider),
                joinedload(ProviderProfileUpdate.reviewer),
            )
            .where(ProviderProfileUpdate.id == update_id)
        )

    def get_for_provider_for_update(self, provider_id: UUID) -> ProviderProfileUpdate | None:
        return self._db.scalar(
            select(ProviderProfileUpdate)
            .where(ProviderProfileUpdate.provider_id == provider_id)
            .with_for_update(of=ProviderProfileUpdate)
        )

    def create(self, **fields) -> ProviderProfileUpdate:
        update = ProviderProfileUpdate(**fields)
        self._db.add(update)
        self._db.flush()
        return update

    def list(
        self,
        *,
        search: str | None = None,
        review_status: ProviderProfileUpdateStatus | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[ProviderProfileUpdate], int]:
        conditions = []
        if search:
            conditions.append(Provider.name.ilike(f"%{search.strip()}%"))
        if review_status is not None:
            conditions.append(ProviderProfileUpdate.review_status == review_status)
        total = self._db.scalar(
            select(func.count()).select_from(ProviderProfileUpdate).join(Provider).where(*conditions)
        ) or 0
        rows = self._db.scalars(
            select(ProviderProfileUpdate)
            .join(Provider)
            .options(
                joinedload(ProviderProfileUpdate.provider),
                joinedload(ProviderProfileUpdate.reviewer),
            )
            .where(*conditions)
            .order_by(ProviderProfileUpdate.submitted_at.desc(), ProviderProfileUpdate.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total