"""
Rerunnable development demo-data seed.

Usage:
    cd backend
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --city mumbai

Creates a small set of active specializations plus active, published
hospitals, clinics, and doctors with primary geocoded Dubai (default) or
Mumbai locations. Both catalogues are fictional and additive.
Idempotent: seed identities are matched by (provider_type, name) for
providers, by name for specializations, and by provider/location name for
locations — reruns create nothing new and do not touch unrelated or
user-edited records.

No secrets are used or stored by this script.
"""
import argparse
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

MUMBAI_PROVIDERS = [
    (
        "Mumbai Demo Harbor Lantern Hospital", ProviderType.HOSPITAL,
        ["Cardiology", "Oncology", "Pediatrics"],
        ("Colaba Campus", "18 Lantern Quay", "Mumbai", "Maharashtra",
         "India", "400005", Decimal("18.915000"), Decimal("72.826000")),
    ),
    (
        "Mumbai Demo Banyan Arc Hospital", ProviderType.HOSPITAL,
        ["Neurology", "Orthopedics"],
        ("Dadar Campus", "27 Banyan Arc Lane", "Mumbai", "Maharashtra",
         "India", "400014", Decimal("19.018000"), Decimal("72.842000")),
    ),
    (
        "Mumbai Demo Monsoon Vale Hospital", ProviderType.HOSPITAL,
        ["Dermatology", "Pediatrics", "Cardiology"],
        ("Andheri Campus", "44 Monsoon Vale Road", "Mumbai", "Maharashtra",
         "India", "400053", Decimal("19.119000"), Decimal("72.846000")),
    ),
    (
        "Mumbai Demo Seabreeze Family Clinic", ProviderType.CLINIC,
        ["Pediatrics", "Dermatology"],
        ("Bandra Suite", "11 Seabreeze Crescent", "Mumbai", "Maharashtra",
         "India", "400050", Decimal("19.059000"), Decimal("72.830000")),
    ),
    (
        "Mumbai Demo Lotus Crossing Clinic", ProviderType.CLINIC,
        ["Orthopedics", "Neurology"],
        ("Powai Suite", "36 Lotus Crossing", "Mumbai", "Maharashtra",
         "India", "400076", Decimal("19.117000"), Decimal("72.906000")),
    ),
    (
        "Mumbai Demo Coral Grove Clinic", ProviderType.CLINIC,
        ["Cardiology", "Oncology"],
        ("Chembur Suite", "8 Coral Grove Walk", "Mumbai", "Maharashtra",
         "India", "400071", Decimal("19.052000"), Decimal("72.899000")),
    ),
    (
        "Dr. Mira Lantern (Mumbai Demo)", ProviderType.DOCTOR,
        ["Cardiology"],
        ("Worli Consultation Room", "19 Lantern Terrace", "Mumbai", "Maharashtra",
         "India", "400018", Decimal("19.012000"), Decimal("72.817000")),
    ),
    (
        "Dr. Arin Grove (Mumbai Demo)", ProviderType.DOCTOR,
        ["Neurology"],
        ("Juhu Consultation Room", "25 Grove Path", "Mumbai", "Maharashtra",
         "India", "400049", Decimal("19.106000"), Decimal("72.827000")),
    ),
    (
        "Dr. Tara Cove (Mumbai Demo)", ProviderType.DOCTOR,
        ["Pediatrics"],
        ("Goregaon Consultation Room", "7 Cove Lane", "Mumbai", "Maharashtra",
         "India", "400063", Decimal("19.164000"), Decimal("72.849000")),
    ),
]

CATALOGUES = {"dubai": PROVIDERS, "mumbai": MUMBAI_PROVIDERS}


def seed(db, city: str = "dubai") -> dict:
    """Run the idempotent seed against *db*. Returns creation counts."""
    if city not in CATALOGUES:
        raise ValueError(f"Unknown demo city: {city}")
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

    for name, ptype, spec_names, loc in CATALOGUES[city]:
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
    parser = argparse.ArgumentParser(description="Seed a fictional development provider catalogue.")
    parser.add_argument("--city", choices=CATALOGUES, default="dubai")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        created = seed(db, city=args.city)
        logger.info("seed_demo.done", city=args.city, **created)
        print(f"✓ {args.city.title()} demo data seeded: {created}")
    except Exception as exc:
        db.rollback()
        logger.error("seed_demo.failed", error=str(exc))
        print(f"✗ Demo seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
