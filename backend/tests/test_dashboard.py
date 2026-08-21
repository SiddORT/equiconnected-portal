"""
Admin dashboard endpoint + demo seed tests.

Covers:
  - Auth protection (401 unauthenticated, 403 non-admin)
  - Provider-type counting across mixed types
  - Coordinate filtering (locations without lat/lon omitted)
  - Multiple locations per provider
  - Empty-data shape
  - Seed idempotency
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.models.enums import (
    ProviderStatus,
    PublicationStatus,
    ProviderType,
    PublicAccountApprovalStatus,
    VisitStability,
)
from app.models.provider import Provider, ProviderLocation, ProviderSpecialization
from app.repositories.user_repository import UserRepository

URL = "/api/v1/admin/dashboard/stats"
PROVIDERS = "/api/v1/admin/providers"


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_token(client: TestClient, seeded_admin) -> str:
    user, password = seeded_admin
    return _login(client, user.email, password)


def _create_provider(client, token, name, ptype="HOSPITAL"):
    resp = client.post(
        PROVIDERS,
        json={"provider_type": ptype, "name": name, "visit_stability": "STABLE_VISIT"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_location(client, token, provider_id, lat=None, lon=None, city="Springfield"):
    body = {"address_line_1": "1 Main St", "city": city}
    if lat is not None:
        body["latitude"] = lat
    if lon is not None:
        body["longitude"] = lon
    resp = client.post(f"{PROVIDERS}/{provider_id}/locations", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestSecurity:
    def test_requires_auth(self, client: TestClient):
        assert client.get(URL).status_code == 401

    def test_forbidden_for_non_admin(self, client: TestClient, db):
        repo = UserRepository(db)
        role = repo.get_role_by_name("visitor") or repo.create_role("visitor", "Visitor")
        repo.create_user(
            email="v@example.com",
            password_hash=hash_password("Visitor#2026!ABC"),
            role=role,
        )
        db.commit()
        token = _login(client, "v@example.com", "Visitor#2026!ABC")
        assert client.get(URL, headers=_auth(token)).status_code == 403


class TestDashboard:
    def test_empty_data_shape(self, client: TestClient, admin_token: str):
        resp = client.get(URL, headers=_auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_counts"] == {"hospitals": 0, "clinics": 0, "doctors": 0}
        assert data["active_providers"] == 0
        assert data["invitation_counts"] == {"sent": 0, "accepted": 0, "rejected": 0}
        assert data["registration_counts"] == {
            "requests": 0,
            "approved": 0,
            "rejected": 0,
            "horse_owners": 0,
            "stable_managers": 0,
        }
        assert len(data["visitor_visits"]) == 7
        assert all(visit["count"] == 0 for visit in data["visitor_visits"])
        assert data["location_markers"] == []
        assert "total_users" in data
        assert "recent_audit_events" not in data

    def test_mixed_provider_type_counts(self, client: TestClient, admin_token: str):
        _create_provider(client, admin_token, "H1", "HOSPITAL")
        _create_provider(client, admin_token, "H2", "HOSPITAL")
        _create_provider(client, admin_token, "C1", "CLINIC")
        _create_provider(client, admin_token, "D1", "DOCTOR")
        _create_provider(client, admin_token, "D2", "DOCTOR")
        _create_provider(client, admin_token, "D3", "DOCTOR")
        data = client.get(URL, headers=_auth(admin_token)).json()
        assert data["provider_counts"] == {"hospitals": 2, "clinics": 1, "doctors": 3}

    def test_coordinate_filtering(self, client: TestClient, admin_token: str):
        p = _create_provider(client, admin_token, "Geo Hospital")
        _add_location(client, admin_token, p["id"], lat=40.0, lon=-73.9, city="NYC")
        _add_location(client, admin_token, p["id"])  # no coords → omitted
        _add_location(client, admin_token, p["id"], lat=41.0)  # missing lon → omitted
        data = client.get(URL, headers=_auth(admin_token)).json()
        markers = data["location_markers"]
        assert len(markers) == 1
        m = markers[0]
        assert m["provider_name"] == "Geo Hospital"
        assert m["provider_type"] == "HOSPITAL"
        assert m["latitude"] == 40.0
        assert m["longitude"] == -73.9
        assert m["city"] == "NYC"
        assert "1 Main St" in m["address"]

    def test_multiple_locations_and_providers(self, client: TestClient, admin_token: str):
        p1 = _create_provider(client, admin_token, "Multi Hospital")
        p2 = _create_provider(client, admin_token, "Solo Clinic", "CLINIC")
        _add_location(client, admin_token, p1["id"], lat=10.0, lon=10.0, city="A")
        _add_location(client, admin_token, p1["id"], lat=11.0, lon=11.0, city="B")
        _add_location(client, admin_token, p2["id"], lat=12.0, lon=12.0, city="C")
        markers = client.get(URL, headers=_auth(admin_token)).json()["location_markers"]
        assert len(markers) == 3
        assert {m["provider_type"] for m in markers} == {"HOSPITAL", "CLINIC"}
        assert len([m for m in markers if m["provider_id"] == p1["id"]]) == 2

    def test_dashboard_does_not_include_audit_feed(self, client: TestClient, admin_token: str):
        data = client.get(URL, headers=_auth(admin_token)).json()
        assert "recent_audit_events" not in data

    def test_public_visit_is_reflected_in_dashboard(self, client: TestClient, admin_token: str):
        response = client.post("/api/v1/public/visits")
        assert response.status_code == 204

        visits = client.get(URL, headers=_auth(admin_token)).json()["visitor_visits"]
        assert len(visits) == 7
        assert sum(visit["count"] for visit in visits) == 1

    def test_registration_counts_include_status_and_public_roles(
        self, client: TestClient, admin_token: str, db
    ):
        repo = UserRepository(db)
        horse_owner = repo.get_role_by_name("horse_owner") or repo.create_role(
            "horse_owner", "Public horse owner account"
        )
        stable_manager = repo.get_role_by_name("stable_manager") or repo.create_role(
            "stable_manager", "Public stable manager account"
        )
        approved = repo.create_user(
            email="approved-owner@example.com",
            password_hash=hash_password("Approved#2026!ABC"),
            role=horse_owner,
            roles=[horse_owner, stable_manager],
        )
        approved.email_verified_at = datetime.now(timezone.utc)
        approved.approval_status = PublicAccountApprovalStatus.APPROVED
        rejected = repo.create_user(
            email="rejected-owner@example.com",
            password_hash=hash_password("Rejected#2026!ABC"),
            role=horse_owner,
            is_active=False,
        )
        rejected.email_verified_at = datetime.now(timezone.utc)
        rejected.approval_status = PublicAccountApprovalStatus.REJECTED
        db.commit()

        counts = client.get(URL, headers=_auth(admin_token)).json()["registration_counts"]
        assert counts == {
            "requests": 2,
            "approved": 1,
            "rejected": 1,
            "horse_owners": 2,
            "stable_managers": 1,
        }


class TestDemoSeed:
    def test_seed_idempotent(self, db):
        from scripts.seed_demo_data import seed, PROVIDERS as SEED_PROVIDERS, SPECIALIZATIONS

        first = seed(db)
        assert first["providers"] == len(SEED_PROVIDERS)
        assert first["specializations"] == len(SPECIALIZATIONS)
        assert first["locations"] == len(SEED_PROVIDERS)
        assert first["assignments"] > 0

        second = seed(db)
        assert second == {
            "specializations": 0,
            "providers": 0,
            "locations": 0,
            "assignments": 0,
        }

    def test_seeded_rows_are_active_published_with_dubai_coords(self, db):
        from scripts.seed_demo_data import seed

        seed(db)
        providers = db.query(Provider).all()
        assert providers
        for p in providers:
            assert p.status == ProviderStatus.ACTIVE
            assert p.publication_status == PublicationStatus.PUBLISHED

        locations = db.query(ProviderLocation).all()
        assert len(locations) == len(providers)
        required_neighborhoods = {
            "Dubai Marina",
            "Jumeirah",
            "Downtown Dubai",
            "Al Barsha",
            "Mirdif",
        }
        location_names = {loc.name for loc in locations}
        assert all(
            any(neighborhood in (name or "") for name in location_names)
            for neighborhood in required_neighborhoods
        )

        for loc in locations:
            assert loc.latitude is not None and loc.longitude is not None
            assert loc.is_primary is True
            assert loc.city == "Dubai"
            assert loc.state_province == "Dubai"
            assert loc.country == "United Arab Emirates"
            assert 24.8 <= float(loc.latitude) <= 25.4
            assert 54.9 <= float(loc.longitude) <= 55.6

    def test_seeded_rows_are_visible_on_dashboard_map(self, client: TestClient, admin_token: str, db):
        from scripts.seed_demo_data import seed

        seed(db)
        data = client.get(URL, headers=_auth(admin_token)).json()

        assert data["provider_counts"] == {"hospitals": 3, "clinics": 3, "doctors": 3}
        assert data["active_providers"] == 9
        assert len(data["location_markers"]) == 9
        assert {marker["city"] for marker in data["location_markers"]} == {"Dubai"}
        assert all(
            24.8 <= marker["latitude"] <= 25.4
            and 54.9 <= marker["longitude"] <= 55.6
            and marker["is_primary"] is True
            for marker in data["location_markers"]
        )

    def test_seed_does_not_change_unrelated_rows(self, db):
        from scripts.seed_demo_data import seed

        unrelated = Provider(
            provider_type=ProviderType.CLINIC,
            name="User Entered Clinic",
            visit_stability=VisitStability.STABLE_VISIT,
            status=ProviderStatus.INACTIVE,
            publication_status=PublicationStatus.UNPUBLISHED,
        )
        db.add(unrelated)
        db.flush()
        unrelated_location = ProviderLocation(
            provider_id=unrelated.id,
            name="User Entered Location",
            address_line_1="1 User Street",
            city="Abu Dhabi",
            country="United Arab Emirates",
            is_primary=True,
        )
        db.add(unrelated_location)
        db.commit()
        original_provider_id = unrelated.id
        original_location_id = unrelated_location.id

        seed(db)

        unchanged_provider = db.get(Provider, original_provider_id)
        unchanged_location = db.get(ProviderLocation, original_location_id)
        assert unchanged_provider is not None
        assert unchanged_provider.status == ProviderStatus.INACTIVE
        assert unchanged_provider.publication_status == PublicationStatus.UNPUBLISHED
        assert unchanged_location is not None
        assert unchanged_location.city == "Abu Dhabi"
        assert db.query(ProviderSpecialization).count() > 0
