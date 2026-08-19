"""
Doctor management endpoints (admin only).

GET    /api/v1/admin/doctors                                  — list
POST   /api/v1/admin/doctors                                  — create
GET    /api/v1/admin/doctors/{id}                             — detail
PATCH  /api/v1/admin/doctors/{id}                             — update profile fields
PATCH  /api/v1/admin/doctors/{id}/status                      — toggle status
PATCH  /api/v1/admin/doctors/{id}/publication                 — toggle publication
POST   /api/v1/admin/doctors/{id}/specializations             — assign spec
DELETE /api/v1/admin/doctors/{id}/specializations/{spec_id}   — unassign spec
POST   /api/v1/admin/doctors/{id}/qualifications              — add qualification
PATCH  /api/v1/admin/doctors/{id}/qualifications/{q_id}       — update qualification
DELETE /api/v1/admin/doctors/{id}/qualifications/{q_id}       — delete qualification
POST   /api/v1/admin/doctors/{id}/organizations               — add org relationship
PATCH  /api/v1/admin/doctors/{id}/organizations/{rel_id}      — update relationship
DELETE /api/v1/admin/doctors/{id}/organizations/{rel_id}      — remove relationship
"""
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.models.enums import ProviderStatus, ProviderType, PublicationStatus, VisitStability
from app.repositories.doctor_repository import DoctorRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.doctor import (
    DoctorCreate,
    DoctorListItem,
    DoctorOrgCreate,
    DoctorOrgResponse,
    DoctorOrgUpdate,
    DoctorResponse,
    DoctorUpdate,
    QualificationCreate,
    QualificationResponse,
    QualificationUpdate,
)
from app.services.doctor_service import (
    DoctorNotFoundError,
    DoctorOrgSelfReferenceError,
    DoctorService,
    DuplicateOrgRelationshipError,
    DuplicateSpecializationError,
    OrgNotFoundError,
    OrgRelationshipNotFoundError,
    QualificationNotFoundError,
    SpecializationNotFoundError,
)

router = APIRouter(
    prefix="/admin/doctors",
    tags=["Admin — Doctors"],
    dependencies=[Depends(require_role("admin"))],
)

AdminDep = Depends(require_role("admin"))


