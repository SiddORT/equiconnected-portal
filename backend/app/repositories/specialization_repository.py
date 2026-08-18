"""
SpecializationRepository — data-access layer for specialization master data.
"""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.specialization import Specialization


class SpecializationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get_by_id(self, id: UUID) -> Specialization | None:
        return self._db.get(Specialization, id)

    def get_by_name(self, name: str) -> Specialization | None:
        """Case-insensitive exact name lookup."""
        return self._db.scalar(
            select(Specialization).where(
                func.lower(Specialization.name) == name.strip().lower()
            )
        )

    def list(
        self,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Specialization], int]:
        """
        Return (items, total_count) for the requested page.
        Search is a case-insensitive name substring match.
        """
        stmt = select(Specialization)
        count_stmt = select(func.count()).select_from(Specialization)

        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(Specialization.name.ilike(pattern))
            count_stmt = count_stmt.where(Specialization.name.ilike(pattern))

        if is_active is not None:
            stmt = stmt.where(Specialization.is_active == is_active)
            count_stmt = count_stmt.where(Specialization.is_active == is_active)

        total: int = self._db.scalar(count_stmt) or 0

        stmt = (
            stmt.order_by(Specialization.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self._db.scalars(stmt).all())

        return items, total

    # ── Writes ────────────────────────────────────────────────────────────────

    def create(
        self,
        *,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> Specialization:
        spec = Specialization(name=name, description=description, is_active=is_active)
        self._db.add(spec)
        self._db.flush()  # surface constraint errors before commit
        return spec

    # ── Transaction helpers ───────────────────────────────────────────────────

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
