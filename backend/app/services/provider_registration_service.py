"""Provider application review decisions and their atomic listing creation."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.enums import (
    ProviderApplicationStatus,
    ProviderStatus,
    PublicationStatus,
)
from app.models.provider import Provider
from app.models.provider_registration import ProviderRegistrationApplication
from app.repositories.audit_repository import AuditRepository
from app.repositories.provider_registration_repository import ProviderRegistrationRepository


class ProviderApplicationNotFoundError(Exception):
    """Raised when an application is unavailable."""


class ProviderApplicationDecisionError(Exception):
    """Raised when a decision cannot be applied to the current state."""


class ProviderRegistrationService:
    def __init__(self, repository: ProviderRegistrationRepository) -> None:
        self._repo = repository
        self._db = repository._db
        self._audit = AuditRepository(self._db)

    def list(self, **filters) -> tuple[list[ProviderRegistrationApplication], int]:
        return self._repo.list(**filters)

    def get(self, application_id: UUID) -> ProviderRegistrationApplication:
        application = self._repo.get(application_id)
        if application is None:
            raise ProviderApplicationNotFoundError
        return application

    def approve(
        self, application_id: UUID, reviewer_id: UUID
    ) -> ProviderRegistrationApplication:
        application = self._repo.get_for_update(application_id)
        if application is None:
            raise ProviderApplicationNotFoundError
        if application.review_status != ProviderApplicationStatus.PENDING_REVIEW:
            self._db.rollback()
            raise ProviderApplicationDecisionError(
                "Only verified applications awaiting review can be approved."
            )
        if application.user.email_verified_at is None:
            self._db.rollback()
            raise ProviderApplicationDecisionError(
                "The provider email must be verified before approval."
            )

        now = datetime.now(timezone.utc)
        provider = Provider(
            provider_type=application.provider_type,
            name=application.provider_name,
            visit_stability=application.visit_stability,
            status=ProviderStatus.DRAFT,
            publication_status=PublicationStatus.UNPUBLISHED,
            email=application.user.email,
            phone=application.user.mobile_number,
        )
        self._db.add(provider)
        self._db.flush()
        application.provider_id = provider.id
        application.review_status = ProviderApplicationStatus.APPROVED
        application.reviewed_by_user_id = reviewer_id
        application.reviewed_at = now
        application.rejection_reason = None
        application.user.is_active = True
        self._audit.log(
            action="provider_application.approved",
            user_id=reviewer_id,
            resource_type="provider_registration_application",
            resource_id=str(application.id),
            metadata={
                "provider_id": str(provider.id),
                "provider_name": provider.name,
                "provider_type": provider.provider_type.value,
                "status": provider.status.value,
                "publication_status": provider.publication_status.value,
            },
            summary="Approved provider application and staged an unpublished listing.",
        )
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ProviderApplicationDecisionError(
                "This application was already decided."
            ) from exc
        return self.get(application_id)

    def reject(
        self,
        application_id: UUID,
        reviewer_id: UUID,
        rejection_reason: str | None = None,
    ) -> ProviderRegistrationApplication:
        application = self._repo.get_for_update(application_id)
        if application is None:
            raise ProviderApplicationNotFoundError
        if application.review_status != ProviderApplicationStatus.PENDING_REVIEW:
            self._db.rollback()
            raise ProviderApplicationDecisionError(
                "Only verified applications awaiting review can be rejected."
            )
        now = datetime.now(timezone.utc)
        application.review_status = ProviderApplicationStatus.REJECTED
        application.reviewed_by_user_id = reviewer_id
        application.reviewed_at = now
        application.rejection_reason = rejection_reason
        application.user.is_active = False
        self._audit.log(
            action="provider_application.rejected",
            user_id=reviewer_id,
            resource_type="provider_registration_application",
            resource_id=str(application.id),
            metadata={"rejection_reason": rejection_reason},
            summary="Rejected provider application.",
        )
        self._db.commit()
        return self.get(application_id)