def get_svc(db: Annotated[Session, Depends(get_db)]) -> DoctorService:
    return DoctorService(DoctorRepository(db))


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[DoctorListItem])
def list_doctors(
    search: str | None = Query(None),
    specialization_id: UUID | None = Query(None),
    organization_id: UUID | None = Query(None),
    visit_stability: VisitStability | None = Query(None),
    status: ProviderStatus | None = Query(None),
    publication_status: PublicationStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: DoctorService = Depends(get_svc),
):
    doctors, total = svc.list(
        search=search,
        specialization_id=specialization_id,
        organization_id=organization_id,
        visit_stability=visit_stability,
        status=status,
        publication_status=publication_status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=[DoctorListItem.from_doctor(d) for d in doctors],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
def create_doctor(body: DoctorCreate, svc: DoctorService = Depends(get_svc)):
    try:
        doctor = svc.create(
            name=body.name,
            visit_stability=body.visit_stability,
            status=body.status,
            publication_status=body.publication_status,
            website=body.website,
            professional_title=body.professional_title,
            biography=body.biography,
            years_experience=body.years_experience,
            experience_description=body.experience_description,
            specialization_ids=body.specialization_ids,
            organization_ids=body.organization_ids,
            primary_organization_id=body.primary_organization_id,
            phones=body.phones,
            emails=body.emails,
        )
    except SpecializationNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Specialization not found: {e}")
    except OrgNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Organization not found or invalid type: {e}")
    except DuplicateSpecializationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return DoctorResponse.from_doctor(doctor)


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(doctor_id: UUID, svc: DoctorService = Depends(get_svc)):
    try:
        return DoctorResponse.from_doctor(svc.get(doctor_id))
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(doctor_id: UUID, body: DoctorUpdate, svc: DoctorService = Depends(get_svc)):
    try:
        update_fields = body.model_dump(exclude_unset=True)
        doctor = svc.update(doctor_id, update_fields=update_fields)
        return DoctorResponse.from_doctor(doctor)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")


# ── Status / Publication ──────────────────────────────────────────────────────

@router.patch("/{doctor_id}/status", response_model=DoctorResponse)
def set_status(
    doctor_id: UUID,
    body: dict,
    svc: DoctorService = Depends(get_svc),
):
    new_status = body.get("status")
    if new_status not in (s.value for s in ProviderStatus):
        raise HTTPException(status_code=422, detail="Invalid status value")
    try:
        doctor = svc.set_status(doctor_id, status=ProviderStatus(new_status))
        return DoctorResponse.from_doctor(doctor)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")


@router.patch("/{doctor_id}/publication", response_model=DoctorResponse)
def set_publication(
    doctor_id: UUID,
    body: dict,
    svc: DoctorService = Depends(get_svc),
):
    new_pub = body.get("publication_status")
    if new_pub not in (s.value for s in PublicationStatus):
        raise HTTPException(status_code=422, detail="Invalid publication_status value")
    try:
        doctor = svc.set_publication(doctor_id, publication_status=PublicationStatus(new_pub))
        return DoctorResponse.from_doctor(doctor)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")


# ── Specializations ───────────────────────────────────────────────────────────

@router.post("/{doctor_id}/specializations", response_model=DoctorResponse)
def add_specialization(
    doctor_id: UUID, body: dict, svc: DoctorService = Depends(get_svc)
):
    spec_id = body.get("specialization_id")
    if not spec_id:
        raise HTTPException(status_code=422, detail="specialization_id required")
    try:
        doctor = svc.add_specialization(doctor_id, UUID(str(spec_id)))
        return DoctorResponse.from_doctor(doctor)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")
    except SpecializationNotFoundError:
        raise HTTPException(status_code=404, detail="Specialization not found or inactive")
    except DuplicateSpecializationError:
        raise HTTPException(status_code=409, detail="Specialization already assigned")


@router.delete("/{doctor_id}/specializations/{spec_id}", response_model=DoctorResponse)
def remove_specialization(
    doctor_id: UUID, spec_id: UUID, svc: DoctorService = Depends(get_svc)
):
    try:
        doctor = svc.remove_specialization(doctor_id, spec_id)
        return DoctorResponse.from_doctor(doctor)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")
    except SpecializationNotFoundError:
        raise HTTPException(status_code=404, detail="Specialization not assigned")


# ── Qualifications ────────────────────────────────────────────────────────────

@router.post("/{doctor_id}/qualifications", response_model=QualificationResponse, status_code=201)
def add_qualification(
    doctor_id: UUID, body: QualificationCreate, svc: DoctorService = Depends(get_svc)
):
    try:
        q = svc.add_qualification(doctor_id, fields=body.model_dump())
        return QualificationResponse.model_validate(q)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")


@router.patch("/{doctor_id}/qualifications/{q_id}", response_model=QualificationResponse)
def update_qualification(
    doctor_id: UUID, q_id: UUID, body: QualificationUpdate, svc: DoctorService = Depends(get_svc)
):
    try:
        q = svc.update_qualification(doctor_id, q_id, fields=body.model_dump(exclude_unset=True))
        return QualificationResponse.model_validate(q)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")
    except QualificationNotFoundError:
        raise HTTPException(status_code=404, detail="Qualification not found")


@router.delete("/{doctor_id}/qualifications/{q_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_qualification(
    doctor_id: UUID, q_id: UUID, svc: DoctorService = Depends(get_svc)
):
    try:
        svc.delete_qualification(doctor_id, q_id)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")
    except QualificationNotFoundError:
        raise HTTPException(status_code=404, detail="Qualification not found")


# ── Organization relationships ─────────────────────────────────────────────────

@router.post("/{doctor_id}/organizations", response_model=DoctorResponse, status_code=201)
def add_org_relationship(
    doctor_id: UUID, body: DoctorOrgCreate, svc: DoctorService = Depends(get_svc)
):
    try:
        doctor = svc.add_org_relationship(
            doctor_id,
            organization_id=body.organization_id,
            status=body.status,
            is_primary=body.is_primary,
        )
        return DoctorResponse.from_doctor(doctor)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")
    except OrgNotFoundError:
        raise HTTPException(status_code=404, detail="Organization not found or must be Hospital/Clinic")
    except DoctorOrgSelfReferenceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DuplicateOrgRelationshipError:
        raise HTTPException(status_code=409, detail="Relationship already exists")


@router.patch("/{doctor_id}/organizations/{rel_id}", response_model=DoctorResponse)
def update_org_relationship(
    doctor_id: UUID, rel_id: UUID, body: DoctorOrgUpdate, svc: DoctorService = Depends(get_svc)
):
    try:
        doctor = svc.update_org_relationship(
            doctor_id, rel_id, fields=body.model_dump(exclude_unset=True)
        )
        return DoctorResponse.from_doctor(doctor)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")
    except OrgRelationshipNotFoundError:
        raise HTTPException(status_code=404, detail="Relationship not found")


@router.delete("/{doctor_id}/organizations/{rel_id}", response_model=DoctorResponse)
def remove_org_relationship(
    doctor_id: UUID, rel_id: UUID, svc: DoctorService = Depends(get_svc)
):
    try:
        doctor = svc.remove_org_relationship(doctor_id, rel_id)
        return DoctorResponse.from_doctor(doctor)
    except DoctorNotFoundError:
        raise HTTPException(status_code=404, detail="Doctor not found")
    except OrgRelationshipNotFoundError:
        raise HTTPException(status_code=404, detail="Relationship not found")
