"""
Healthcare Provider management endpoints (admin only).

GET    /api/v1/admin/providers                       — list with search/filter/pagination
POST   /api/v1/admin/providers                       — create
GET    /api/v1/admin/providers/{id}                  — get detail
PATCH  /api/v1/admin/providers/{id}                  — partial update of core fields
PATCH  /api/v1/admin/providers/{id}/status           — toggle operational status
PATCH  /api/v1/admin/providers/{id}/publication      — toggle publication status
POST   /api/v1/admin/providers/{id}/specializations  — assign specialization
DELETE /api/v1/admin/providers/{id}/specializations/{spec_id} — unassign
POST   /api/v1/admin/providers/{id}/locations        — add location
PATCH  /api/v1/admin/providers/{id}/locations/{loc_id}   — update location
DELETE /api/v1/admin/providers/{id}/locations/{loc_id}   — delete location
POST   /api/v1/admin/providers/{id}/photos           — add photo metadata
PATCH  /api/v1/admin/providers/{id}/photos/{photo_id}    — update photo metadata
DELETE /api/v1/admin/providers/{id}/photos/{photo_id}    — delete photo
PATCH  /api/v1/admin/providers/{id}/photos/{photo_id}/thumbnail — set thumbnail
"""
from math import ceil
from typing import Annotated
from uuid import UUID

