"""Authenticated portal endpoints for provider accounts created from invitations."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, require_role
from app.db.session import get_db
from app.models.specialization import Specialization
from app.repositories.audit_repository import context_from_request
from app.repositories.provider_profile_update_repository import ProviderProfileUpdateRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.review_repository import ReviewRepository
from app.schemas.provider import ProviderPortalResponse, ProviderPortalUpdate
from app.services.invitation_service import InvalidProviderDataError
from app.services.provider_portal_service import (
    ProviderPortalService,
    ProviderPortalUnavailableError,
    ProviderProfileUpdateDiscardError,
)

router = APIRouter(
    prefix="/provider/portal",
    tags=["Provider portal"],
    dependencies=[Depends(require_role("provider"))],
)
_DB = Annotated[Session, Depends(get_db)]


def _svc(db: _DB) -> ProviderPortalService:
    return ProviderPortalService(
        ProviderRepository(db),
        ReviewRepository(db),
        ProviderProfileUpdateRepository(db),
    )


_Svc = Annotated[ProviderPortalService, Depends(_svc)]


@router.get("/profile", response_model=ProviderPortalResponse)
def get_profile(current_user: CurrentUser, svc: _Svc) -> ProviderPortalResponse:
    try:
        return svc.get_profile(current_user)
    except ProviderPortalUnavailableError:
        raise HTTPException(
            status_code=403,
            detail={"code": "provider_portal_unavailable", "message": "Provider portal access is unavailable."},
        )


@router.get("/specializations")
def list_specializations(db: _DB, current_user: CurrentUser, svc: _Svc):
    """Offer active specialization choices without exposing provider administration."""
    try:
        svc.get_profile(current_user)
    except ProviderPortalUnavailableError:
        raise HTTPException(
            status_code=403,
            detail={"code": "provider_portal_unavailable", "message": "Provider portal access is unavailable."},
        )
    rows = db.scalars(
        select(Specialization)
        .where(Specialization.is_active.is_(True))
        .order_by(Specialization.name)
    ).all()
    return [{"id": str(row.id), "name": row.name, "is_active": row.is_active} for row in rows]


@router.patch("/profile", response_model=ProviderPortalResponse)
def update_profile(
    body: ProviderPortalUpdate, request: Request, current_user: CurrentUser, svc: _Svc
) -> ProviderPortalResponse:
    try:
        return svc.update_profile(
            current_user,
            body.model_dump(exclude_unset=True),
            audit_context=context_from_request(request, current_user.id),
        )
    except ProviderPortalUnavailableError:
        raise HTTPException(
            status_code=403,
            detail={"code": "provider_portal_unavailable", "message": "Provider portal access is unavailable."},
        )
    except InvalidProviderDataError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "provider_profile_invalid", "message": str(exc)},
        )


@router.post("/profile-update/discard", response_model=ProviderPortalResponse)
def discard_profile_update(
    request: Request, current_user: CurrentUser, svc: _Svc
) -> ProviderPortalResponse:
    try:
        return svc.discard_profile_update(
            current_user,
            audit_context=context_from_request(request, current_user.id),
        )
    except ProviderPortalUnavailableError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "provider_profile_update_unavailable",
                "message": "There is no profile update draft to discard.",
            },
        )
    except ProviderProfileUpdateDiscardError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "provider_profile_update_not_discardable",
                "message": str(exc),
            },
        )