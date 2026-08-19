"""Persistence operations for organization search and doctor requests."""
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.models.doctor import DoctorOrganization
from app.models.enums import (
    OrganizationRequestStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
)
from app.models.organization_request import OrganizationRequest
from app.models.provider import Provider, ProviderLocation


class OrganizationRequestRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def search_organizations(self, *, query: str | None, organization_type: ProviderType | None,
                             page: int, page_size: int) -> tuple[list[tuple[Provider, str | None]], int]:
        types = [organization_type] if organization_type else [ProviderType.HOSPITAL, ProviderType.CLINIC]
        visible_conditions = (
            Provider.provider_type.in_(types),
            Provider.status == ProviderStatus.ACTIVE,
            Provider.publication_status == PublicationStatus.PUBLISHED,
        )
        stmt = (
            select(Provider, func.min(ProviderLocation.city).label("city"))
            .outerjoin(ProviderLocation, ProviderLocation.provider_id == Provider.id)
            .where(*visible_conditions)
            .group_by(Provider.id)
        )
        count_stmt = (
            select(func.count(func.distinct(Provider.id)))
            .select_from(Provider)
            .where(*visible_conditions)
        )
        if query:
            term = f"%{query.strip()}%"
            predicate = or_(Provider.name.ilike(term), ProviderLocation.city.ilike(term))
            stmt = stmt.where(predicate)
            count_stmt = count_stmt.outerjoin(ProviderLocation).where(predicate)
        total = self._db.scalar(count_stmt) or 0
        rows = self._db.execute(
            stmt.order_by(Provider.name, Provider.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [(row[0], row[1]) for row in rows], total

    def duplicate_suggestions(self, name: str, organization_type: ProviderType) -> list[Provider]:
        normalized = " ".join(name.strip().split())
        ilike_match = Provider.name.ilike(f"%{normalized}%")
        trigram_schema = self._db.scalar(
            text(
                """
                SELECT namespace.nspname
                FROM pg_extension extension
                JOIN pg_namespace namespace ON namespace.oid = extension.extnamespace
                WHERE extension.extname = 'pg_trgm'
                """
            )
        )
        stmt = select(Provider).where(Provider.provider_type == organization_type)
        if trigram_schema:
            similarity = getattr(func, trigram_schema).similarity(
                func.lower(Provider.name), normalized.lower()
            )
            stmt = stmt.where(or_(ilike_match, similarity >= 0.3)).order_by(
                similarity.desc(), Provider.name
            )
        else:
            stmt = stmt.where(ilike_match).order_by(Provider.name)
        return list(self._db.scalars(stmt.limit(10)))

    def create(self, **fields) -> OrganizationRequest:
        request = OrganizationRequest(**fields)
        self._db.add(request)
        self._db.flush()
        return request

    def get(self, request_id: UUID) -> OrganizationRequest | None:
        return self._db.scalar(select(OrganizationRequest).where(OrganizationRequest.id == request_id).with_for_update())

    def list(self, *, status: OrganizationRequestStatus | None, organization_type: ProviderType | None,
             page: int, page_size: int) -> tuple[list[OrganizationRequest], int]:
        conditions = []
        if status:
            conditions.append(OrganizationRequest.status == status)
        if organization_type:
            conditions.append(OrganizationRequest.organization_type == organization_type)
        stmt = select(OrganizationRequest).where(*conditions)
        total = self._db.scalar(select(func.count()).select_from(OrganizationRequest).where(*conditions)) or 0
        return list(self._db.scalars(stmt.order_by(OrganizationRequest.created_at.desc()).offset(
            (page - 1) * page_size).limit(page_size))), total

    def get_provider(self, provider_id: UUID) -> Provider | None:
        return self._db.get(Provider, provider_id)

    def get_relationship(self, doctor_id: UUID, organization_id: UUID) -> DoctorOrganization | None:
        return self._db.scalar(select(DoctorOrganization).where(
            DoctorOrganization.doctor_id == doctor_id, DoctorOrganization.organization_id == organization_id
        ))

    def create_provider(self, **fields) -> Provider:
        provider = Provider(**fields)
        self._db.add(provider)
        self._db.flush()
        return provider

    def create_relationship(self, doctor_id: UUID, organization_id: UUID, **fields) -> DoctorOrganization:
        relationship = DoctorOrganization(doctor_id=doctor_id, organization_id=organization_id, **fields)
        self._db.add(relationship)
        self._db.flush()
        return relationship

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()