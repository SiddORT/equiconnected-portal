from datetime import date, timedelta

import pytest
from sqlalchemy import event, func, text
from sqlalchemy.orm import Session

from scripts.seed_dubai_providers import (
    DEMO_EMERGENCY_PHONE, LISTINGS, SPECIALIZATIONS, DemoSeedError, main, seed,
)
from app.models.enums import (
    DoctorAvailability, ProviderStatus, ProviderType, PublicationStatus, VisitStability,
)
from app.models.provider import DoctorVisit, Provider, ProviderEmail, ProviderLocation, ProviderPhone
from app.models.specialization import Specialization
from app.schemas.provider import DoctorVisitRequired

ANCHOR = date(2026, 10, 13)


def test_all_types_locations_specializations_visits_and_emergencies(db):
    counts = seed(db, start_date=ANCHOR)
    db.commit()
    db.expire_all()
    assert counts == {"providers": 9, "skipped": 0, "specializations": 7,
                      "locations": 9, "visits": 2, "emergency_providers": 6}
    providers = db.query(Provider).all()
    for kind in ProviderType:
        assert sum(p.provider_type == kind for p in providers) == 3
        assert sum(p.provider_type == kind and p.emergency_services_available for p in providers) == 2
    assert len({(p.locations[0].latitude, p.locations[0].longitude) for p in providers}) == 9
    for provider in providers:
        assert provider.status == ProviderStatus.ACTIVE
        assert provider.publication_status == PublicationStatus.PUBLISHED
        assert provider.provider_specializations
        assert all(link.specialization.is_active for link in provider.provider_specializations)
        assert len(provider.locations) == 1 and provider.locations[0].is_primary
        assert provider.locations[0].city == "Dubai"
        assert provider.locations[0].country == "United Arab Emirates"
        assert len(provider.emails) == len(provider.phones) == 1
        assert provider.emails[0].is_primary and provider.emails[0].email.endswith("@example.com")
        assert provider.phones[0].is_primary and provider.phones[0].number == "000000000"
        if provider.emergency_services_available:
            assert provider.emergency_contact_number == DEMO_EMERGENCY_PHONE
        if provider.provider_type == ProviderType.DOCTOR:
            assert provider.doctor_profile.first_name
            assert "Fictional" in provider.doctor_profile.biography
        else:
            assert provider.doctor_availability is None and not provider.doctor_visits
    visiting = [p for p in providers if p.doctor_availability == DoctorAvailability.VISITING]
    assert len(visiting) == 2
    trips = sorted((p.doctor_visits[0] for p in visiting), key=lambda trip: trip.start_date)
    assert trips[0].start_date <= ANCHOR <= trips[0].end_date
    assert trips[1].start_date == ANCHOR + timedelta(days=14)
    for trip in trips:
        assert DoctorVisitRequired.model_validate(trip, from_attributes=True).location.city == "Dubai"
    # Raw storage must use the configured encryption, never plaintext dummy contacts.
    raw_email = db.execute(text("SELECT email FROM provider_emails LIMIT 1")).scalar_one()
    raw_emergency = db.execute(text(
        "SELECT emergency_contact_number FROM providers "
        "WHERE emergency_services_available IS TRUE LIMIT 1"
    )).scalar_one()
    assert "@example.com" not in raw_email
    assert DEMO_EMERGENCY_PHONE not in raw_emergency


def test_rerun_preserves_edits_and_does_not_duplicate(db):
    seed(db, start_date=ANCHOR)
    db.commit()
    provider = db.get(Provider, LISTINGS[-1].id)
    provider.name = "Administrator renamed this demo"
    provider.publication_status = PublicationStatus.UNPUBLISHED
    provider.emergency_services_available = True
    provider.locations[0].name = "Edited location"
    provider.doctor_visits[0].end_date += timedelta(days=3)
    db.commit()
    saved_end = provider.doctor_visits[0].end_date
    counts = seed(db, start_date=ANCHOR + timedelta(days=100))
    db.commit()
    assert counts["skipped"] == 9
    assert all(value == 0 for key, value in counts.items() if key != "skipped")
    assert db.query(Provider).count() == 9
    assert db.query(ProviderLocation).count() == 9
    assert db.query(ProviderEmail).count() == db.query(ProviderPhone).count() == 9
    assert db.query(DoctorVisit).count() == 2
    assert provider.name == "Administrator renamed this demo"
    assert provider.publication_status == PublicationStatus.UNPUBLISHED
    assert provider.emergency_services_available
    assert provider.locations[0].name == "Edited location"
    assert provider.doctor_visits[0].end_date == saved_end


