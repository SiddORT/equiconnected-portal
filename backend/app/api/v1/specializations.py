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

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.repositories.specialization_repository import SpecializationRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.specialization import (
    ImportConfirmRequest,
    ImportPreviewResponse,
    ImportResult,
    ImportRowPreview,
    SpecializationCreate,
    SpecializationResponse,
    SpecializationStatusUpdate,
    SpecializationUpdate,
)
from app.services import specialization_import_export_service as ie_svc
from app.services.specialization_import_export_service import (
    ImportFileError,
    ImportRowResult,
    MAX_FILE_SIZE_BYTES,
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


# ── CSV export ────────────────────────────────────────────────────────────────
# NOTE: static-path routes must be declared BEFORE the /{id} route.

@router.get("/export")
def export_specializations(
    db: _DB,
    search: str | None = Query(None, max_length=200),
    is_active: bool | None = Query(None),
):
    filename = ie_svc.export_filename()
    return StreamingResponse(
        ie_svc.export_csv(db, search=search, is_active=is_active),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/import/template")
def download_import_template():
    return Response(
        content=ie_svc.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="equiconnected-specializations-template.csv"'
        },
    )


# ── CSV import ────────────────────────────────────────────────────────────────

def _validate_upload(file: UploadFile) -> None:
    name = (file.filename or "").lower()
    if not name.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_file_type", "message": "Only .csv files are accepted."},
        )
    if file.content_type not in (
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "text/plain",
        "application/octet-stream",
        None,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_file_type", "message": "File must be a CSV."},
        )


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview_import(file: UploadFile, db: _DB):
    _validate_upload(file)
    contents = await file.read(MAX_FILE_SIZE_BYTES + 1)
    try:
        rows = ie_svc.parse_and_validate(contents, db)
    except ImportFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_import_file", "message": str(exc)},
        )
    return ImportPreviewResponse(
        total=len(rows),
        valid=sum(1 for r in rows if r.state == "valid"),
        duplicate=sum(1 for r in rows if r.state == "duplicate"),
        invalid=sum(1 for r in rows if r.state == "invalid"),
        rows=[ImportRowPreview(**r.__dict__) for r in rows],
    )


@router.post("/import", response_model=ImportResult)
def confirm_import(body: ImportConfirmRequest, db: _DB):
    validated = [ImportRowResult(**r.model_dump()) for r in body.rows]
    # Re-run canonical field validation server-side: never trust client 'state'.
    for r in validated:
        if r.state == "valid":
            ie_svc.validate_row_fields(r)
    result = ie_svc.commit_import(db, validated)
    return ImportResult(
        imported=result.imported,
        skipped=result.skipped,
        errors=result.errors,
        row_details=[ImportRowPreview(**r.__dict__) for r in result.row_details],
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
