"""
SpecializationService — business logic for specialization master data.
"""
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.specialization import Specialization
from app.repositories.specialization_repository import SpecializationRepository


# ── Domain exceptions ─────────────────────────────────────────────────────────

class DuplicateSpecializationError(Exception):
    """Raised when a specialization with the same name already exists."""


class SpecializationNotFoundError(Exception):
    """Raised when a specialization is not found by ID."""


# ── Service ───────────────────────────────────────────────────────────────────

class SpecializationService:
    def __init__(self, repo: SpecializationRepository) -> None:
        self._repo = repo

    def list(
        self,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Specialization], int]:
        return self._repo.list(
            search=search, is_active=is_active, page=page, page_size=page_size
        )

    def get(self, id: UUID) -> Specialization:
        spec = self._repo.get_by_id(id)
        if spec is None:
            raise SpecializationNotFoundError(str(id))
        return spec

    def create(
        self,
        *,
        name: str,
        description: str | None = None,
        is_active: bool = True,
    ) -> Specialization:
        try:
            spec = self._repo.create(
                name=name.strip(),
                description=description,
                is_active=is_active,
            )
            self._repo.commit()
            return spec
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError(
                f"A specialization named '{name}' already exists."
            )

    def update(
        self,
        id: UUID,
        *,
        update_fields: dict,
    ) -> Specialization:
        """
        Partial update — only keys present in update_fields are applied.
        Accepts: name, description.
        """
        spec = self.get(id)

        if "name" in update_fields:
            new_name = update_fields["name"]
            if new_name is not None:
                spec.name = new_name.strip()

        if "description" in update_fields:
            spec.description = update_fields["description"]

        try:
            self._repo.commit()
            return spec
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError(
                f"A specialization named '{update_fields.get('name')}' already exists."
            )

    def set_status(self, id: UUID, *, is_active: bool) -> Specialization:
        spec = self.get(id)
        spec.is_active = is_active
        self._repo.commit()
        return spec