def test_existing_master_reused_without_editing_unrelated_provider(db):
    spec = Specialization(name=SPECIALIZATIONS[0].upper(), is_active=True)
    db.add(spec)
    db.add(Provider(name="Existing unrelated hospital", provider_type=ProviderType.HOSPITAL,
                    visit_stability=VisitStability.NOT_STABLE_VISIT,
                    status=ProviderStatus.INACTIVE, publication_status=PublicationStatus.UNPUBLISHED))
    db.commit()
    counts = seed(db, start_date=ANCHOR)
    db.commit()
    assert counts["specializations"] == 6
    assert db.query(Specialization).count() == 7
    assert db.query(Specialization).filter(func.lower(Specialization.name) ==
                                         SPECIALIZATIONS[0].lower()).one().id == spec.id
    existing = db.query(Provider).filter(Provider.name == "Existing unrelated hospital").one()
    assert existing.status == ProviderStatus.INACTIVE
    assert existing.publication_status == PublicationStatus.UNPUBLISHED
    assert not existing.locations and not existing.provider_specializations


def test_inactive_specialization_rolls_back_entire_seed(db):
    db.add(Specialization(name=SPECIALIZATIONS[-1], is_active=False))
    db.commit()
    with pytest.raises(DemoSeedError, match="inactive"):
        seed(db, start_date=ANCHOR)
    db.rollback()
    assert db.query(Provider).count() == 0
    assert db.query(Specialization).count() == 1
    assert not db.query(Specialization).one().is_active


def test_failed_encryption_preflight_has_no_database_writes(db, monkeypatch):
    from scripts import seed_dubai_providers as module
    from app.services.contact_encryption import ContactEncryptionUnavailable

    def unavailable():
        raise ContactEncryptionUnavailable("test_unavailable")

    monkeypatch.setattr(module, "ensure_contact_encryption_available", unavailable)
    with pytest.raises(ContactEncryptionUnavailable):
        seed(db, start_date=ANCHOR)
    assert db.query(Provider).count() == db.query(Specialization).count() == 0


def test_preview_does_not_run_encryption_or_database_checks(monkeypatch, capsys):
    from scripts import seed_dubai_providers as module

    def forbidden():
        raise AssertionError("Preview must not attempt preflight or DB writes")

    monkeypatch.setattr(module, "ensure_contact_encryption_available", forbidden)
    assert main(["--start-date", ANCHOR.isoformat()]) == 0
    output = capsys.readouterr().out
    assert "Preview only" in output
    assert "visiting 2026-10-11 to 2026-10-20" in output
    assert "visiting 2026-10-27 to 2026-11-05" in output


def test_apply_command_commits_to_the_configured_session(db, monkeypatch, capsys):
    from app.db import session as session_module

    monkeypatch.setattr(session_module, "SessionLocal", lambda: Session(db.get_bind()))
    assert main(["--apply", "--start-date", ANCHOR.isoformat()]) == 0
    assert db.query(Provider).count() == 9
    assert "Dubai demo seed committed" in capsys.readouterr().out
    db.rollback()
    assert main(["--apply", "--start-date", ANCHOR.isoformat()]) == 0
    assert "'skipped': 9" in capsys.readouterr().out
    assert db.query(Provider).count() == 9


def test_apply_failure_rolls_back_all_inserts_and_does_not_log_payload(db, monkeypatch, capsys):
    from app.db import session as session_module

    monkeypatch.setattr(session_module, "SessionLocal", lambda: Session(db.get_bind()))

    def reject_last_provider(mapper, connection, target):
        if target.id == LISTINGS[-1].id:
            raise RuntimeError("example_sensitive_error_payload")

    event.listen(Provider, "before_insert", reject_last_provider)
    try:
        assert main(["--apply", "--start-date", ANCHOR.isoformat()]) == 1
    finally:
        event.remove(Provider, "before_insert", reject_last_provider)
    assert db.query(Provider).count() == 0
    assert db.query(Specialization).count() == 0
    assert db.query(ProviderLocation).count() == db.query(DoctorVisit).count() == 0
    output = capsys.readouterr()
    assert "Seed failed (RuntimeError)" in output.err
    assert "example_sensitive_error_payload" not in output.err + output.out
