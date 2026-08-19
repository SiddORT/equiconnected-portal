"""Business rules for invited-doctor organization associations and requests."""
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.enums import (
    DoctorOrganizationStatus, OrganizationRequestStatus, ProviderStatus, ProviderType,
    PublicationStatus, VisitStability,
)
from app.models.organization_request import OrganizationRequest
from app.repositories.organization_request_repository import OrganizationRequestRepository


class OrganizationRequestNotFoundError(Exception):
    pass


class InvalidOrganizationTypeError(Exception):
    pass


class DuplicateOrganizationRelationshipError(Exception):
    pass


class DuplicateOrganizationSuggestionsError(Exception):
    def __init__(self, suggestions: list) -> None:
        self.suggestions = suggestions


class InvalidOrganizationRequestStateError(Exception):
    pass


class OrganizationRequestService:
    def __init__(self, repo: OrganizationRequestRepository) -> None:
        self._repo = repo

    @staticmethod
    def _require_org_type(organization_type: ProviderType) -> None:
        if organization_type not in (ProviderType.HOSPITAL, ProviderType.CLINIC):
            raise InvalidOrganizationTypeError("Organization type must be HOSPITAL or CLINIC.")

    def search(self, **kwargs):
        return self._repo.search_organizations(**kwargs)

    def suggestions(self, name: str, organization_type: ProviderType):
        self._require_org_type(organization_type)
        return self._repo.duplicate_suggestions(name, organization_type)

    def associate_existing(self, doctor_id: UUID, organization_id: UUID):
        doctor = self._repo.get_provider(doctor_id)
        target = self._repo.get_provider(organization_id)
        if not doctor or doctor.provider_type != ProviderType.DOCTOR:
            raise InvalidOrganizationTypeError("Invitation provider must be a Doctor.")
        if doctor_id == organization_id:
            raise InvalidOrganizationTypeError("A doctor cannot be affiliated with itself.")
        if not target or target.provider_type not in (ProviderType.HOSPITAL, ProviderType.CLINIC):
            raise InvalidOrganizationTypeError("Organization must be a Hospital or Clinic.")
        if self._repo.get_relationship(doctor_id, organization_id):
            raise DuplicateOrganizationRelationshipError()
        try:
            relationship = self._repo.create_relationship(
                doctor_id, organization_id, status=DoctorOrganizationStatus.PENDING
            )
            self._repo.commit()
            return relationship
        except IntegrityError as exc:
            self._repo.rollback()
            raise DuplicateOrganizationRelationshipError() from exc

    def create_request(self, doctor_id: UUID, data: dict) -> OrganizationRequest:
        data = dict(data)
        self._require_org_type(data["organization_type"])
        doctor = self._repo.get_provider(doctor_id)
        if not doctor or doctor.provider_type != ProviderType.DOCTOR:
            raise InvalidOrganizationTypeError("Invitation provider must be a Doctor.")
        suggestions = self.suggestions(data["organization_name"], data["organization_type"])
        if suggestions and not data.pop("confirm_no_match", False):
            raise DuplicateOrganizationSuggestionsError(suggestions)
        data.pop("confirm_no_match", None)
        request = self._repo.create(doctor_provider_id=doctor_id, **data)
        self._repo.commit()
        return request

    def list(self, **kwargs):
        return self._repo.list(**kwargs)

    def approve(self, request_id: UUID, admin_id: UUID | None = None) -> OrganizationRequest:
        request = self._repo.get(request_id)
        if not request:
            raise OrganizationRequestNotFoundError()
        if request.status != OrganizationRequestStatus.PENDING:
            raise InvalidOrganizationRequestStateError("Only pending requests can be approved.")
        try:
            provider = self._repo.create_provider(
                provider_type=request.organization_type, name=request.organization_name,
                email=request.contact_email, visit_stability=VisitStability.STABLE_VISIT,
                status=ProviderStatus.DRAFT, publication_status=PublicationStatus.UNPUBLISHED,
            )
            relationship = self._repo.create_relationship(
                request.doctor_provider_id, provider.id, status=DoctorOrganizationStatus.PENDING
            )
            relationship.status = DoctorOrganizationStatus.ACTIVE
            request.status = OrganizationRequestStatus.APPROVED
            self._repo.commit()
        except Exception:
            self._repo.rollback()
            raise
        return request

    def reject(self, request_id: UUID) -> OrganizationRequest:
        request = self._repo.get(request_id)
        if not request:
            raise OrganizationRequestNotFoundError()
        if request.status != OrganizationRequestStatus.PENDING:
            raise InvalidOrganizationRequestStateError("Only pending requests can be rejected.")
        try:
            request.status = OrganizationRequestStatus.REJECTED
            self._repo.commit()
        except Exception:
            self._repo.rollback()
            raise
        return request