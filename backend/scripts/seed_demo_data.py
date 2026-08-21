"""
Rerunnable development demo-data seed.

Usage:
    cd backend
    python scripts/seed_demo_data.py

Creates a small set of active specializations plus active, published
hospitals, clinics, and doctors with primary geocoded Dubai locations.
Idempotent: seed identities are matched by (provider_type, name) for
providers, by name for specializations, and by provider/location name for
locations — reruns create nothing new and do not touch unrelated or
user-edited records.

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

# name, type, specializations,
# (location name, address, city, state, country, postal, lat, lon)
PROVIDERS = [
    (
        "Dubai Demo Crescent Harbor Hospital", ProviderType.HOSPITAL,
        ["Cardiology", "Oncology", "Pediatrics"],
        ("Dubai Marina Campus", "88 Crescent Harbor Walk", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.080600"), Decimal("55.142400")),
    ),
    (
        "Dubai Demo Oasis Meridian Hospital", ProviderType.HOSPITAL,
        ["Neurology", "Orthopedics"],
        ("Jumeirah Campus", "17 Oasis Meridian Road", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.204800"), Decimal("55.238800")),
    ),
    (
        "Dubai Demo Skyline Gate Hospital", ProviderType.HOSPITAL,
        ["Cardiology", "Pediatrics", "Dermatology"],
        ("Mirdif Campus", "42 Skyline Gate Avenue", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.220800"), Decimal("55.420900")),
    ),
    (
        "Dubai Demo Pearl Family Clinic", ProviderType.CLINIC,
        ["Pediatrics", "Dermatology"],
        ("Downtown Dubai Suite", "6 Pearl Family Lane", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.197200"), Decimal("55.274400")),
    ),
    (
        "Dubai Demo Barsha Horizon Clinic", ProviderType.CLINIC,
        ["Dermatology", "Orthopedics"],
        ("Al Barsha Suite", "31 Barsha Horizon Street", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.112400"), Decimal("55.200300")),
    ),
    (
        "Dubai Demo Creekside Wellness Clinic", ProviderType.CLINIC,
        ["Neurology", "Cardiology"],
        ("Deira Wellness Center", "9 Creekside Crescent", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.266700"), Decimal("55.316700")),
    ),
    (
        "Dr. Layla Meridian (Dubai Demo)", ProviderType.DOCTOR,
        ["Cardiology"],
        ("Business Bay Consultation Room", "24 Meridian Quay", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.185100"), Decimal("55.263200")),
    ),
    (
        "Dr. Sami Crescent (Dubai Demo)", ProviderType.DOCTOR,
        ["Neurology"],
        ("Dubai Marina Consultation Room", "12 Crescent Marina Promenade", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.077200"), Decimal("55.140300")),
    ),
    (
        "Dr. Hana Bloom (Dubai Demo)", ProviderType.DOCTOR,
        ["Pediatrics"],
        ("Jumeirah Consultation Room", "28 Bloom Garden Road", "Dubai", "Dubai",
         "United Arab Emirates", "00000", Decimal("25.206000"), Decimal("55.245000")),
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
                ProviderLocation.name == loc_name,
            )
            .first()
        )
        # The address/city fallback keeps reruns idempotent for locations
        # created by an earlier version of this script.
        if existing_loc is None:
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
