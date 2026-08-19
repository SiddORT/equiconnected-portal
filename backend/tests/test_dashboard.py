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
import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
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
        assert data["location_markers"] == []
        assert "total_users" in data
        assert "recent_audit_events" in data

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

    def test_audit_events_still_present(self, client: TestClient, admin_token: str):
        data = client.get(URL, headers=_auth(admin_token)).json()
        # Login above produced at least one audit event
        assert isinstance(data["recent_audit_events"], list)


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

    def test_seeded_rows_are_active_published_with_coords(self, db):
        from scripts.seed_demo_data import seed
        from app.models.enums import ProviderStatus, PublicationStatus
        from app.models.provider import Provider, ProviderLocation

        seed(db)
        providers = db.query(Provider).all()
        assert providers
        for p in providers:
            assert p.status == ProviderStatus.ACTIVE
            assert p.publication_status == PublicationStatus.PUBLISHED
        locations = db.query(ProviderLocation).all()
        assert locations
        for loc in locations:
            assert loc.latitude is not None and loc.longitude is not None
            assert loc.is_primary is True
