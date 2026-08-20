"""
ProviderRepository — data-access layer for healthcare providers and their
locations, photos, and specialization assignments.
"""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import (
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.doctor import DoctorProfile
from app.models.provider import (
    Provider,
    ProviderEmail,
    ProviderLocation,
    ProviderPhone,
    ProviderPhoto,
    ProviderSpecialization,
)
from app.models.specialization import Specialization


class ProviderRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Provider reads ────────────────────────────────────────────────────────

    def get_by_id(self, id: UUID) -> Provider | None:
        return self._db.scalar(
            select(Provider)
            .where(Provider.id == id)
            .options(
                selectinload(Provider.doctor_profile),
                selectinload(Provider.locations),
                selectinload(Provider.photos),
                selectinload(Provider.phones),
                selectinload(Provider.emails),
                selectinload(Provider.provider_specializations).selectinload(
                    ProviderSpecialization.specialization
                ),
            )
        )

    def list(
        self,
        *,
        search: str | None = None,
        provider_type: ProviderType | None = None,
        visit_stability: VisitStability | None = None,
        status: ProviderStatus | None = None,
        publication_status: PublicationStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Provider], int]:
        """Return (items, total_count) for the requested page — all filters at the DB level."""
        stmt = select(Provider).options(
            selectinload(Provider.phones),
            selectinload(Provider.emails),
            selectinload(Provider.photos),
        )
        count_stmt = select(func.count()).select_from(Provider)

        conditions = []
        if search:
            conditions.append(Provider.name.ilike(f"%{search.strip()}%"))
        if provider_type is not None:
            conditions.append(Provider.provider_type == provider_type)
        if visit_stability is not None:
            conditions.append(Provider.visit_stability == visit_stability)
        if status is not None:
            conditions.append(Provider.status == status)
        if publication_status is not None:
            conditions.append(Provider.publication_status == publication_status)

        for cond in conditions:
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        total: int = self._db.scalar(count_stmt) or 0

        stmt = (
            stmt.order_by(Provider.name, Provider.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self._db.scalars(stmt).all())
        return items, total

    # ── Provider writes ───────────────────────────────────────────────────────

    def create(self, **fields) -> Provider:
        provider = Provider(**fields)
        self._db.add(provider)
        self._db.flush()
        return provider

    def update(self, provider: Provider, update_fields: dict) -> Provider:
        for key, value in update_fields.items():
            setattr(provider, key, value)
        self._db.flush()
        return provider

    # ── Doctor profile sub-operations ─────────────────────────────────────────

    def get_doctor_profile(self, provider_id: UUID) -> DoctorProfile | None:
        return self._db.get(DoctorProfile, provider_id)

    def upsert_doctor_profile(self, provider_id: UUID, fields: dict) -> DoctorProfile:
        """Create or update the 1:1 DoctorProfile row for a provider."""
        profile = self.get_doctor_profile(provider_id)
        if profile is None:
            profile = DoctorProfile(provider_id=provider_id, **fields)
            self._db.add(profile)
        else:
            for key, value in fields.items():
                setattr(profile, key, value)
        self._db.flush()
        return profile

    # ── Specialization sub-operations ─────────────────────────────────────────

    def get_specialization(self, spec_id: UUID) -> Specialization | None:
        return self._db.get(Specialization, spec_id)

    def get_assignment(
        self, provider_id: UUID, spec_id: UUID
    ) -> ProviderSpecialization | None:
        return self._db.get(ProviderSpecialization, (provider_id, spec_id))

    def add_specialization(
        self, provider_id: UUID, spec_id: UUID
    ) -> ProviderSpecialization:
        link = ProviderSpecialization(
            provider_id=provider_id, specialization_id=spec_id
        )
        self._db.add(link)
        self._db.flush()
        return link

    def remove_specialization(self, link: ProviderSpecialization) -> None:
        self._db.delete(link)
        self._db.flush()

    # ── Location sub-operations ───────────────────────────────────────────────

    def get_location(self, provider_id: UUID, loc_id: UUID) -> ProviderLocation | None:
        return self._db.scalar(
            select(ProviderLocation).where(
                ProviderLocation.id == loc_id,
                ProviderLocation.provider_id == provider_id,
            )
        )

    def add_location(self, provider_id: UUID, **fields) -> ProviderLocation:
        loc = ProviderLocation(provider_id=provider_id, **fields)
        self._db.add(loc)
        self._db.flush()
        return loc

    def delete_location(self, loc: ProviderLocation) -> None:
        self._db.delete(loc)
        self._db.flush()

    def clear_primary_location(self, provider_id: UUID) -> None:
        """Clear the is_primary flag on every location of the provider."""
        for loc in self._db.scalars(
            select(ProviderLocation).where(
                ProviderLocation.provider_id == provider_id,
                ProviderLocation.is_primary.is_(True),
            )
        ):
            loc.is_primary = False
        self._db.flush()

    # ── Photo sub-operations ──────────────────────────────────────────────────

    def get_photo(self, provider_id: UUID, photo_id: UUID) -> ProviderPhoto | None:
        return self._db.scalar(
            select(ProviderPhoto).where(
                ProviderPhoto.id == photo_id,
                ProviderPhoto.provider_id == provider_id,
            )
        )

    def add_photo(self, provider_id: UUID, **fields) -> ProviderPhoto:
        photo = ProviderPhoto(provider_id=provider_id, **fields)
        self._db.add(photo)
        self._db.flush()
        return photo

    def delete_photo(self, photo: ProviderPhoto) -> None:
        self._db.delete(photo)
        self._db.flush()

    def clear_thumbnail(self, provider_id: UUID) -> None:
        """Clear the is_thumbnail flag on every photo of the provider."""
        for photo in self._db.scalars(
            select(ProviderPhoto).where(
                ProviderPhoto.provider_id == provider_id,
                ProviderPhoto.is_thumbnail.is_(True),
            )
        ):
            photo.is_thumbnail = False
        self._db.flush()

    # ── Phone sub-operations ──────────────────────────────────────────────────

    def get_phone(self, provider_id: UUID, phone_id: UUID) -> ProviderPhone | None:
        return self._db.scalar(
            select(ProviderPhone).where(
                ProviderPhone.id == phone_id,
                ProviderPhone.provider_id == provider_id,
            )
        )

    def add_phone(self, provider_id: UUID, **fields) -> ProviderPhone:
        phone = ProviderPhone(provider_id=provider_id, **fields)
        self._db.add(phone)
        self._db.flush()
        return phone

    def delete_phone(self, phone: ProviderPhone) -> None:
        self._db.delete(phone)
        self._db.flush()

    def clear_primary_phone(self, provider_id: UUID) -> None:
        """Clear the is_primary flag on every phone of the provider."""
        for phone in self._db.scalars(
            select(ProviderPhone).where(
                ProviderPhone.provider_id == provider_id,
                ProviderPhone.is_primary.is_(True),
            )
        ):
            phone.is_primary = False
        self._db.flush()

    # ── Email sub-operations ──────────────────────────────────────────────────

    def get_email(self, provider_id: UUID, email_id: UUID) -> ProviderEmail | None:
        return self._db.scalar(
            select(ProviderEmail).where(
                ProviderEmail.id == email_id,
                ProviderEmail.provider_id == provider_id,
            )
        )

    def add_email(self, provider_id: UUID, **fields) -> ProviderEmail:
        email = ProviderEmail(provider_id=provider_id, **fields)
        self._db.add(email)
        self._db.flush()
        return email

    def delete_email(self, email: ProviderEmail) -> None:
        self._db.delete(email)
        self._db.flush()

    def clear_primary_email(self, provider_id: UUID) -> None:
        """Clear the is_primary flag on every email of the provider."""
        for email in self._db.scalars(
            select(ProviderEmail).where(
                ProviderEmail.provider_id == provider_id,
                ProviderEmail.is_primary.is_(True),
            )
        ):
            email.is_primary = False
        self._db.flush()

    # ── Transaction helpers ───────────────────────────────────────────────────

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()

    def flush(self) -> None:
        self._db.flush()
