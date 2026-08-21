"""
SpecializationService — business logic for specialization master data.
"""
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.specialization import Specialization
from app.repositories.specialization_repository import SpecializationRepository
from app.repositories.audit_repository import AuditContext, AuditRepository


# ── Domain exceptions ─────────────────────────────────────────────────────────

class DuplicateSpecializationError(Exception):
    """Raised when a specialization with the same name already exists."""


class SpecializationNotFoundError(Exception):
    """Raised when a specialization is not found by ID."""


# ── Service ───────────────────────────────────────────────────────────────────

class SpecializationService:
    def __init__(self, repo: SpecializationRepository) -> None:
        self._repo = repo
        self._audit = AuditRepository(repo._db)

    def _record(
        self, action: str, spec: Specialization, summary: str, *,
        context: AuditContext | None = None, changes: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._audit.record(
            action,
            context=context,
            resource_type="specialization",
            resource_id=str(spec.id),
            summary=summary,
            changes=changes,
            metadata={"specialization_name": spec.name, **(metadata or {})},
        )

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
        audit_context: AuditContext | None = None,
    ) -> Specialization:
        try:
            spec = self._repo.create(
                name=name.strip(),
                description=description,
                is_active=is_active,
            )
            self._record(
                "specialization.created", spec, f"Created specialization “{spec.name}”.",
                context=audit_context,
                changes=[
                    {"field": "name", "before": None, "after": spec.name},
                    {"field": "description", "before": None, "after": spec.description},
                    {"field": "is_active", "before": None, "after": spec.is_active},
                ],
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
        audit_context: AuditContext | None = None,
    ) -> Specialization:
        """
        Partial update — only keys present in update_fields are applied.
        Accepts: name, description.
        """
        spec = self.get(id)
        changes = []

        if "name" in update_fields:
            new_name = update_fields["name"]
            if new_name is not None:
                if spec.name != new_name.strip():
                    changes.append({"field": "name", "before": spec.name, "after": new_name.strip()})
                spec.name = new_name.strip()

        if "description" in update_fields:
            if spec.description != update_fields["description"]:
                changes.append(
                    {"field": "description", "before": spec.description, "after": update_fields["description"]}
                )
            spec.description = update_fields["description"]

        try:
            if changes:
                self._record(
                    "specialization.updated", spec, f"Updated specialization “{spec.name}”.",
                    context=audit_context, changes=changes,
                )
            self._repo.commit()
            return spec
        except IntegrityError:
            self._repo.rollback()
            raise DuplicateSpecializationError(
                f"A specialization named '{update_fields.get('name')}' already exists."
            )

    def set_status(self, id: UUID, *, is_active: bool,
                   audit_context: AuditContext | None = None) -> Specialization:
        spec = self.get(id)
        before = spec.is_active
        spec.is_active = is_active
        self._record(
            "specialization.status_changed",
            spec,
            f"{'Activated' if is_active else 'Deactivated'} specialization “{spec.name}”.",
            context=audit_context,
            changes=[{"field": "is_active", "before": before, "after": is_active}],
        )
        self._repo.commit()
        return spec
