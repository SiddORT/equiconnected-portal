"""Provider discovery, member reviews, and administrator moderation coverage."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

from app.api.v1.member_providers import _contact
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.repositories.review_repository import ReviewRepository
from app.schemas.provider import ProviderListItem, ProviderResponse
from tests.conftest import TestingSessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import (
    DoctorAvailability,
    ProviderReviewStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.provider import (
    DoctorVisit,
    Provider,
    ProviderEmail,
    ProviderLocation,
    ProviderPhone,
    ProviderPhoto,
    ProviderReview,
    ProviderSpecialization,
)
from app.models.provider_review_action import ProviderReviewAction
from app.models.doctor import DoctorProfile, DoctorQualification
from app.models.language import Language, ProviderLanguage
from app.models.specialization import Specialization
from app.repositories.user_repository import UserRepository

MEMBER_BASE = "/api/v1/member/providers"
ADMIN_BASE = "/api/v1/admin/reviews"


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _member(db, email: str):
    repo = UserRepository(db)
    role = repo.get_role_by_name("horse_owner") or repo.create_role("horse_owner")
    user = repo.create_user(
        email=email,
        password_hash=hash_password("MemberPassword1"),
        role=role,
        roles=[role],
        first_name=email.split("@")[0].title(),
        last_name="Member",
    )
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return user


def _provider(
    db,
    name: str,
    *,
    provider_type=ProviderType.CLINIC,
    status=ProviderStatus.ACTIVE,
    publication=PublicationStatus.PUBLISHED,
    latitude: str | None = "30.267200",
    longitude: str | None = "-97.743100",
    maximum_working_radius_km: str | None = None,
    years_experience: int | None = None,
):
    provider = Provider(
        provider_type=provider_type,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
        status=status,
        publication_status=publication,
        description=f"{name} description",
        years_experience=years_experience,
        maximum_working_radius_km=(
            Decimal(maximum_working_radius_km) if maximum_working_radius_km is not None else None
        ),
    )
    db.add(provider)
    db.flush()
    if latitude is not None and longitude is not None:
        db.add(
            ProviderLocation(
                provider_id=provider.id,
                address_line_1="1 Stable Lane",
                city="Austin",
                country="United States",
                latitude=Decimal(latitude),
                longitude=Decimal(longitude),
                is_primary=True,
            )
        )
    db.commit()
    return provider


class TestMemberProviderDiscoveryAndReviews:
    @pytest.mark.parametrize("same_created_at", [False, True])
    def test_contact_fallback_survives_fresh_sessions_and_non_primary_edits(
        self, client, db, monkeypatch, same_created_at
    ):
        member = _member(db, "ordered-contacts@example.com")
        provider = _provider(db, "Ordered Contacts")
        provider.phone = "legacy phone"
        provider.email = "legacy@example.com"
        provider_id = provider.id
        headers = _headers(member)
        oldest = datetime(2020, 1, 1, tzinfo=timezone.utc)
        newer = oldest if same_created_at else datetime(2021, 1, 1, tzinfo=timezone.utc)
        # Insert the losing contact first. Equal timestamps must use the ID,
        # not insertion order or the database's physical row order.
        phone_ids = [UUID(int=2), UUID(int=1)]
        email_ids = [UUID(int=4), UUID(int=3)]
        for index, created_at in enumerate((newer, oldest)):
            db.add_all([
                ProviderPhone(
                    id=phone_ids[index], provider_id=provider_id,
                    country_code="+1", number=f"512555010{index}",
                    created_at=created_at, is_primary=False,
                ),
                ProviderEmail(
                    id=email_ids[index], provider_id=provider_id,
                    email=f"contact{index}@example.com",
                    created_at=created_at, is_primary=False,
                ),
            ])
            db.flush()
        db.commit()

        def fresh_db():
            with TestingSessionLocal() as session:
                yield session

        monkeypatch.setitem(app.dependency_overrides, get_db, fresh_db)
        expected_phone = "+1 5125550101"
        expected_email = "contact1@example.com"

        def assert_contacts():
            # Each request below has its own session, as does each explicit
            # reload. Check eager API loads and lazy relationship loads.
            for _ in range(2):
                with TestingSessionLocal() as session:
                    loaded = session.get(Provider, provider_id)
                    assert [row.id for row in loaded.phones] == phone_ids[::-1]
                    assert [row.id for row in loaded.emails] == email_ids[::-1]
                    assert all(not row.is_primary for row in loaded.phones + loaded.emails)
                    assert loaded.phone == "legacy phone"
                    assert loaded.email == "legacy@example.com"
                    assert loaded.phones[0].created_at == oldest
                    assert loaded.emails[0].created_at == oldest
                    item = ProviderListItem.from_provider_row(loaded)
                    assert (item.phone, item.email) == (expected_phone, expected_email)
                    detail = ProviderResponse.from_provider(loaded)
                    assert [row.id for row in detail.phones] == phone_ids[::-1]
                    assert [row.id for row in detail.emails] == email_ids[::-1]
                    # Serializers must agree even before ORM ordering is applied.
                    reversed_contacts = SimpleNamespace(
                        phones=loaded.phones[::-1], emails=loaded.emails[::-1],
                        phone=loaded.phone, email=loaded.email,
                    )
                    assert _contact(reversed_contacts, "phone") == expected_phone
                    assert _contact(reversed_contacts, "email") == expected_email

                directory = client.get(MEMBER_BASE, headers=headers)
                assert directory.status_code == 200
                item = directory.json()["data"][0]
                assert (item["phone"], item["email"]) == (expected_phone, expected_email)
                detail = client.get(f"{MEMBER_BASE}/{provider_id}", headers=headers)
                assert detail.status_code == 200
                assert (detail.json()["phone"], detail.json()["email"]) == (
                    expected_phone, expected_email,
                )

        assert_contacts()
        # Updating the newer non-primary contact must not change selection.
        with TestingSessionLocal() as session:
            session.get(ProviderPhone, phone_ids[0]).number = "5125559999"
            session.get(ProviderEmail, email_ids[0]).email = "changed-newer@example.com"
            session.commit()
        assert_contacts()
        # Updating the selected non-primary contact changes the displayed value,
        # but not its fallback rank (updated_at is deliberately irrelevant).
        with TestingSessionLocal() as session:
            session.get(ProviderPhone, phone_ids[1]).number = "5125558888"
            session.get(ProviderEmail, email_ids[1]).email = "changed-oldest@example.com"
            session.commit()
        expected_phone = "+1 5125558888"
        expected_email = "changed-oldest@example.com"
        assert_contacts()

    def test_directory_and_detail_select_persisted_contacts(self, client, db, seeded_admin):
        member = _member(db, "contacts-member@example.com")
        primary = _provider(db, "Contact Primary")
        fallback = _provider(db, "Contact Fallback")
        legacy = _provider(db, "Contact Legacy")
        absent = _provider(db, "Contact Absent")
        hidden = _provider(db, "Contact Draft", publication=PublicationStatus.UNPUBLISHED)
        inactive = _provider(db, "Contact Inactive", status=ProviderStatus.INACTIVE)
        for provider in (primary, fallback, legacy):
            provider.phone = "legacy phone"
            provider.email = "legacy@example.com"
        # Flush each first contact separately so the primary is not the first
        # stored record. These are real ORM children, not serializer mocks.
        for provider in (primary, fallback, hidden, inactive):
            db.add_all([
                ProviderPhone(provider_id=provider.id, country_code="+1", number="5125550100"),
                ProviderEmail(provider_id=provider.id, email="first@example.com"),
            ])
            db.flush()
            db.add_all([
                ProviderPhone(
                    provider_id=provider.id, country_code="+971", number="501234567",
                    is_primary=provider == primary,
                ),
                ProviderEmail(
                    provider_id=provider.id, email="selected@example.com",
                    is_primary=provider == primary,
                ),
            ])
        db.commit()
        db.expire_all()
        headers = _headers(member)
        expected = {
            str(primary.id): ("+971 501234567", "selected@example.com"),
            str(fallback.id): ("+1 5125550100", "first@example.com"),
            str(legacy.id): ("legacy phone", "legacy@example.com"),
            str(absent.id): (None, None),
        }
        directory = client.get(MEMBER_BASE, headers=headers)
        assert directory.status_code == 200
        assert directory.json()["meta"]["total"] == 4
        assert {
            row["id"]: (row["phone"], row["email"])
            for row in directory.json()["data"]
        } == expected
        for provider_id, contacts in expected.items():
            detail = client.get(f"{MEMBER_BASE}/{provider_id}", headers=headers)
            assert detail.status_code == 200
            assert (detail.json()["phone"], detail.json()["email"]) == contacts

        filtered = client.get(MEMBER_BASE, headers=headers, params={"name": "Contact Primary"})
        assert filtered.status_code == 200
        assert [row["id"] for row in filtered.json()["data"]] == [str(primary.id)]
        assert client.put(f"{MEMBER_BASE}/{primary.id}/favorite", headers=headers).status_code == 204
        saved = client.get(MEMBER_BASE, headers=headers, params={"saved_only": True})
        assert saved.status_code == 200
        assert [(row["id"], row["phone"], row["email"], row["is_saved"])
                for row in saved.json()["data"]] == [
            (str(primary.id), "+971 501234567", "selected@example.com", True),
        ]
        for provider in (hidden, inactive):
            assert client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers).status_code == 404
        admin, _ = seeded_admin
        for url in (MEMBER_BASE, f"{MEMBER_BASE}/{primary.id}"):
            assert client.get(url).status_code == 401
            assert client.get(url, headers=_headers(admin)).status_code == 403
        member.email_verified_at = None
        db.commit()
        for url in (MEMBER_BASE, f"{MEMBER_BASE}/{primary.id}"):
            assert client.get(url, headers=headers).status_code == 403

    def test_member_detail_exposes_only_ordered_safe_profile_data(self, client, db):
        member = _member(db, "profile-details@example.com")
        doctor = _provider(
            db,
            "Profile Doctor",
            provider_type=ProviderType.DOCTOR,
            maximum_working_radius_km="75.50",
        )
        doctor.professional_title = None
        doctor.clinic_hospital_visit = True
        doctor.emergency_services_available = True
        doctor.doctor_availability = DoctorAvailability.VISITING
        db.add(
            DoctorProfile(
                provider_id=doctor.id,
                professional_title="Equine Veterinarian",
                biography="A member-safe professional biography.",
                years_experience=0,
                experience_description="Private experience note",
            )
        )
        db.add_all(
            [
                DoctorQualification(
                    provider_id=doctor.id,
                    title="Advanced Equine Care",
                    institution="North College",
                    year_obtained=2022,
                    description="Second",
                    display_order=2,
                ),
                DoctorQualification(
                    provider_id=doctor.id,
                    title="Doctor of Veterinary Medicine",
                    institution="South College",
                    year_obtained=2018,
                    description="First",
                    display_order=1,
                ),
                ProviderPhoto(
                    provider_id=doctor.id,
                    storage_reference="/uploads/providers/second.jpg",
                    alt_text="Second profile photo",
                    caption="Second",
                    display_order=2,
                ),
                ProviderPhoto(
                    provider_id=doctor.id,
                    storage_reference="/uploads/providers/first.jpg",
                    alt_text="First profile photo",
                    caption="First",
                    display_order=1,
                    is_thumbnail=True,
                ),
            ]
        )
        primary_location = db.query(ProviderLocation).filter_by(provider_id=doctor.id).one()
        primary_location.address_line_1 = "Private Street Address"
        primary_location.state_province = "Texas"
        primary_location.postal_code = "78701"
        db.add(
            ProviderLocation(
                provider_id=doctor.id,
                address_line_1="Another Private Street",
                city="San Antonio",
                state_province="Texas",
                country="United States",
                postal_code="78201",
                is_primary=False,
            )
        )
        english = Language(name="English", code="en")
        spanish = Language(name="Spanish", code="es")
        db.add_all([english, spanish])
        db.flush()
        db.add_all(
            [
                ProviderLanguage(provider_id=doctor.id, language_id=english.id),
                ProviderLanguage(provider_id=doctor.id, language_id=spanish.id),
                DoctorVisit(
                    provider_id=doctor.id,
                    location={
                        "name": "Private Visit Site",
                        "address_line_1": "Private Visit Street",
                        "address_line_2": "Private Suite",
                        "city": "Dallas",
                        "state_province": "Texas",
                        "country": "United States",
                        "postal_code": "75001",
                        "latitude": 32.7767,
                        "longitude": -96.7970,
                        "is_primary": True,
                    },
                    start_date=date(2030, 4, 3),
                    end_date=date(2030, 4, 8),
                ),
            ]
        )
        db.commit()

        headers = _headers(member)
        detail_url = f"{MEMBER_BASE}/{doctor.id}"
        assert client.get(detail_url).status_code == 401
        response = client.get(detail_url, headers=headers)
        assert response.status_code == 200
        payload = response.json()

        assert payload["biography"] == "A member-safe professional biography."
        assert payload["professional_title"] == "Equine Veterinarian"
        assert payload["experience_description"] == "Private experience note"
        # A legacy doctor_profile value is used when the newer provider field is null;
        # zero years is a real value, not a missing-value sentinel.
        assert payload["years_experience"] == 0
        assert payload["qualifications"] == [
            {
                "title": "Doctor of Veterinary Medicine",
                "institution": "South College",
                "year_obtained": 2018,
                "description": "First",
                "display_order": 1,
            },
            {
                "title": "Advanced Equine Care",
                "institution": "North College",
                "year_obtained": 2022,
                "description": "Second",
                "display_order": 2,
            },
        ]
        assert payload["photos"] == [
            {
                "url": "/uploads/providers/first.jpg",
                "alt_text": "First profile photo",
                "caption": "First",
                "display_order": 1,
                "is_thumbnail": True,
            },
            {
                "url": "/uploads/providers/second.jpg",
                "alt_text": "Second profile photo",
                "caption": "Second",
                "display_order": 2,
                "is_thumbnail": False,
            },
        ]
        assert payload["languages"] == [
            {"name": "English", "code": "en"},
            {"name": "Spanish", "code": "es"},
        ]
        assert payload["locations"] == [
            {
                "city": "Austin",
                "state_province": "Texas",
                "country": "United States",
                "is_primary": True,
            },
            {
                "city": "San Antonio",
                "state_province": "Texas",
                "country": "United States",
                "is_primary": False,
            },
        ]
        assert payload["maximum_working_radius_km"] == 75.5
        assert payload["clinic_hospital_visit"] is True
        assert payload["emergency_services_available"] is True
        assert payload["doctor_availability"] == "VISITING"
        assert payload["doctor_visits"] == [
            {
                "start_date": "2030-04-03",
                "end_date": "2030-04-08",
                "location": {
                    "city": "Dallas",
                    "state_province": "Texas",
                    "country": "United States",
                },
            }
        ]
        assert "Private Street Address" not in response.text
        assert "Private Visit Street" not in response.text
        assert "Private Suite" not in response.text
        assert "75001" not in response.text
        assert "32.7767" not in response.text
        assert "emergency_contact" not in response.text

    def test_member_detail_keeps_discoverability_boundary_and_non_doctor_empty_data(
        self, client, db, seeded_admin
    ):
        member = _member(db, "detail-boundary@example.com")
        visible = _provider(db, "Detail Visible Clinic", years_experience=9)
        unpublished = _provider(
            db, "Detail Draft Clinic", publication=PublicationStatus.UNPUBLISHED
        )
        inactive = _provider(
            db, "Detail Inactive Clinic", status=ProviderStatus.INACTIVE
        )
        admin, _ = seeded_admin
        headers = _headers(member)

        assert client.get(
            f"{MEMBER_BASE}/{visible.id}", headers=_headers(admin)
        ).status_code == 403
        assert client.get(f"{MEMBER_BASE}/{unpublished.id}", headers=headers).status_code == 404
        assert client.get(f"{MEMBER_BASE}/{inactive.id}", headers=headers).status_code == 404
        payload = client.get(f"{MEMBER_BASE}/{visible.id}", headers=headers).json()
        assert payload["years_experience"] == 9
        assert payload["biography"] is None
        assert payload["professional_title"] is None
        assert payload["qualifications"] == []
        assert payload["photos"] == []
        assert payload["languages"] == []
        assert payload["doctor_availability"] is None
        assert payload["doctor_visits"] == []

    def test_name_search_combines_filters_count_sort_and_pages_without_exposing_hidden_rows(self, client, db):
        member = _member(db, "directory-name@example.com")
        alpha = _provider(db, "Alpha Equine Care")
        beta = _provider(db, "Beta Equine Care")
        _provider(db, "Equine Draft", publication=PublicationStatus.UNPUBLISHED)
        _provider(db, "Equine Inactive", status=ProviderStatus.INACTIVE)
        _provider(db, "Other Clinic")
        headers = _headers(member)

        params = {"name": "  eQuInE  ", "provider_type": "CLINIC", "sort": "name", "page_size": 1}
        first = client.get(MEMBER_BASE, headers=headers, params=params)
        assert first.status_code == 200
        assert first.json()["meta"]["total"] == 2
        assert first.json()["meta"]["total_pages"] == 2
        assert [item["id"] for item in first.json()["data"]] == [str(alpha.id)]
        second = client.get(MEMBER_BASE, headers=headers, params={**params, "page": 2})
        assert second.json()["meta"]["total"] == 2
        assert [item["id"] for item in second.json()["data"]] == [str(beta.id)]

        empty = client.get(MEMBER_BASE, headers=headers, params={"name": "no such provider"})
        assert empty.json()["meta"]["total"] == 0
        assert empty.json()["data"] == []
        cleared = client.get(MEMBER_BASE, headers=headers, params={"name": "   "})
        assert cleared.json()["meta"]["total"] == 3
        assert client.get(MEMBER_BASE, headers=headers, params={"name": "%"}).json()["meta"]["total"] == 0
        assert client.get(MEMBER_BASE, headers=headers, params={"name": "_"}).json()["meta"]["total"] == 0

        member.email_verified_at = None
        db.commit()
        assert client.get(MEMBER_BASE, headers=headers, params=params).status_code == 403
        assert client.get(MEMBER_BASE, params=params).status_code == 401

    def test_member_favorites_are_private_persistent_and_discoverable_only(self, client, db):
        first = _member(db, "favorites-first@example.com")
        second = _member(db, "favorites-second@example.com")
        visible = _provider(db, "Saved Clinic")
        hidden = _provider(db, "Unpublished Clinic", publication=PublicationStatus.UNPUBLISHED)
        url = f"{MEMBER_BASE}/{visible.id}/favorite"
        first_headers = _headers(first)
        second_headers = _headers(second)

        assert client.put(url).status_code == 401
        assert client.put(f"{MEMBER_BASE}/{hidden.id}/favorite", headers=first_headers).status_code == 404
        assert client.put(url, headers=first_headers).status_code == 204
        assert client.put(url, headers=first_headers).status_code == 204
        assert client.get(f"{MEMBER_BASE}/{visible.id}", headers=first_headers).json()["is_saved"] is True
        saved = client.get(f"{MEMBER_BASE}?saved_only=true", headers=first_headers)
        assert saved.status_code == 200
        assert saved.json()["meta"]["total"] == 1
        assert [entry["id"] for entry in saved.json()["data"]] == [str(visible.id)]
        assert saved.json()["data"][0]["is_saved"] is True
        assert client.get(f"{MEMBER_BASE}?saved_only=true", headers=second_headers).json()["data"] == []
        assert client.get(f"{MEMBER_BASE}/{visible.id}", headers=second_headers).json()["is_saved"] is False

        visible.publication_status = PublicationStatus.UNPUBLISHED
        db.commit()
        assert client.get(f"{MEMBER_BASE}?saved_only=true", headers=first_headers).json()["data"] == []
        assert client.put(url, headers=first_headers).status_code == 404
        assert client.delete(url, headers=first_headers).status_code == 204
        visible.publication_status = PublicationStatus.PUBLISHED
        db.commit()
        assert client.get(f"{MEMBER_BASE}?saved_only=true", headers=first_headers).json()["data"] == []
        assert client.delete(url, headers=first_headers).status_code == 204

    def test_directory_facets_filters_sort_and_pages_use_published_data(self, client, db):
        member = _member(db, "directory-facets@example.com")
        a = _provider(db, "Alpha Stable")
        b = _provider(db, "Beta Stable")
        hidden = _provider(db, "Hidden Stable", publication=PublicationStatus.UNPUBLISHED)
        other = _provider(db, "Other Clinic")
        other.visit_stability = VisitStability.NOT_STABLE_VISIT
        a.emergency_services_available = True
        b.emergency_services_available = True
        hidden.emergency_services_available = True
        spec = Specialization(name="Real Specialty", is_active=True)
        hidden_spec = Specialization(name="Hidden Specialty", is_active=True)
        db.add_all([spec, hidden_spec])
        db.flush()
        for provider in (a, b, hidden):
            db.add(ProviderSpecialization(
                provider_id=provider.id,
                specialization_id=spec.id if provider != hidden else hidden_spec.id,
            ))
            location = db.query(ProviderLocation).filter_by(provider_id=provider.id).one()
            location.state_province = "Texas"
        db.commit()
        headers = _headers(member)
        assert client.get(f"{MEMBER_BASE}/filters").status_code == 401
        facets = client.get(f"{MEMBER_BASE}/filters", headers=headers).json()
        assert facets == {
            "specializations": [{"id": str(spec.id), "name": "Real Specialty"}],
            "regions": ["Texas"],
        }
        params = {
            "visit_stability": "STABLE_VISIT",
            "specialization_id": str(spec.id),
            "region": "texas",
            "emergency_only": "true",
            "sort": "name",
            "page_size": 1,
        }
        first = client.get(MEMBER_BASE, headers=headers, params=params)
        assert first.status_code == 200
        assert first.json()["meta"]["total"] == 2
        assert first.json()["meta"]["total_pages"] == 2
        assert first.json()["data"][0]["name"] == "Alpha Stable"
        assert first.json()["data"][0]["specializations"] == ["Real Specialty"]
        assert first.json()["data"][0]["emergency_services_available"] is True
        second = client.get(MEMBER_BASE, headers=headers, params={**params, "page": 2})
        assert second.json()["data"][0]["name"] == "Beta Stable"
        no_match = client.get(MEMBER_BASE, headers=headers, params={**params, "provider_type": "DOCTOR"})
        assert no_match.json()["meta"]["total"] == 0
        assert no_match.json()["data"] == []
        assert client.get(MEMBER_BASE, headers=headers, params={"sort": "invalid"}).status_code == 422

    def test_public_discovery_is_anonymous_bounded_and_coordinate_safe(self, client, db):
        reviewer = _member(db, "public-reviewer@example.com")
        visible = _provider(db, "Public Equine Doctor", provider_type=ProviderType.DOCTOR)
        _provider(db, "Draft Map Provider", publication=PublicationStatus.UNPUBLISHED)
        _provider(db, "Inactive Map Provider", status=ProviderStatus.INACTIVE)
        _provider(db, "Unlocated Map Provider", latitude=None, longitude=None)
        specialization = Specialization(name="Sports Medicine", is_active=True)
        db.add(specialization)
        db.flush()
        visible_location = (
            db.query(ProviderLocation)
            .filter(ProviderLocation.provider_id == visible.id)
            .one()
        )
        visible_location.is_primary = False
        db.add_all(
            [
                ProviderLocation(
                    provider_id=visible.id,
                    address_line_1="Private primary address",
                    city="Private Primary City",
                    country="United States",
                    latitude=None,
                    longitude=None,
                    is_primary=True,
                ),
                ProviderSpecialization(
                    provider_id=visible.id,
                    specialization_id=specialization.id,
                ),
                ProviderReview(
                    provider_id=visible.id,
                    member_id=reviewer.id,
                    rating=5,
                    comment="Excellent",
                    status=ProviderReviewStatus.PUBLISHED,
                ),
            ]
        )
        db.commit()

        response = client.get("/api/v1/public/providers")

        assert response.status_code == 200
        assert len(response.json()) == 1
        item = response.json()[0]
        assert item["id"] == str(visible.id)
        assert item["specializations"] == ["Sports Medicine"]
        assert item["average_rating"] == 5.0
        assert item["review_count"] == 1
        assert item["location"] == {
            "city": "Austin",
            "state_province": None,
            "country": "United States",
            "latitude": 30.2672,
            "longitude": -97.7431,
        }
        assert "email" not in item
        assert "phone" not in item

        nearby = client.get(
            "/api/v1/public/providers",
            params={"latitude": 30.2672, "longitude": -97.7431},
        )
        assert nearby.status_code == 200
        assert nearby.json()[0]["distance_km"] == 0.0
        assert client.get(
            "/api/v1/public/providers",
            params={"latitude": 30.2672},
        ).status_code == 422

    def test_directory_has_member_boundary_and_only_published_active_providers(
        self, client, db, seeded_admin
    ):
        member = _member(db, "member@example.com")
        visible = _provider(db, "Visible Clinic")
        _provider(db, "Draft Clinic", publication=PublicationStatus.UNPUBLISHED)
        _provider(db, "Inactive Clinic", status=ProviderStatus.INACTIVE)

        assert client.get(MEMBER_BASE).status_code == 401
        admin, _ = seeded_admin
        assert client.get(MEMBER_BASE, headers=_headers(admin)).status_code == 403

        response = client.get(MEMBER_BASE, headers=_headers(member))
        assert response.status_code == 200
        payload = response.json()
        assert [item["id"] for item in payload["data"]] == [str(visible.id)]
        assert payload["data"][0]["review_count"] == 0
        assert payload["data"][0]["average_rating"] is None

    def test_filters_closest_order_and_unlocated_provider_fallback(self, client, db):
        member = _member(db, "sort@example.com")
        nearby = _provider(db, "Nearby Clinic", provider_type=ProviderType.CLINIC)
        far = _provider(
            db, "Far Hospital", provider_type=ProviderType.HOSPITAL,
            latitude="35.084400", longitude="-106.650400",
        )
        unlocated = _provider(db, "Unlocated Clinic", latitude=None, longitude=None)
        db.add_all([
            ProviderReview(provider_id=nearby.id, member_id=member.id, rating=5, comment="Great", status=ProviderReviewStatus.PUBLISHED),
            ProviderReview(provider_id=far.id, member_id=member.id, rating=3, comment="Fine", status=ProviderReviewStatus.PUBLISHED),
        ])
        db.commit()

        filtered = client.get(
            MEMBER_BASE,
            headers=_headers(member),
            params={"provider_type": "CLINIC", "minimum_rating": 4},
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()["data"]] == [str(nearby.id)]

        closest = client.get(
            MEMBER_BASE,
            headers=_headers(member),
            params={"closest_first": "true", "latitude": 30.2672, "longitude": -97.7431},
        )
        assert closest.status_code == 200
        items = closest.json()["data"]
        assert [item["id"] for item in items] == [str(nearby.id), str(far.id), str(unlocated.id)]
        assert items[0]["distance_km"] == 0.0
        assert items[-1]["distance_km"] is None
        assert client.get(
            MEMBER_BASE, headers=_headers(member), params={"closest_first": "true"}
        ).status_code == 422

    def test_working_radius_filter_uses_provider_radius_and_pages_db_filtered_results(
        self, client, db
    ):
        member = _member(db, "radius@example.com")
        nearby = _provider(db, "Nearby Stable", maximum_working_radius_km="40")
        outside = _provider(
            db,
            "Outside Stable",
            latitude="31.000000",
            longitude="-97.743100",
            maximum_working_radius_km="10",
        )
        second_nearby = _provider(db, "Second Stable", maximum_working_radius_km="1")
        missing_radius = _provider(db, "Missing Radius")
        zero_radius = _provider(db, "Zero Radius", maximum_working_radius_km="0")
        exact_boundary = _provider(
            db,
            "Equatorial Boundary",
            provider_type=ProviderType.HOSPITAL,
            latitude="31.267200",
            longitude="-97.743100",
            maximum_working_radius_km="111.20",
        )
        unusable_location = _provider(
            db,
            "Unusable Location",
            latitude="91.000000",
            longitude="0.000000",
            maximum_working_radius_km="500",
        )
        _provider(
            db,
            "Inactive Radius Provider",
            status=ProviderStatus.INACTIVE,
            maximum_working_radius_km="40",
        )
        _provider(
            db,
            "Unpublished Radius Provider",
            publication=PublicationStatus.UNPUBLISHED,
            maximum_working_radius_km="40",
        )
        _provider(
            db,
            "Unstable Nearby",
            maximum_working_radius_km="40",
        ).visit_stability = VisitStability.NOT_STABLE_VISIT
        db.add(
            ProviderReview(provider_id=nearby.id, member_id=member.id, rating=5, comment="Great", status=ProviderReviewStatus.PUBLISHED)
        )
        db.add(
            ProviderReview(
                provider_id=second_nearby.id, member_id=member.id, rating=2, comment="Okay",
                status=ProviderReviewStatus.PUBLISHED,
            )
        )
        db.commit()
        headers = _headers(member)

        for params in (
            {"within_working_radius": "true"},
            {"within_working_radius": "true", "latitude": 30.2672},
        ):
            assert client.get(MEMBER_BASE, headers=headers, params=params).status_code == 422

        response = client.get(
            MEMBER_BASE,
            headers=headers,
            params={
                "within_working_radius": "true",
                "latitude": 30.2672,
                "longitude": -97.7431,
                "page": 1,
                "page_size": 1,
                "provider_type": "CLINIC",
                "minimum_rating": 4,
            },
        )
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 1
        assert response.json()["meta"]["total_pages"] == 1
        assert response.json()["data"][0]["id"] == str(nearby.id)
        assert str(outside.id) not in {item["id"] for item in response.json()["data"]}
        assert str(missing_radius.id) not in {item["id"] for item in response.json()["data"]}
        assert str(zero_radius.id) not in {item["id"] for item in response.json()["data"]}

        # The provider's configured radius, rather than a member-supplied
        # radius, determines eligibility and is applied before pagination.
        unfiltered = client.get(
            MEMBER_BASE,
            headers=headers,
            params={
                "within_working_radius": "true",
                "latitude": 30.2672,
                "longitude": -97.7431,
                "page": 1,
                "page_size": 1,
            },
        )
        assert unfiltered.json()["meta"]["total"] == 3
        assert unfiltered.json()["meta"]["total_pages"] == 3
        assert unfiltered.json()["data"][0]["id"] == str(nearby.id)
        second_page = client.get(
            MEMBER_BASE,
            headers=headers,
            params={
                "within_working_radius": "true",
                "latitude": 30.2672,
                "longitude": -97.7431,
                "page": 2,
                "page_size": 1,
            },
        )
        assert second_page.json()["data"][0]["id"] == str(second_nearby.id)
        third_page = client.get(
            MEMBER_BASE,
            headers=headers,
            params={
                "within_working_radius": "true",
                "latitude": 30.2672,
                "longitude": -97.7431,
                "page": 3,
                "page_size": 1,
            },
        )
        assert third_page.json()["data"][0]["id"] == str(exact_boundary.id)
        assert str(unusable_location.id) not in {
            item["id"] for item in unfiltered.json()["data"]
        }

    def test_directory_uses_selected_thumbnail_and_ordered_photo_fallback(
        self, client, db, seeded_admin
    ):
        member = _member(db, "photos@example.com")
        selected = _provider(db, "Selected Photo Clinic")
        fallback = _provider(db, "Fallback Photo Clinic")
        db.add_all(
            [
                ProviderPhoto(
                    provider_id=selected.id,
                    storage_reference="/uploads/providers/selected.jpg",
                    alt_text="Selected clinic entrance",
                    display_order=4,
                    is_thumbnail=True,
                ),
                ProviderPhoto(
                    provider_id=selected.id,
                    storage_reference="/uploads/providers/earlier.jpg",
                    alt_text="Earlier clinic photo",
                    display_order=1,
                ),
                ProviderPhoto(
                    provider_id=fallback.id,
                    storage_reference="/uploads/providers/fallback.jpg",
                    alt_text="Fallback clinic photo",
                    display_order=2,
                ),
                ProviderPhoto(
                    provider_id=fallback.id,
                    storage_reference="/uploads/providers/first.jpg",
                    alt_text=None,
                    display_order=1,
                ),
            ]
        )
        db.commit()

        response = client.get(MEMBER_BASE, headers=_headers(member))

        assert response.status_code == 200
        items = {item["name"]: item for item in response.json()["data"]}
        assert items["Selected Photo Clinic"]["thumbnail_url"] == "/uploads/providers/selected.jpg"
        assert items["Selected Photo Clinic"]["thumbnail_alt_text"] == "Selected clinic entrance"
        assert items["Fallback Photo Clinic"]["thumbnail_url"] == "/uploads/providers/first.jpg"
        assert items["Fallback Photo Clinic"]["thumbnail_alt_text"] is None
        admin, password = seeded_admin
        token = client.post("/api/v1/auth/login", json={"email": admin.email, "password": password}).json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {token}"}
        admin_items = {item["name"]: item for item in client.get(
            "/api/v1/admin/providers", headers=admin_headers,
        ).json()["data"]}
        for name, provider in [("Selected Photo Clinic", selected), ("Fallback Photo Clinic", fallback)]:
            detail = client.get(f"/api/v1/admin/providers/{provider.id}", headers=admin_headers).json()
            assert detail["thumbnail_url"] == admin_items[name]["thumbnail_url"] == items[name]["thumbnail_url"]

    def test_member_can_upsert_one_review_and_hidden_comments_are_not_public(
        self, client, db, seeded_admin
    ):
        reviewer = _member(db, "reviewer@example.com")
        provider = _provider(db, "Review Clinic", years_experience=14)
        headers = _headers(reviewer)

        created = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 4, "comment": "Caring team"},
        )
        assert created.status_code == 200
        assert created.json()["status"] == "PENDING"
        assert created.json()["version"] == 1
        retry = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 4, "comment": "Caring team"},
        )
        assert retry.status_code == 200
        assert retry.json()["id"] == created.json()["id"]
        assert retry.json()["version"] == created.json()["version"]
        assert db.query(ProviderReviewAction).filter_by(
            review_id=UUID(created.json()["id"])
        ).count() == 1
        no_version_edit = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 3, "comment": "Different content without a version"},
        )
        assert no_version_edit.status_code == 409
        updated = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={
                "rating": 5,
                "comment": "Even better on our second visit",
                "expected_version": created.json()["version"],
            },
        )
        assert updated.status_code == 200
        assert db.query(ProviderReview).count() == 1
        assert db.query(ProviderReview).one().rating == 5
        assert updated.json()["status"] == "PENDING"
        assert client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 6, "comment": "Nope"},
        ).status_code == 422

        detail = client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["review_count"] == 0
        assert detail.json()["average_rating"] is None
        assert detail.json()["years_experience"] == 14
        assert detail.json()["visible_reviews"] == []

        admin, _ = seeded_admin
        review_id = updated.json()["id"]
        unapproved_hide = client.patch(
            f"{ADMIN_BASE}/{review_id}/status",
            headers=_headers(admin),
            json={"status": "HIDDEN", "expected_version": updated.json()["version"]},
        )
        assert unapproved_hide.status_code == 409
        assert client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers).json()["review_count"] == 0
        denied = client.patch(
            f"{ADMIN_BASE}/{review_id}/comment-visibility",
            headers=headers,
            json={"comment_visible": False},
        )
        assert denied.status_code == 403
        published = client.patch(
            f"{ADMIN_BASE}/{review_id}/status",
            headers=_headers(admin),
            json={
                "status": "PUBLISHED",
                "expected_version": updated.json()["version"],
                "member_note": "Thank you for sharing your experience.",
                "internal_note": "Reviewed against moderation guidelines.",
            },
        )
        assert published.status_code == 200
        assert published.json()["status"] == "PUBLISHED"
        assert published.json()["version"] == 3
        detail = client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers).json()
        assert detail["review_count"] == 1
        assert detail["average_rating"] == 5.0
        assert detail["visible_reviews"][0]["comment"] == "Even better on our second visit"
        assert detail["own_review"]["member_note"] == "Thank you for sharing your experience."
        published_retry = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 5, "comment": "Even better on our second visit"},
        )
        assert published_retry.status_code == 200
        assert published_retry.json()["status"] == "PUBLISHED"
        assert published_retry.json()["version"] == published.json()["version"]
        assert published_retry.json()["member_note"] == "Thank you for sharing your experience."
        own_card = client.get(f"/api/v1/member/reviews/{review_id}", headers=headers)
        assert own_card.status_code == 200
        assert "internal_note" not in own_card.json()

        hidden = client.patch(
            f"{ADMIN_BASE}/{review_id}/comment-visibility",
            headers=_headers(admin),
            json={"comment_visible": False, "expected_version": published.json()["version"]},
        )
        assert hidden.status_code == 200
        assert hidden.json()["comment_visible"] is False
        assert hidden.json()["comment"] == "Even better on our second visit"

        after_hide = client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers).json()
        assert after_hide["review_count"] == 1
        assert after_hide["average_rating"] == 5.0
        assert after_hide["visible_reviews"] == []
        assert after_hide["own_review"]["comment"] == "Even better on our second visit"
        hidden_edit = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={
                "rating": 1,
                "comment": "Trying to bypass moderation",
                "expected_version": hidden.json()["version"],
            },
        )
        assert hidden_edit.status_code == 409
        moderation = client.get(
            ADMIN_BASE, headers=_headers(admin), params={"comment_visible": "false"}
        )
        assert moderation.status_code == 200
        assert moderation.json()["data"][0]["id"] == review_id

        restored = client.patch(
            f"{ADMIN_BASE}/{review_id}/comment-visibility",
            headers=_headers(admin),
            json={"comment_visible": True, "expected_version": hidden.json()["version"]},
        )
        assert restored.status_code == 200
        assert client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers).json()["visible_reviews"][0]["comment"]

        history = client.get(f"{ADMIN_BASE}/{review_id}", headers=_headers(admin))
        assert history.status_code == 200
        actions = history.json()["history"]
        assert [action["action"] for action in actions] == [
            "member_submitted",
            "member_edited",
            "admin_published",
            "admin_hidden",
            "admin_published",
        ]
        assert actions[1]["content_snapshot"]["comment"] == "Even better on our second visit"
        assert actions[2]["content_snapshot"]["member_note"] == "Thank you for sharing your experience."
        assert actions[2]["content_snapshot"]["internal_note"] == "Reviewed against moderation guidelines."
        assert actions[2]["actor_name"] == admin.full_name
        assert actions[2]["actor_email"] == admin.email

        events = db.query(AuditLog).filter(AuditLog.resource_id == review_id).all()
        assert events
        assert all("Caring team" not in str(event.event_metadata) for event in events)

    def test_member_review_ownership_stale_writes_and_soft_deletion_history(
        self, client, db, seeded_admin
    ):
        owner = _member(db, "lifecycle-owner@example.com")
        other = _member(db, "lifecycle-other@example.com")
        admin, _ = seeded_admin
        provider = _provider(db, "Lifecycle Clinic")
        headers = _headers(owner)
        created = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 4, "comment": "Keep the original account of my visit"},
        )
        assert created.status_code == 200
        review_id = created.json()["id"]

        listing = client.get("/api/v1/member/reviews", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["meta"]["total"] == 1
        assert listing.json()["data"][0]["id"] == review_id
        assert listing.json()["data"][0]["status"] == "PENDING"
        assert client.get(
            f"/api/v1/member/reviews/{review_id}", headers=_headers(other)
        ).status_code == 404
        assert client.put(
            f"/api/v1/member/reviews/{review_id}",
            headers=_headers(other),
            json={"rating": 1, "comment": "Not mine", "expected_version": 1},
        ).status_code == 404
        assert client.delete(
            f"/api/v1/member/reviews/{review_id}",
            headers=_headers(other),
            params={"expected_version": 1},
        ).status_code == 404

        stale_edit = client.put(
            f"/api/v1/member/reviews/{review_id}",
            headers=headers,
            json={"rating": 3, "comment": "Stale write", "expected_version": 8},
        )
        assert stale_edit.status_code == 409
        edited = client.put(
            f"/api/v1/member/reviews/{review_id}",
            headers=headers,
            json={
                "rating": 5,
                "comment": "The current version",
                "expected_version": created.json()["version"],
            },
        )
        assert edited.status_code == 200
        assert edited.json()["status"] == "PENDING"
        deleted = client.delete(
            f"/api/v1/member/reviews/{review_id}",
            headers=headers,
            params={"expected_version": edited.json()["version"]},
        )
        assert deleted.status_code == 204
        assert client.get("/api/v1/member/reviews", headers=headers).json()["meta"]["total"] == 0

        # A new active review is allowed, while the deleted record and its
        # attributable action snapshots remain available to administrators.
        replacement = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 2, "comment": "A fresh review"},
        )
        assert replacement.status_code == 200
        assert replacement.json()["id"] != review_id
        admin_detail = client.get(f"{ADMIN_BASE}/{review_id}", headers=_headers(admin))
        assert admin_detail.status_code == 200
        payload = admin_detail.json()
        assert payload["deleted_at"] is not None
        assert payload["comment"] == "The current version"
        assert payload["history"][-1]["action"] == "member_deleted"
        assert payload["history"][-1]["content_snapshot"]["comment"] == "The current version"
        assert payload["history"][-1]["actor_name"] == owner.full_name
        assert payload["history"][-1]["actor_email"] == owner.email

    def test_reviews_cannot_target_an_undiscoverable_provider(self, client, db):
        member = _member(db, "missing@example.com")
        unavailable = _provider(db, "Unpublished Clinic", publication=PublicationStatus.UNPUBLISHED)
        response = client.put(
            f"{MEMBER_BASE}/{unavailable.id}/review",
            headers=_headers(member),
            json={"rating": 4, "comment": "Cannot submit"},
        )
        assert response.status_code == 404

    def test_simultaneous_first_reviews_use_one_atomic_upsert(self, db):
        member = _member(db, "concurrent@example.com")
        provider = _provider(db, "Concurrent Clinic")
        provider_id = provider.id
        member_id = member.id
        barrier = Barrier(2)

        def submit():
            session = TestingSessionLocal()
            try:
                barrier.wait(timeout=5)
                review, _ = ReviewRepository(session).save_member_review(
                    provider_id,
                    member_id,
                    rating=4,
                    comment="Idempotent concurrent submission",
                    expected_version=None,
                )
                if review is None:
                    session.rollback()
                    return None
                session.commit()
                return review.id
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            review_ids = list(pool.map(lambda _index: submit(), [1, 2]))

        assert review_ids[0] == review_ids[1]
        assert db.query(ProviderReview).count() == 1
        assert db.query(ProviderReview).one().rating == 4
        assert db.query(ProviderReview).one().status == ProviderReviewStatus.PENDING

    def test_conflicting_concurrent_first_write_does_not_overwrite_moderation(
        self, db
    ):
        member = _member(db, "moderation-race@example.com")
        provider = _provider(db, "Moderation Race Clinic")
        existing = ProviderReview(
            provider_id=provider.id,
            member_id=member.id,
            rating=5,
            comment="Submitted content",
            status=ProviderReviewStatus.PUBLISHED,
            member_note="Approved note",
            internal_note="Moderator-only note",
            version=2,
        )
        db.add(existing)
        db.commit()

        session = TestingSessionLocal()
        try:
            repository = ReviewRepository(session)
            original_get = repository.get_member_review
            read_count = 0

            def simulate_stale_initial_read(provider_id, member_id):
                nonlocal read_count
                read_count += 1
                if read_count == 1:
                    return None
                return original_get(provider_id, member_id)

            repository.get_member_review = simulate_stale_initial_read
            retried, created = repository.save_member_review(
                provider.id,
                member.id,
                rating=5,
                comment="Submitted content",
                expected_version=None,
            )
            assert retried is not None
            assert created is False
            session.commit()
        finally:
            session.close()

        db.refresh(existing)
        assert existing.status == ProviderReviewStatus.PUBLISHED
        assert existing.version == 2
        assert existing.member_note == "Approved note"
        assert existing.internal_note == "Moderator-only note"

    def test_admin_provider_list_summaries_include_hidden_comments(self, client, db, seeded_admin):
        admin, _ = seeded_admin
        reviewed = _provider(db, "Reviewed Clinic")
        no_reviews = _provider(db, "No Reviews Clinic")
        visible_reviewer = _member(db, "visible-summary@example.com")
        hidden_reviewer = _member(db, "hidden-summary@example.com")
        db.add_all([
            ProviderReview(
                provider_id=reviewed.id,
                member_id=visible_reviewer.id,
                rating=5,
                comment="Visible feedback",
                comment_visible=True,
                status=ProviderReviewStatus.PUBLISHED,
            ),
            ProviderReview(
                provider_id=reviewed.id,
                member_id=hidden_reviewer.id,
                rating=3,
                comment="Hidden feedback",
                comment_visible=False,
                status=ProviderReviewStatus.HIDDEN,
            ),
        ])
        db.commit()

        response = client.get("/api/v1/admin/providers", headers=_headers(admin))
        assert response.status_code == 200
        providers = {item["id"]: item for item in response.json()["data"]}
        assert providers[str(reviewed.id)]["review_count"] == 2
        assert providers[str(reviewed.id)]["average_rating"] == 4.0
        assert providers[str(no_reviews.id)]["review_count"] == 0
        assert providers[str(no_reviews.id)]["average_rating"] is None

    def test_admin_reviews_can_be_scoped_to_a_provider_and_moderated(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        provider = _provider(db, "Scoped Clinic")
        other_provider = _provider(db, "Other Clinic")
        first_reviewer = _member(db, "first-scoped@example.com")
        second_reviewer = _member(db, "second-scoped@example.com")
        other_reviewer = _member(db, "other-scoped@example.com")
        visible_review = ProviderReview(
            provider_id=provider.id,
            member_id=first_reviewer.id,
            rating=5,
            comment="Visible scoped comment",
            comment_visible=True,
            status=ProviderReviewStatus.PUBLISHED,
        )
        hidden_review = ProviderReview(
            provider_id=provider.id,
            member_id=second_reviewer.id,
            rating=2,
            comment="Hidden scoped comment",
            comment_visible=False,
            status=ProviderReviewStatus.HIDDEN,
        )
        db.add_all([
            visible_review,
            hidden_review,
            ProviderReview(
                provider_id=other_provider.id,
                member_id=other_reviewer.id,
                rating=4,
                comment="Other provider comment",
                status=ProviderReviewStatus.PUBLISHED,
            ),
        ])
        db.commit()

        params = {"provider_id": str(provider.id), "page": 1, "page_size": 1}
        assert client.get(ADMIN_BASE, params=params).status_code == 401
        assert client.get(ADMIN_BASE, headers=_headers(first_reviewer), params=params).status_code == 403

        first_page = client.get(ADMIN_BASE, headers=_headers(admin), params=params)
        assert first_page.status_code == 200
        assert first_page.json()["meta"] == {
            "page": 1,
            "page_size": 1,
            "total": 2,
            "total_pages": 2,
        }
        assert first_page.json()["data"][0]["provider_id"] == str(provider.id)
        second_page = client.get(
            ADMIN_BASE,
            headers=_headers(admin),
            params={**params, "page": 2},
        )
        assert second_page.json()["data"][0]["provider_id"] == str(provider.id)

        hidden_only = client.get(
            ADMIN_BASE,
            headers=_headers(admin),
            params={"provider_id": str(provider.id), "comment_visible": "false"},
        )
        assert hidden_only.json()["meta"]["total"] == 1
        assert hidden_only.json()["data"][0]["id"] == str(hidden_review.id)

        updated = client.patch(
            f"{ADMIN_BASE}/{visible_review.id}/comment-visibility",
            headers=_headers(admin),
            json={"comment_visible": False, "expected_version": visible_review.version},
        )
        assert updated.status_code == 200
        assert updated.json()["rating"] == 5
        assert updated.json()["comment_visible"] is False
        db.refresh(visible_review)
        assert visible_review.rating == 5