import os
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.models.enums import (
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.repositories.provider_repository import ProviderRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.provider import (
    EmailCreate,
    EmailResponse,
    LocationCreate,
    PhoneCreate,
    PhoneResponse,
    LocationResponse,
    LocationUpdate,
    PhotoCreate,
    PhotoResponse,
    PhotoUpdate,
    ProviderCreate,
    ProviderListItem,
    ProviderPublicationUpdate,
    ProviderResponse,
    ProviderSpecializationAdd,
    ProviderStatusUpdate,
    ProviderUpdate,
)
from app.services.provider_service import (
    DuplicateSpecializationError,
    EmailNotFoundError,
    LocationNotFoundError,
    PhoneNotFoundError,
    PhotoNotFoundError,
    ProviderNotFoundError,
    ProviderService,
    SpecializationNotFoundError,
)

router = APIRouter(
    prefix="/admin/providers",
    tags=["Providers"],
    dependencies=[Depends(require_role("admin"))],
)

_DB = Annotated[Session, Depends(get_db)]


def _svc(db: _DB) -> ProviderService:
    return ProviderService(ProviderRepository(db))


_Svc = Annotated[ProviderService, Depends(_svc)]


def _404(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": code, "message": message},
    )


def _409(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message": message},
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[ProviderListItem])
def list_providers(
    svc: _Svc,
    search: str | None = Query(None, max_length=300, description="Name substring search"),
    provider_type: ProviderType | None = Query(None),
    visit_stability: VisitStability | None = Query(None),
    status_: ProviderStatus | None = Query(None, alias="status"),
    publication_status: PublicationStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = svc.list(
        search=search,
        provider_type=provider_type,
        visit_stability=visit_stability,
        status=status_,
        publication_status=publication_status,
        page=page,
        page_size=page_size,
    )
    total_pages = max(1, ceil(total / page_size))
    return PaginatedResponse(
        data=[ProviderListItem.from_provider_row(p) for p in items],
        meta=PaginationMeta(
            page=page, page_size=page_size, total=total, total_pages=total_pages
        ),
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(body: ProviderCreate, svc: _Svc):
    _PROFILE_FIELDS = {
        "professional_title", "biography", "years_experience", "experience_description"
    }
    core = body.model_dump(
        exclude={"specialization_ids", "primary_location", "phones", "emails"}
        | _PROFILE_FIELDS
    )
    try:
        provider = svc.create(
            core_fields=core,
            specialization_ids=body.specialization_ids,
            primary_location=(
                body.primary_location.model_dump() if body.primary_location else None
            ),
            phones=[p.model_dump() for p in body.phones],
            emails=[e.model_dump() for e in body.emails],
            doctor_profile=body.model_dump(include=_PROFILE_FIELDS),
        )
        return ProviderResponse.from_provider(provider)
    except SpecializationNotFoundError as exc:
        raise _404("specialization_not_found", f"Specialization not found or inactive: {exc}")
    except DuplicateSpecializationError as exc:
        raise _409("duplicate_specialization", str(exc))


# ── Get detail ────────────────────────────────────────────────────────────────

@router.get("/{id}", response_model=ProviderResponse)
def get_provider(id: UUID, svc: _Svc):
    try:
        return ProviderResponse.from_provider(svc.get(id))
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")


# ── Update core fields ────────────────────────────────────────────────────────

@router.patch("/{id}", response_model=ProviderResponse)
def update_provider(id: UUID, body: ProviderUpdate, svc: _Svc):
    _PROFILE_FIELDS = {
        "professional_title", "biography", "years_experience", "experience_description"
    }
    fields = body.model_dump(exclude_unset=True)
    doctor_profile = {k: fields.pop(k) for k in list(fields) if k in _PROFILE_FIELDS}
    try:
        provider = svc.update(id, update_fields=fields, doctor_profile=doctor_profile)
        return ProviderResponse.from_provider(provider)
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")


# ── Status / publication toggles ──────────────────────────────────────────────

@router.patch("/{id}/status", response_model=ProviderResponse)
def update_provider_status(id: UUID, body: ProviderStatusUpdate, svc: _Svc):
    try:
        return ProviderResponse.from_provider(svc.set_status(id, status=body.status))
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")


@router.patch("/{id}/publication", response_model=ProviderResponse)
def update_provider_publication(id: UUID, body: ProviderPublicationUpdate, svc: _Svc):
    try:
        return ProviderResponse.from_provider(
            svc.set_publication(id, publication_status=body.publication_status)
        )
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")


# ── Specializations ───────────────────────────────────────────────────────────

@router.post(
    "/{id}/specializations",
    response_model=ProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_provider_specialization(id: UUID, body: ProviderSpecializationAdd, svc: _Svc):
    try:
        return ProviderResponse.from_provider(
            svc.add_specialization(id, body.specialization_id)
        )
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except SpecializationNotFoundError:
        raise _404("specialization_not_found", "Specialization not found")
    except DuplicateSpecializationError as exc:
        raise _409("duplicate_specialization", str(exc))


@router.delete("/{id}/specializations/{spec_id}", response_model=ProviderResponse)
def remove_provider_specialization(id: UUID, spec_id: UUID, svc: _Svc):
    try:
        return ProviderResponse.from_provider(svc.remove_specialization(id, spec_id))
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except SpecializationNotFoundError:
        raise _404(
            "specialization_not_assigned",
            "Specialization is not assigned to this provider",
        )


# ── Locations ─────────────────────────────────────────────────────────────────

@router.post(
    "/{id}/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_provider_location(id: UUID, body: LocationCreate, svc: _Svc):
    try:
        return LocationResponse.model_validate(
            svc.add_location(id, fields=body.model_dump())
        )
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")


@router.patch("/{id}/locations/{loc_id}", response_model=LocationResponse)
def update_provider_location(id: UUID, loc_id: UUID, body: LocationUpdate, svc: _Svc):
    try:
        return LocationResponse.model_validate(
            svc.update_location(
                id, loc_id, update_fields=body.model_dump(exclude_unset=True)
            )
        )
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except LocationNotFoundError:
        raise _404("location_not_found", "Location not found")


@router.delete("/{id}/locations/{loc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_location(id: UUID, loc_id: UUID, svc: _Svc):
    try:
        svc.delete_location(id, loc_id)
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except LocationNotFoundError:
        raise _404("location_not_found", "Location not found")


# ── Phones ────────────────────────────────────────────────────────────────────

@router.post(
    "/{id}/phones",
    response_model=PhoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_provider_phone(id: UUID, body: PhoneCreate, svc: _Svc):
    try:
        return PhoneResponse.model_validate(
            svc.add_provider_phone(id, fields=body.model_dump())
        )
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")


@router.delete("/{id}/phones/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_provider_phone(id: UUID, phone_id: UUID, svc: _Svc):
    try:
        svc.remove_provider_phone(id, phone_id)
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except PhoneNotFoundError:
        raise _404("phone_not_found", "Phone not found")


# ── Emails ────────────────────────────────────────────────────────────────────

@router.post(
    "/{id}/emails",
    response_model=EmailResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_provider_email(id: UUID, body: EmailCreate, svc: _Svc):
    try:
        return EmailResponse.model_validate(
            svc.add_provider_email(id, fields=body.model_dump())
        )
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")


@router.delete("/{id}/emails/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_provider_email(id: UUID, email_id: UUID, svc: _Svc):
    try:
        svc.remove_provider_email(id, email_id)
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except EmailNotFoundError:
        raise _404("email_not_found", "Email not found")


# Resolve uploads dir: backend/app/api/v1/ → 4 levels up → backend/uploads
_UPLOADS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "uploads",
)

_ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

# ── Photos ────────────────────────────────────────────────────────────────────

@router.post(
    "/{id}/photos",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_provider_photo(id: UUID, request: Request, svc: _Svc):
    """Create a photo record from JSON metadata or upload a multipart image.

    JSON metadata is retained for existing integrations that store an externally
    hosted asset reference. Multipart requests save an uploaded image locally.
    """
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        try:
            fields = PhotoCreate.model_validate(await request.json()).model_dump()
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        try:
            return PhotoResponse.model_validate(svc.add_photo(id, fields=fields))
        except ProviderNotFoundError:
            raise _404("provider_not_found", "Provider not found")

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "filename") or not hasattr(file, "read"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "file_required",
                "message": "An image file is required.",
            },
        )

    try:
        metadata = PhotoCreate.model_validate({
            # Reuse the established metadata validation rules for uploads too.
            "storage_reference": "upload",
            "alt_text": form.get("alt_text"),
            "caption": form.get("caption"),
            "display_order": form.get("display_order", 0),
            "is_thumbnail": form.get("is_thumbnail", False),
        })
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    # Validate MIME type
    content_type = file.content_type or ""
    ext = _ALLOWED_IMAGE_TYPES.get(content_type)
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_image_type",
                "message": "Only JPEG, PNG, GIF, and WebP images are accepted.",
            },
        )

    # Build destination: uploads/providers/{provider_id}/photos/{uuid}{ext}
    dest_dir = os.path.join(_UPLOADS_DIR, "providers", str(id), "photos")
    os.makedirs(dest_dir, exist_ok=True)
    filename = f"{_uuid.uuid4()}{ext}"
    dest_path = os.path.join(dest_dir, filename)

    # Write file to disk
    try:
        contents = await file.read()
    finally:
        await file.close()

    with open(dest_path, "wb") as fh:
        fh.write(contents)

    # URL path served by the /uploads StaticFiles mount
    storage_reference = f"/uploads/providers/{id}/photos/{filename}"

    try:
        return PhotoResponse.model_validate(
            svc.add_photo(id, fields={
                "storage_reference": storage_reference,
                "alt_text": metadata.alt_text,
                "caption": metadata.caption,
                "display_order": metadata.display_order,
                "is_thumbnail": metadata.is_thumbnail,
            })
        )
    except ProviderNotFoundError:
        os.remove(dest_path)
        raise _404("provider_not_found", "Provider not found")


@router.patch("/{id}/photos/{photo_id}", response_model=PhotoResponse)
def update_provider_photo(id: UUID, photo_id: UUID, body: PhotoUpdate, svc: _Svc):
    try:
        return PhotoResponse.model_validate(
            svc.update_photo(
                id, photo_id, update_fields=body.model_dump(exclude_unset=True)
            )
        )
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except PhotoNotFoundError:
        raise _404("photo_not_found", "Photo not found")


@router.delete("/{id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_photo(id: UUID, photo_id: UUID, svc: _Svc):
    try:
        svc.delete_photo(id, photo_id)
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except PhotoNotFoundError:
        raise _404("photo_not_found", "Photo not found")


@router.patch("/{id}/photos/{photo_id}/thumbnail", response_model=PhotoResponse)
def set_provider_thumbnail(id: UUID, photo_id: UUID, svc: _Svc):
    try:
        return PhotoResponse.model_validate(svc.set_thumbnail(id, photo_id))
    except ProviderNotFoundError:
        raise _404("provider_not_found", "Provider not found")
    except PhotoNotFoundError:
        raise _404("photo_not_found", "Photo not found")
