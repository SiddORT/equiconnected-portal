"""
Specialization management endpoints (admin only).

GET    /api/v1/admin/specializations          — list with search/filter/pagination
POST   /api/v1/admin/specializations          — create
GET    /api/v1/admin/specializations/{id}     — get single
PATCH  /api/v1/admin/specializations/{id}     — update name / description
PATCH  /api/v1/admin/specializations/{id}/status — activate / deactivate
"""
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.repositories.specialization_repository import SpecializationRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.specialization import (
    SpecializationCreate,
    SpecializationResponse,
    SpecializationStatusUpdate,
    SpecializationUpdate,
)
from app.services.specialization_service import (
    DuplicateSpecializationError,
    SpecializationNotFoundError,
    SpecializationService,
)

router = APIRouter(
    prefix="/admin/specializations",
    tags=["Specializations"],
    dependencies=[Depends(require_role("admin"))],
)

_DB = Annotated[Session, Depends(get_db)]


def _svc(db: _DB) -> SpecializationService:
    return SpecializationService(SpecializationRepository(db))


_Svc = Annotated[SpecializationService, Depends(_svc)]


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[SpecializationResponse])
def list_specializations(
    svc: _Svc,
    search: str | None = Query(None, max_length=200, description="Name substring search"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
):
    items, total = svc.list(
        search=search, is_active=is_active, page=page, page_size=page_size
    )
    total_pages = max(1, ceil(total / page_size))
    return PaginatedResponse(
        data=[SpecializationResponse.model_validate(s) for s in items],
        meta=PaginationMeta(
            page=page, page_size=page_size, total=total, total_pages=total_pages
        ),
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=SpecializationResponse, status_code=status.HTTP_201_CREATED)
def create_specialization(body: SpecializationCreate, svc: _Svc):
    try:
        spec = svc.create(
            name=body.name,
            description=body.description,
            is_active=body.is_active,
        )
        return SpecializationResponse.model_validate(spec)
    except DuplicateSpecializationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "duplicate_specialization", "message": str(exc)},
        )


# ── Get single ────────────────────────────────────────────────────────────────

@router.get("/{id}", response_model=SpecializationResponse)
def get_specialization(id: UUID, svc: _Svc):
    try:
        return SpecializationResponse.model_validate(svc.get(id))
    except SpecializationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "specialization_not_found", "message": "Specialization not found"},
        )


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{id}", response_model=SpecializationResponse)
def update_specialization(id: UUID, body: SpecializationUpdate, svc: _Svc):
    try:
        spec = svc.update(id, update_fields=body.model_dump(exclude_unset=True))
        return SpecializationResponse.model_validate(spec)
    except SpecializationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "specialization_not_found", "message": "Specialization not found"},
        )
    except DuplicateSpecializationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "duplicate_specialization", "message": str(exc)},
        )


# ── Status toggle ─────────────────────────────────────────────────────────────

@router.patch("/{id}/status", response_model=SpecializationResponse)
def update_specialization_status(id: UUID, body: SpecializationStatusUpdate, svc: _Svc):
    try:
        spec = svc.set_status(id, is_active=body.is_active)
        return SpecializationResponse.model_validate(spec)
    except SpecializationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "specialization_not_found", "message": "Specialization not found"},
        )
