"""Add fictional Dubai listings without changing existing providers or secrets.

Preview: python backend/scripts/seed_dubai_providers.py
Apply:   python backend/scripts/seed_dubai_providers.py --apply
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.db.base  # noqa: F401, E402 — register all relationships
from app.models.doctor import DoctorProfile  # noqa: E402
from app.models.enums import (  # noqa: E402
    DoctorAvailability, ProviderStatus, ProviderType, PublicationStatus, VisitStability,
)
from app.models.provider import (  # noqa: E402
    DoctorVisit, Provider, ProviderEmail, ProviderLocation, ProviderPhone, ProviderSpecialization,
)
from app.models.specialization import Specialization  # noqa: E402
from app.schemas.provider import LocationCreate  # noqa: E402
from app.services.contact_encryption import (  # noqa: E402
    ContactEncryptionUnavailable, ensure_contact_encryption_available,
)

DEMO_NOTICE = (
    "Fictional Dubai demo listing for website testing only. "
    "Not a real veterinary provider; addresses and contacts are placeholders. "
    "Do not use for emergency care."
)
# Intentionally invalid UAE national number, NOT a real subscriber number.
DEMO_PHONE = "000000000"
DEMO_EMERGENCY_PHONE = "+971 00 000 0000"
SPECIALIZATIONS = (
    "Equine Dentistry", "Equine Orthopedics", "Equine Internal Medicine",
    "Equine Reproduction", "Equine Diagnostic Imaging", "Equine Emergency Care",
    "Equine Sports Medicine",
)


@dataclass(frozen=True)
class DemoListing:
    slug: str
    name: str
    provider_type: ProviderType
    area: str
    latitude: str
    longitude: str
    specialties: tuple[int, ...]
    emergency: bool = False
    visit_offset: int | None = None
    first_name: str | None = None
    last_name: str | None = None

    @property
    def id(self) -> UUID:
        # Never use the editable display name as the seed's identity.
        return uuid5(NAMESPACE_URL, f"equiconnected:demo:dubai:{self.slug}")

    def location(self) -> LocationCreate:
        return LocationCreate(
            name=f"{self.area} demo location",
            address_line_1=f"Fictional demo premises, {self.area}",
            address_line_2="Test address only — not a real practice",
            city="Dubai", state_province="Dubai", country="United Arab Emirates",
            is_primary=True,
            latitude=Decimal(self.latitude), longitude=Decimal(self.longitude),
        )


LISTINGS = (
    DemoListing("marmoom-hospital", "Dubai Demo Al Marmoom Equine Hospital",
                ProviderType.HOSPITAL, "Al Marmoom", "24.981000", "55.361000",
                (1, 4, 5), emergency=True),
    DemoListing("jebel-ali-hospital", "Dubai Demo Jebel Ali Equine Hospital",
                ProviderType.HOSPITAL, "Jebel Ali", "24.985700", "55.027300",
                (2, 3, 5), emergency=True),
    DemoListing("academic-city-hospital", "Dubai Demo Academic City Equine Hospital",
                ProviderType.HOSPITAL, "Dubai Academic City", "25.105000", "55.425000",
                (0, 4, 6)),
    DemoListing("al-quoz-clinic", "Dubai Demo Al Quoz Equine Clinic",
                ProviderType.CLINIC, "Al Quoz", "25.141000", "55.235000",
                (0, 2, 5), emergency=True),
    DemoListing("nad-al-sheba-clinic", "Dubai Demo Nad Al Sheba Equine Clinic",
                ProviderType.CLINIC, "Nad Al Sheba", "25.154000", "55.322000",
                (3, 6)),
    DemoListing("jumeirah-clinic", "Dubai Demo Jumeirah Equine Clinic",
                ProviderType.CLINIC, "Jumeirah", "25.204800", "55.238800",
                (1, 4, 5), emergency=True),
    DemoListing("layla-doctor", "Dr. Layla Demo Meridian (Dubai Demo)",
                ProviderType.DOCTOR, "Emirates Hills", "25.066000", "55.173000",
                (2, 5), emergency=True, first_name="Layla", last_name="Demo Meridian"),
    DemoListing("sami-doctor", "Dr. Sami Demo Crescent (Dubai Demo)",
                ProviderType.DOCTOR, "Meydan", "25.157000", "55.301000",
                (1, 5, 6), emergency=True, visit_offset=-2,
                first_name="Sami", last_name="Demo Crescent"),
    DemoListing("hana-doctor", "Dr. Hana Demo Bloom (Dubai Demo)",
                ProviderType.DOCTOR, "Al Barsha", "25.112400", "55.200300",
                (0, 3), visit_offset=14, first_name="Hana", last_name="Demo Bloom"),
)


class DemoSeedError(RuntimeError):
    """An operator-readable error containing no configuration values."""


def seed(db: Session, *, start_date: date) -> dict[str, int]:
    """Stage the complete seed in the caller's transaction; never commit midway."""
    ensure_contact_encryption_available()
    # Serialize simultaneous VPS invocations, including shared master-data creation.
    db.execute(text("SELECT pg_advisory_xact_lock(194781026, 20261013)"))
    counts = {"providers": 0, "skipped": 0, "specializations": 0,
              "locations": 0, "visits": 0, "emergency_providers": 0}
    pending = []
    for item in LISTINGS:
        if db.get(Provider, item.id) is not None:
            counts["skipped"] += 1
            continue
        if db.query(Provider.id).filter(Provider.name == item.name).first() is not None:
            raise DemoSeedError("A demo display name already exists with a different identity. "
                                "No records were changed; resolve the collision in admin first.")
        pending.append(item)

    specialties = {}
    for index in sorted({index for item in pending for index in item.specialties}):
        name = SPECIALIZATIONS[index]
        spec = db.query(Specialization).filter(
            func.lower(Specialization.name) == name.lower()
        ).first()
        if spec is None:
            spec = Specialization(name=name, is_active=True)
            db.add(spec)
            db.flush()
            counts["specializations"] += 1
        elif not spec.is_active:
            raise DemoSeedError(f"Specialization '{name}' is inactive. Activate it in admin "
                                "before seeding; no records were changed.")
        specialties[index] = spec

    for item in pending:
        doctor = item.provider_type == ProviderType.DOCTOR
        stable_visits = item.provider_type != ProviderType.HOSPITAL
        location = item.location()
        provider = Provider(
            id=item.id, name=item.name, provider_type=item.provider_type,
            description=None if doctor else DEMO_NOTICE,
            status=ProviderStatus.ACTIVE, publication_status=PublicationStatus.PUBLISHED,
            professional_title="Demo Equine Veterinarian" if doctor else None,
            years_experience=12 if doctor else 8,
            visit_stability=(VisitStability.STABLE_VISIT if stable_visits
                             else VisitStability.NOT_STABLE_VISIT),
            maximum_working_radius_km=Decimal("40") if stable_visits else None,
            clinic_hospital_visit=True if doctor else None,
            doctor_availability=(
                DoctorAvailability.VISITING if item.visit_offset is not None
                else DoctorAvailability.ONGOING
            ) if doctor else None,
            emergency_services_available=item.emergency,
            emergency_contact_name="DEMO ONLY — not real emergency care" if item.emergency else None,
            emergency_contact_number=DEMO_EMERGENCY_PHONE if item.emergency else None,
        )
        provider.locations = [ProviderLocation(**location.model_dump())]
        provider.emails = [
            ProviderEmail(email=f"dubai-demo-{item.slug}@example.com", is_primary=True),
        ]
        provider.phones = [
            ProviderPhone(country_code="+971", number=DEMO_PHONE, is_primary=True),
        ]
        provider.provider_specializations = [
            ProviderSpecialization(specialization=specialties[index])
            for index in item.specialties
        ]
        if doctor:
            provider.doctor_profile = DoctorProfile(
                first_name=item.first_name, last_name=item.last_name,
                professional_title="Demo Equine Veterinarian",
                biography=DEMO_NOTICE, years_experience=12,
                experience_description="Synthetic experience for demonstration only.",
            )
        if item.visit_offset is not None:
            visit_start = start_date + timedelta(days=item.visit_offset)
            provider.doctor_visits = [DoctorVisit(
                location=location.model_dump(mode="json"),
                start_date=visit_start, end_date=visit_start + timedelta(days=9),
            )]
            counts["visits"] += 1
        db.add(provider)
        counts["providers"] += 1
        counts["locations"] += 1
        counts["emergency_providers"] += int(item.emergency)
    db.flush()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview or add fictional Dubai provider listings.")
    parser.add_argument("--apply", action="store_true", help="Write demo data to the configured database.")
    parser.add_argument("--start-date", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Asia/Dubai")).date(),
                        help="Visit calendar anchor, YYYY-MM-DD (default: today in Dubai).")
    args = parser.parse_args(argv)
    print(DEMO_NOTICE)
    for item in LISTINGS:
        visit = ""
        if item.visit_offset is not None:
            start = args.start_date + timedelta(days=item.visit_offset)
            visit = f" | visiting {start} to {start + timedelta(days=9)}"
        print(f"{item.provider_type.value}: {item.name} | {item.area}"
              f" | emergency={'demo yes' if item.emergency else 'no'}{visit}")
    if not args.apply:
        print("Preview only: no database access or writes. Add --apply to seed.")
        return 0
    try:
        ensure_contact_encryption_available()
        # Import only after preflight so invalid settings fail safely before DB access.
        from app.db.session import SessionLocal

        with SessionLocal() as db, db.begin():
            counts = seed(db, start_date=args.start_date)
        print(f"Dubai demo seed committed: {counts}")
        print("Reruns skip existing demo IDs, preserving edits and original visit dates.")
        return 0
    except ContactEncryptionUnavailable as exc:
        print(f"Seed blocked: contact encryption unavailable ({exc.reason}). "
              "Run backend/scripts/check_contact_encryption.py; do not replace keys.",
              file=sys.stderr)
    except DemoSeedError as exc:
        print(f"Seed blocked: {exc}", file=sys.stderr)
    except Exception as exc:
        # Never print exception payloads: connection/configuration errors can contain secrets.
        print(f"Seed failed ({type(exc).__name__}); no partial seed was committed. "
              "Check database connectivity and run the existing Alembic upgrade first.",
              file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
