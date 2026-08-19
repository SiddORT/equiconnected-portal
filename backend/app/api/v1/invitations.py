"""Authenticated admin and token-only public provider invitation endpoints."""
from datetime import datetime
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_role
from app.db.session import get_db
from app.core.rate_limit import check_invitation_rate_limit
from app.models.enums import InvitationStatus, ProviderType
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.provider_repository import ProviderRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.invitation import DraftSaveRequest, InvitationCreate, InvitationListResponse, InvitationResponse, InvitationTokenResponse, SubmitRequest
from app.services.email_service import EmailDeliveryError
from app.services.invitation_service import (
    DuplicateInvitationError, InvitationCancelledError, InvitationCompletedError, InvitationExpiredError,
    InvitationNotFoundError, InvitationService, InvalidInvitationStateError, InvalidProviderDataError,
    ProviderTypeMismatchError,
)
from app.services.provider_service import ProviderNotFoundError
from app.repositories.organization_request_repository import OrganizationRequestRepository
from app.schemas.organization_request import OrgAssociateRequest, OrgRequestCreate, OrgRequestResponse
from app.services.organization_request_service import (
    DuplicateOrganizationRelationshipError, DuplicateOrganizationSuggestionsError,
    InvalidOrganizationTypeError, OrganizationRequestService,
)

admin_router = APIRouter(prefix="/admin/invitations", tags=["Invitations"], dependencies=[Depends(require_role("admin"))])
public_router = APIRouter(
    prefix="/provider/invitations",
    tags=["Provider invitations"],
    dependencies=[Depends(check_invitation_rate_limit)],
)
_DB = Annotated[Session, Depends(get_db)]

def _svc(db: _DB) -> InvitationService:
    return InvitationService(InvitationRepository(db), ProviderRepository(db))
_Svc = Annotated[InvitationService, Depends(_svc)]

def _organization_svc(db: _DB) -> OrganizationRequestService:
    return OrganizationRequestService(OrganizationRequestRepository(db))
_OrganizationSvc = Annotated[OrganizationRequestService, Depends(_organization_svc)]

def _error(code: int, key: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"code": key, "message": message})

@admin_router.get("", response_model=InvitationListResponse)
def list_invitations(svc: _Svc, search: str | None = None, status_: InvitationStatus | None = Query(None, alias="status"),
                     provider_type: ProviderType | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                     page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    items, total = svc.list(search=search, status=status_, provider_type=provider_type, date_from=date_from, date_to=date_to, page=page, page_size=page_size)
    return PaginatedResponse(data=[InvitationResponse.model_validate(item) for item in items],
                             meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=max(1, ceil(total/page_size))))

@admin_router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(body: InvitationCreate, user: CurrentUser, svc: _Svc):
    try: return InvitationResponse.model_validate(svc.create_invitation(fields=body.model_dump(), created_by=user.id))
    except DuplicateInvitationError as exc: raise _error(409, "duplicate_invitation", str(exc))
    except (ProviderNotFoundError,): raise _error(404, "provider_not_found", "Provider was not found.")
    except ProviderTypeMismatchError as exc: raise _error(422, "provider_type_mismatch", str(exc))
    except EmailDeliveryError as exc: raise _error(502, "email_delivery_failed", str(exc))

@admin_router.post("/{invitation_id}/resend", response_model=InvitationResponse)
def resend_invitation(invitation_id: UUID, svc: _Svc):
    try: return InvitationResponse.model_validate(svc.resend_invitation(invitation_id))
    except InvitationNotFoundError: raise _error(404, "invitation_not_found", "Invitation was not found.")
    except DuplicateInvitationError as exc: raise _error(409, "duplicate_invitation", str(exc))
    except InvalidInvitationStateError as exc: raise _error(409, "invalid_invitation_state", str(exc))
    except EmailDeliveryError as exc: raise _error(502, "email_delivery_failed", str(exc))

@admin_router.post("/{invitation_id}/cancel", response_model=InvitationResponse)
def cancel_invitation(invitation_id: UUID, svc: _Svc):
    try: return InvitationResponse.model_validate(svc.cancel_invitation(invitation_id))
    except InvitationNotFoundError: raise _error(404, "invitation_not_found", "Invitation was not found.")
    except InvalidInvitationStateError as exc: raise _error(409, "invalid_invitation_state", str(exc))

