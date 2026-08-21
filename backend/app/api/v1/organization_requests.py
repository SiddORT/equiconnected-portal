"""Public organization lookup and admin review endpoints."""
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import OrganizationRequestStatus, ProviderType
from app.repositories.organization_request_repository import OrganizationRequestRepository
from app.repositories.audit_repository import context_from_request
from app.schemas.common import PaginationMeta
from app.schemas.organization_request import (
    OrganizationSearchResponse, OrganizationSearchResult, OrgRequestListResponse, OrgRequestResponse,
)
from app.services.organization_request_service import (
    InvalidOrganizationRequestStateError,
    OrganizationRequestNotFoundError, OrganizationRequestService,
)

public_router = APIRouter(prefix="/provider/organizations", tags=["Provider organizations"])
admin_router = APIRouter(
    prefix="/admin/organization-requests", tags=["Organization requests"],
    dependencies=[Depends(require_role("admin"))],
)
_DB = Annotated[Session, Depends(get_db)]


def _svc(db: _DB) -> OrganizationRequestService:
    return OrganizationRequestService(OrganizationRequestRepository(db))


_Svc = Annotated[OrganizationRequestService, Depends(_svc)]


@public_router.get("/search", response_model=OrganizationSearchResponse)
def search_organizations(
    svc: _Svc,
    q: str | None = Query(None, max_length=300),
    type_: ProviderType | None = Query(None, alias="type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if type_ == ProviderType.DOCTOR:
        raise HTTPException(status_code=422, detail="type must be HOSPITAL or CLINIC")
    items, total = svc.search(query=q, organization_type=type_, page=page, page_size=page_size)
    return OrganizationSearchResponse(
        data=[OrganizationSearchResult(id=provider.id, name=provider.name, provider_type=provider.provider_type, city=city)
              for provider, city in items],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=max(1, ceil(total / page_size))),
    )


@admin_router.get("", response_model=OrgRequestListResponse)
def list_requests(
    svc: _Svc,
    status: OrganizationRequestStatus | None = None,
    type_: ProviderType | None = Query(None, alias="type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if type_ == ProviderType.DOCTOR:
        raise HTTPException(status_code=422, detail="type must be HOSPITAL or CLINIC")
    items, total = svc.list(status=status, organization_type=type_, page=page, page_size=page_size)
    return OrgRequestListResponse(
        data=[OrgRequestResponse.model_validate(item) for item in items],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=max(1, ceil(total / page_size))),
    )


@admin_router.post("/{request_id}/approve", response_model=OrgRequestResponse)
def approve_request(request_id: UUID, request: Request, user: CurrentUser, svc: _Svc):
    try:
        return svc.approve(
            request_id, user.id, audit_context=context_from_request(request, user.id)
        )
    except OrganizationRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Organization request not found")
    except InvalidOrganizationRequestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@admin_router.post("/{request_id}/reject", response_model=OrgRequestResponse)
def reject_request(request_id: UUID, request: Request, user: CurrentUser, svc: _Svc):
    try:
        return svc.reject(request_id, audit_context=context_from_request(request, user.id))
    except OrganizationRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Organization request not found")
    except InvalidOrganizationRequestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))