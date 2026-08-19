"""
Rerunnable development demo-data seed.

Usage:
    cd backend
    python scripts/seed_demo_data.py

Creates a small set of active specializations plus active, published
hospitals, clinics, and doctors with primary geocoded locations.
Idempotent: seed identities are matched by (provider_type, name) for
providers and by name for specializations — reruns create nothing new
and do not touch unrelated or user-edited records.

No secrets are used or stored by this script.
"""
import os
import sys
from decimal import Decimal

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import configure_logging, get_logger  # noqa: E402
import app.db.base  # noqa: F401, E402 — registers all models in the mapper registry
from app.db.session import SessionLocal  # noqa: E402
from app.models.enums import (  # noqa: E402
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.provider import (  # noqa: E402
    Provider,
    ProviderLocation,
    ProviderSpecialization,
)
from app.models.specialization import Specialization  # noqa: E402

configure_logging()
logger = get_logger(__name__)

SPECIALIZATIONS = [
    "Cardiology",
    "Neurology",
    "Orthopedics",
    "Pediatrics",
    "Dermatology",
    "Oncology",
]

# name, type, specializations, (location name, address, city, state, country, postal, lat, lon)
PROVIDERS = [
    (
        "St. Mary's General Hospital", ProviderType.HOSPITAL,
        ["Cardiology", "Oncology", "Pediatrics"],
        ("Main Campus", "450 Stanyan St", "San Francisco", "CA", "USA", "94117",
         Decimal("37.774900"), Decimal("-122.453500")),
    ),
    (
        "Riverside Medical Center", ProviderType.HOSPITAL,
        ["Neurology", "Orthopedics"],
        ("Main Building", "1000 Riverside Dr", "Austin", "TX", "USA", "78704",
         Decimal("30.244500"), Decimal("-97.748400")),
    ),
    (
        "Downtown Family Clinic", ProviderType.CLINIC,
        ["Pediatrics", "Dermatology"],
        ("Suite 200", "88 5th Ave", "New York", "NY", "USA", "10011",
         Decimal("40.736900"), Decimal("-73.993400")),
    ),
    (
        "Lakeview Urgent Care", ProviderType.CLINIC,
        ["Dermatology"],
        ("Front Office", "3210 N Lake Shore Dr", "Chicago", "IL", "USA", "60657",
         Decimal("41.940300"), Decimal("-87.639700")),
    ),
    (
        "Dr. Amelia Hart", ProviderType.DOCTOR,
        ["Cardiology"],
        ("Private Practice", "200 Peachtree St NW", "Atlanta", "GA", "USA", "30303",
         Decimal("33.759100"), Decimal("-84.387900")),
    ),
    (
        "Dr. Samuel Osei", ProviderType.DOCTOR,
        ["Neurology"],
        ("Neurology Office", "1201 3rd Ave", "Seattle", "WA", "USA", "98101",
         Decimal("47.606200"), Decimal("-122.335300")),
    ),
    (
        "Dr. Priya Raman", ProviderType.DOCTOR,
        ["Pediatrics"],
        ("Children's Suite", "600 Congress Ave", "Austin", "TX", "USA", "78701",
         Decimal("30.268200"), Decimal("-97.742800")),
    ),
]


def seed(db) -> dict:
    """Run the idempotent seed against *db*. Returns creation counts."""
    created = {"specializations": 0, "providers": 0, "locations": 0, "assignments": 0}

    specs_by_name: dict[str, Specialization] = {}
    for name in SPECIALIZATIONS:
        spec = db.query(Specialization).filter(Specialization.name == name).first()
        if spec is None:
            spec = Specialization(name=name, is_active=True)
            db.add(spec)
            db.flush()
            created["specializations"] += 1
        specs_by_name[name] = spec

    for name, ptype, spec_names, loc in PROVIDERS:
        provider = (
            db.query(Provider)
            .filter(Provider.provider_type == ptype, Provider.name == name)
            .first()
        )
        if provider is None:
            provider = Provider(
                provider_type=ptype,
                name=name,
                visit_stability=VisitStability.STABLE_VISIT,
                status=ProviderStatus.ACTIVE,
                publication_status=PublicationStatus.PUBLISHED,
            )
            db.add(provider)
            db.flush()
            created["providers"] += 1

        for spec_name in spec_names:
            spec = specs_by_name[spec_name]
            exists = (
                db.query(ProviderSpecialization)
                .filter(
                    ProviderSpecialization.provider_id == provider.id,
                    ProviderSpecialization.specialization_id == spec.id,
                )
                .first()
            )
            if exists is None:
                db.add(
                    ProviderSpecialization(
                        provider_id=provider.id, specialization_id=spec.id
                    )
                )
                created["assignments"] += 1

        loc_name, addr, city, state, country, postal, lat, lon = loc
        existing_loc = (
            db.query(ProviderLocation)
            .filter(
                ProviderLocation.provider_id == provider.id,
                ProviderLocation.address_line_1 == addr,
                ProviderLocation.city == city,
            )
            .first()
        )
        if existing_loc is None:
            has_primary = (
                db.query(ProviderLocation)
                .filter(
                    ProviderLocation.provider_id == provider.id,
                    ProviderLocation.is_primary.is_(True),
                )
                .first()
                is not None
            )
            db.add(
                ProviderLocation(
                    provider_id=provider.id,
                    name=loc_name,
                    address_line_1=addr,
                    city=city,
                    state_province=state,
                    country=country,
                    postal_code=postal,
                    latitude=lat,
                    longitude=lon,
                    is_primary=not has_primary,
                )
            )
            created["locations"] += 1

    db.commit()
    return created


def main() -> None:
    db = SessionLocal()
    try:
        created = seed(db)
        logger.info("seed_demo.done", **created)
        print(f"✓ Demo data seeded: {created}")
    except Exception as exc:
        db.rollback()
        logger.error("seed_demo.failed", error=str(exc))
        print(f"✗ Demo seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