@public_router.get("/{token}", response_model=InvitationTokenResponse)
def get_invitation(token: str, svc: _Svc):
    try: return InvitationTokenResponse.model_validate(svc.token_payload(svc.validate_token(token)))
    except InvitationNotFoundError: raise _error(404, "invitation_not_found", "Invitation link is invalid.")
    except InvitationExpiredError: raise _error(410, "invitation_expired", "Invitation link has expired.")
    except (InvitationCompletedError, InvitationCancelledError): raise _error(409, "invitation_unavailable", "Invitation link is no longer available.")

@public_router.post("/{token}/save", response_model=InvitationTokenResponse)
def save_invitation(token: str, body: DraftSaveRequest, svc: _Svc):
    try: return InvitationTokenResponse.model_validate(svc.token_payload(svc.save_draft(token, body.model_dump(exclude_unset=True))))
    except InvitationNotFoundError: raise _error(404, "invitation_not_found", "Invitation link is invalid.")
    except InvitationExpiredError: raise _error(410, "invitation_expired", "Invitation link has expired.")
    except (InvitationCompletedError, InvitationCancelledError): raise _error(409, "invitation_unavailable", "Invitation link is no longer available.")
    except InvalidProviderDataError as exc: raise _error(422, "provider_validation_failed", str(exc))

@public_router.post("/{token}/submit", response_model=InvitationTokenResponse)
def submit_invitation(token: str, body: SubmitRequest, svc: _Svc):
    try: return InvitationTokenResponse.model_validate(svc.token_payload(svc.submit_invitation(token, body.model_dump(exclude_unset=True))))
    except InvitationNotFoundError: raise _error(404, "invitation_not_found", "Invitation link is invalid.")
    except InvitationExpiredError: raise _error(410, "invitation_expired", "Invitation link has expired.")
    except (InvitationCompletedError, InvitationCancelledError) as exc: raise _error(409, "invitation_unavailable", str(exc) or "Invitation link is no longer available.")
    except (InvalidInvitationStateError, InvalidProviderDataError) as exc: raise _error(422, "provider_validation_failed", str(exc))


def _doctor_invitation(token: str, svc: InvitationService):
    invitation = svc.validate_token(token)
    if invitation.provider_type != ProviderType.DOCTOR or invitation.provider_id is None:
        raise _error(422, "doctor_invitation_required", "This action requires a Doctor invitation.")
    return invitation


@public_router.post("/{token}/organizations", status_code=status.HTTP_201_CREATED)
def associate_organization(
    token: str, body: OrgAssociateRequest, svc: _Svc, organization_svc: _OrganizationSvc,
):
    try:
        invitation = _doctor_invitation(token, svc)
        relationship = organization_svc.associate_existing(invitation.provider_id, body.organization_id)
        return {"id": relationship.id, "status": relationship.status}
    except InvitationNotFoundError: raise _error(404, "invitation_not_found", "Invitation link is invalid.")
    except InvitationExpiredError: raise _error(410, "invitation_expired", "Invitation link has expired.")
    except (InvitationCompletedError, InvitationCancelledError): raise _error(409, "invitation_unavailable", "Invitation link is no longer available.")
    except InvalidOrganizationTypeError as exc: raise _error(422, "invalid_organization", str(exc))
    except DuplicateOrganizationRelationshipError: raise _error(409, "duplicate_organization_relationship", "This organization is already associated.")


@public_router.post("/{token}/organization-requests", response_model=OrgRequestResponse, status_code=status.HTTP_201_CREATED)
def create_organization_request(
    token: str, body: OrgRequestCreate, svc: _Svc, organization_svc: _OrganizationSvc,
):
    try:
        invitation = _doctor_invitation(token, svc)
        return organization_svc.create_request(invitation.provider_id, body.model_dump())
    except InvitationNotFoundError: raise _error(404, "invitation_not_found", "Invitation link is invalid.")
    except InvitationExpiredError: raise _error(410, "invitation_expired", "Invitation link has expired.")
    except (InvitationCompletedError, InvitationCancelledError): raise _error(409, "invitation_unavailable", "Invitation link is no longer available.")
    except InvalidOrganizationTypeError as exc: raise _error(422, "invalid_organization", str(exc))
    except DuplicateOrganizationSuggestionsError as exc:
        raise HTTPException(status_code=409, detail={
            "code": "organization_suggestions",
            "message": "Similar organizations already exist.",
            "suggestions": [{"id": str(item.id), "name": item.name, "type": item.provider_type.value} for item in exc.suggestions],
        })