"""
Provider module tests — Phase 4 (spec section 27).

Covers:
  - Unauthenticated / non-admin access denial
  - Provider CRUD (create, list, detail, partial update)
  - Create with specializations and primary location
  - Invalid enum / missing field validation (422)
  - All list filters (provider_type, visit_stability, status, publication_status, search)
  - Pagination boundary cases
  - Status and publication toggles
  - Specialization many-to-many (add, remove, duplicate → 409, unknown → 404)
  - Location endpoints incl. single-primary enforcement
  - Photo endpoints incl. thumbnail uniqueness
  - 404s for unknown provider / location / photo IDs
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.repositories.user_repository import UserRepository


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


BASE = "/api/v1/admin/providers"


def _provider_body(name: str = "General Hospital", **overrides) -> dict:
    body = {
        "provider_type": "HOSPITAL",
        "name": name,
        "visit_stability": "STABLE_VISIT",
    }
    body.update(overrides)
    return body


def _create_provider(client: TestClient, token: str, name: str = "General Hospital", **overrides) -> dict:
    resp = client.post(BASE, json=_provider_body(name, **overrides), headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_spec(client: TestClient, token: str, name: str) -> dict:
    resp = client.post(
        "/api/v1/admin/specializations", json={"name": name}, headers=_auth(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _location_body(**overrides) -> dict:
    body = {"address_line_1": "1 Main St", "city": "Springfield"}
    body.update(overrides)
    return body


def _photo_body(**overrides) -> dict:
    body = {"storage_reference": "photos/abc.jpg"}
    body.update(overrides)
    return body


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def admin_token(client: TestClient, seeded_admin) -> str:
    user, password = seeded_admin
    return _login(client, user.email, password)


@pytest.fixture()
def non_admin_token(client: TestClient, db) -> str:
    repo = UserRepository(db)
    role = repo.get_role_by_name("visitor")
    if role is None:
        role = repo.create_role("visitor", "Visitor")
    user = repo.create_user(
        email="visitor@example.com",
        password_hash=hash_password("Visitor#2026!ABC"),
        role=role,
    )
    db.commit()
    return _login(client, user.email, "Visitor#2026!ABC")


# ── Security ──────────────────────────────────────────────────────────────────

class TestSecurity:
    def test_list_requires_auth(self, client: TestClient):
        assert client.get(BASE).status_code == 401

    def test_create_requires_auth(self, client: TestClient):
        assert client.post(BASE, json=_provider_body()).status_code == 401

    def test_get_requires_auth(self, client: TestClient):
        assert client.get(f"{BASE}/{uuid.uuid4()}").status_code == 401

    def test_update_requires_auth(self, client: TestClient):
        assert client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "X"}).status_code == 401

    def test_sub_resources_require_auth(self, client: TestClient):
        pid = uuid.uuid4()
        assert client.post(f"{BASE}/{pid}/locations", json=_location_body()).status_code == 401
        assert client.post(f"{BASE}/{pid}/photos", json=_photo_body()).status_code == 401
        assert client.post(
            f"{BASE}/{pid}/specializations", json={"specialization_id": str(uuid.uuid4())}
        ).status_code == 401

    def test_list_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        assert client.get(BASE, headers=_auth(non_admin_token)).status_code == 403

    def test_create_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        assert client.post(
            BASE, json=_provider_body(), headers=_auth(non_admin_token)
        ).status_code == 403

    def test_sub_resource_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        assert client.post(
            f"{BASE}/{uuid.uuid4()}/photos", json=_photo_body(), headers=_auth(non_admin_token)
        ).status_code == 403


# ── Create ────────────────────────────────────────────────────────────────────

class TestCreate:
    def test_create_minimal_provider(self, client: TestClient, admin_token: str):
        resp = client.post(BASE, json=_provider_body("City Clinic", provider_type="CLINIC"), headers=_auth(admin_token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "City Clinic"
        assert data["provider_type"] == "CLINIC"
        assert data["status"] == "ACTIVE"
        assert data["publication_status"] == "UNPUBLISHED"
        assert data["specializations"] == []
        assert data["locations"] == []
        assert data["photos"] == []

    def test_create_with_specializations_and_primary_location(self, client: TestClient, admin_token: str):
        s1 = _create_spec(client, admin_token, "Cardiology")
        s2 = _create_spec(client, admin_token, "Neurology")
        body = _provider_body(
            "Full Hospital",
            specialization_ids=[s1["id"], s2["id"]],
            primary_location=_location_body(),
        )
        resp = client.post(BASE, json=body, headers=_auth(admin_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert {s["name"] for s in data["specializations"]} == {"Cardiology", "Neurology"}
        assert len(data["locations"]) == 1
        assert data["locations"][0]["is_primary"] is True

    def test_create_with_unknown_specialization_returns_404(self, client: TestClient, admin_token: str):
        body = _provider_body("Bad Spec", specialization_ids=[str(uuid.uuid4())])
        resp = client.post(BASE, json=body, headers=_auth(admin_token))
        assert resp.status_code == 404

    def test_create_with_inactive_specialization_returns_404(self, client: TestClient, admin_token: str):
        spec = _create_spec(client, admin_token, "Retired")
        client.patch(
            f"/api/v1/admin/specializations/{spec['id']}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        resp = client.post(
            BASE, json=_provider_body("X", specialization_ids=[spec["id"]]), headers=_auth(admin_token)
        )
        assert resp.status_code == 404

    def test_invalid_enum_returns_422(self, client: TestClient, admin_token: str):
        resp = client.post(BASE, json=_provider_body(provider_type="SPACESHIP"), headers=_auth(admin_token))
        assert resp.status_code == 422
        resp = client.post(BASE, json=_provider_body(visit_stability="MAYBE"), headers=_auth(admin_token))
        assert resp.status_code == 422

    def test_missing_required_fields_returns_422(self, client: TestClient, admin_token: str):
        resp = client.post(BASE, json={"name": "No type"}, headers=_auth(admin_token))
        assert resp.status_code == 422

    def test_empty_name_rejected(self, client: TestClient, admin_token: str):
        resp = client.post(BASE, json=_provider_body("   "), headers=_auth(admin_token))
        assert resp.status_code == 422

    def test_name_is_trimmed(self, client: TestClient, admin_token: str):
        data = _create_provider(client, admin_token, "  Trimmed Hospital  ")
        assert data["name"] == "Trimmed Hospital"


# ── List, filters & pagination ───────────────────────────────────────────────

class TestList:
    def test_empty_list(self, client: TestClient, admin_token: str):
        resp = client.get(BASE, headers=_auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 0

    def test_search_by_name(self, client: TestClient, admin_token: str):
        _create_provider(client, admin_token, "Mercy Hospital")
        _create_provider(client, admin_token, "City Clinic", provider_type="CLINIC")
        resp = client.get(BASE, params={"search": "mercy"}, headers=_auth(admin_token))
        data = resp.json()
        assert data["meta"]["total"] == 1
        assert data["data"][0]["name"] == "Mercy Hospital"

    def test_filter_provider_type(self, client: TestClient, admin_token: str):
        _create_provider(client, admin_token, "H1", provider_type="HOSPITAL")
        _create_provider(client, admin_token, "C1", provider_type="CLINIC")
        _create_provider(client, admin_token, "D1", provider_type="DOCTOR")
        resp = client.get(BASE, params={"provider_type": "CLINIC"}, headers=_auth(admin_token))
        data = resp.json()
        assert data["meta"]["total"] == 1
        assert data["data"][0]["name"] == "C1"

    def test_filter_visit_stability(self, client: TestClient, admin_token: str):
        _create_provider(client, admin_token, "Stable", visit_stability="STABLE_VISIT")
        _create_provider(client, admin_token, "Unstable", visit_stability="NOT_STABLE_VISIT")
        resp = client.get(BASE, params={"visit_stability": "NOT_STABLE_VISIT"}, headers=_auth(admin_token))
        names = [p["name"] for p in resp.json()["data"]]
        assert names == ["Unstable"]

    def test_filter_status(self, client: TestClient, admin_token: str):
        p = _create_provider(client, admin_token, "WillDeactivate")
        _create_provider(client, admin_token, "StaysActive")
        client.patch(f"{BASE}/{p['id']}/status", json={"status": "INACTIVE"}, headers=_auth(admin_token))
        resp = client.get(BASE, params={"status": "INACTIVE"}, headers=_auth(admin_token))
        names = [x["name"] for x in resp.json()["data"]]
        assert names == ["WillDeactivate"]

    def test_filter_publication_status(self, client: TestClient, admin_token: str):
        p = _create_provider(client, admin_token, "Published One")
        _create_provider(client, admin_token, "Draft One")
        client.patch(
            f"{BASE}/{p['id']}/publication",
            json={"publication_status": "PUBLISHED"},
            headers=_auth(admin_token),
        )
        resp = client.get(BASE, params={"publication_status": "PUBLISHED"}, headers=_auth(admin_token))
        names = [x["name"] for x in resp.json()["data"]]
        assert names == ["Published One"]

    def test_combined_filters(self, client: TestClient, admin_token: str):
        _create_provider(client, admin_token, "Alpha Clinic", provider_type="CLINIC")
        _create_provider(client, admin_token, "Alpha Hospital", provider_type="HOSPITAL")
        _create_provider(client, admin_token, "Beta Clinic", provider_type="CLINIC")
        resp = client.get(
            BASE,
            params={"search": "alpha", "provider_type": "CLINIC"},
            headers=_auth(admin_token),
        )
        data = resp.json()
        assert data["meta"]["total"] == 1
        assert data["data"][0]["name"] == "Alpha Clinic"

    def test_invalid_filter_enum_returns_422(self, client: TestClient, admin_token: str):
        resp = client.get(BASE, params={"provider_type": "NOPE"}, headers=_auth(admin_token))
        assert resp.status_code == 422

    def test_pagination(self, client: TestClient, admin_token: str):
        for i in range(5):
            _create_provider(client, admin_token, f"Prov{i:02d}")
        resp = client.get(BASE, params={"page": 1, "page_size": 2}, headers=_auth(admin_token))
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["meta"]["total"] == 5
        assert data["meta"]["total_pages"] == 3
        resp = client.get(BASE, params={"page": 3, "page_size": 2}, headers=_auth(admin_token))
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["meta"]["page"] == 3

    def test_pagination_beyond_last_page_returns_empty(self, client: TestClient, admin_token: str):
        _create_provider(client, admin_token, "Only One")
        resp = client.get(BASE, params={"page": 5, "page_size": 10}, headers=_auth(admin_token))
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 1

    def test_pagination_bad_params_rejected(self, client: TestClient, admin_token: str):
        assert client.get(BASE, params={"page": 0}, headers=_auth(admin_token)).status_code == 422
        assert client.get(BASE, params={"page_size": 101}, headers=_auth(admin_token)).status_code == 422

    def test_sorted_by_name(self, client: TestClient, admin_token: str):
        for name in ["Zeta", "Alpha", "Mid"]:
            _create_provider(client, admin_token, name)
        names = [p["name"] for p in client.get(BASE, headers=_auth(admin_token)).json()["data"]]
        assert names == sorted(names)


# ── Detail & update ───────────────────────────────────────────────────────────

class TestDetailAndUpdate:
    def test_get_detail(self, client: TestClient, admin_token: str):
        created = _create_provider(client, admin_token, "Detail Hospital")
        resp = client.get(f"{BASE}/{created['id']}", headers=_auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Detail Hospital"
        assert "specializations" in data and "locations" in data and "photos" in data

    def test_get_unknown_returns_404(self, client: TestClient, admin_token: str):
        assert client.get(f"{BASE}/{uuid.uuid4()}", headers=_auth(admin_token)).status_code == 404

    def test_partial_update_only_touches_supplied_fields(self, client: TestClient, admin_token: str):
        created = _create_provider(
            client, admin_token, "Original", description="Keep me", phone="123"
        )
        resp = client.patch(
            f"{BASE}/{created['id']}", json={"name": "Renamed"}, headers=_auth(admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Renamed"
        assert data["description"] == "Keep me"
        assert data["phone"] == "123"

    def test_update_multiple_fields(self, client: TestClient, admin_token: str):
        created = _create_provider(client, admin_token, "Multi")
        resp = client.patch(
            f"{BASE}/{created['id']}",
            json={"email": "a@b.com", "website": "https://x.com", "provider_type": "DOCTOR"},
            headers=_auth(admin_token),
        )
        data = resp.json()
        assert data["email"] == "a@b.com"
        assert data["website"] == "https://x.com"
        assert data["provider_type"] == "DOCTOR"

    def test_update_can_null_a_field(self, client: TestClient, admin_token: str):
        created = _create_provider(client, admin_token, "Nullable", description="temp")
        resp = client.patch(
            f"{BASE}/{created['id']}", json={"description": None}, headers=_auth(admin_token)
        )
        assert resp.json()["description"] is None

    def test_update_invalid_enum_returns_422(self, client: TestClient, admin_token: str):
        created = _create_provider(client, admin_token, "EnumTest")
        resp = client.patch(
            f"{BASE}/{created['id']}", json={"provider_type": "BAD"}, headers=_auth(admin_token)
        )
        assert resp.status_code == 422

    def test_update_unknown_returns_404(self, client: TestClient, admin_token: str):
        resp = client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "X"}, headers=_auth(admin_token))
        assert resp.status_code == 404


# ── Status & publication toggles ──────────────────────────────────────────────

class TestToggles:
    def test_status_toggle(self, client: TestClient, admin_token: str):
        created = _create_provider(client, admin_token, "Toggler")
        resp = client.patch(
            f"{BASE}/{created['id']}/status", json={"status": "INACTIVE"}, headers=_auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "INACTIVE"
        resp = client.patch(
            f"{BASE}/{created['id']}/status", json={"status": "ACTIVE"}, headers=_auth(admin_token)
        )
        assert resp.json()["status"] == "ACTIVE"

    def test_publication_toggle(self, client: TestClient, admin_token: str):
        created = _create_provider(client, admin_token, "Publisher")
        resp = client.patch(
            f"{BASE}/{created['id']}/publication",
            json={"publication_status": "PUBLISHED"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["publication_status"] == "PUBLISHED"

    def test_invalid_status_value_returns_422(self, client: TestClient, admin_token: str):
        created = _create_provider(client, admin_token, "BadStatus")
        resp = client.patch(
            f"{BASE}/{created['id']}/status", json={"status": "MAYBE"}, headers=_auth(admin_token)
        )
        assert resp.status_code == 422

    def test_toggles_unknown_provider_return_404(self, client: TestClient, admin_token: str):
        pid = uuid.uuid4()
        assert client.patch(
            f"{BASE}/{pid}/status", json={"status": "INACTIVE"}, headers=_auth(admin_token)
        ).status_code == 404
        assert client.patch(
            f"{BASE}/{pid}/publication",
            json={"publication_status": "PUBLISHED"},
            headers=_auth(admin_token),
        ).status_code == 404


# ── Specialization assignments ────────────────────────────────────────────────

class TestSpecializations:
    def test_add_and_remove(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        spec = _create_spec(client, admin_token, "Oncology")
        resp = client.post(
            f"{BASE}/{provider['id']}/specializations",
            json={"specialization_id": spec["id"]},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        assert [s["name"] for s in resp.json()["specializations"]] == ["Oncology"]

        resp = client.delete(
            f"{BASE}/{provider['id']}/specializations/{spec['id']}",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["specializations"] == []

    def test_remove_keeps_other_assignments(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        s1 = _create_spec(client, admin_token, "Keep")
        s2 = _create_spec(client, admin_token, "Drop")
        for s in (s1, s2):
            client.post(
                f"{BASE}/{provider['id']}/specializations",
                json={"specialization_id": s["id"]},
                headers=_auth(admin_token),
            )
        resp = client.delete(
            f"{BASE}/{provider['id']}/specializations/{s2['id']}", headers=_auth(admin_token)
        )
        assert [s["name"] for s in resp.json()["specializations"]] == ["Keep"]

    def test_duplicate_assignment_returns_409(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        spec = _create_spec(client, admin_token, "Dup")
        for expected in (201, 409):
            resp = client.post(
                f"{BASE}/{provider['id']}/specializations",
                json={"specialization_id": spec["id"]},
                headers=_auth(admin_token),
            )
            assert resp.status_code == expected

    def test_unknown_specialization_returns_404(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        resp = client.post(
            f"{BASE}/{provider['id']}/specializations",
            json={"specialization_id": str(uuid.uuid4())},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404

    def test_assign_inactive_specialization_returns_404(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        spec = _create_spec(client, admin_token, "Deactivated")
        client.patch(
            f"/api/v1/admin/specializations/{spec['id']}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        resp = client.post(
            f"{BASE}/{provider['id']}/specializations",
            json={"specialization_id": spec["id"]},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404

    def test_remove_unassigned_returns_404(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        spec = _create_spec(client, admin_token, "NeverAssigned")
        resp = client.delete(
            f"{BASE}/{provider['id']}/specializations/{spec['id']}", headers=_auth(admin_token)
        )
        assert resp.status_code == 404

    def test_unknown_provider_returns_404(self, client: TestClient, admin_token: str):
        spec = _create_spec(client, admin_token, "Orphan")
        resp = client.post(
            f"{BASE}/{uuid.uuid4()}/specializations",
            json={"specialization_id": spec["id"]},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404


# ── Locations ─────────────────────────────────────────────────────────────────

class TestLocations:
    def test_add_location(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        resp = client.post(
            f"{BASE}/{provider['id']}/locations",
            json=_location_body(is_primary=True, latitude="40.712800", longitude="-74.006000"),
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["city"] == "Springfield"
        assert data["is_primary"] is True

    def test_update_location(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        loc = client.post(
            f"{BASE}/{provider['id']}/locations", json=_location_body(), headers=_auth(admin_token)
        ).json()
        resp = client.patch(
            f"{BASE}/{provider['id']}/locations/{loc['id']}",
            json={"city": "Shelbyville"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["city"] == "Shelbyville"
        assert resp.json()["address_line_1"] == "1 Main St"

    def test_delete_location(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        loc = client.post(
            f"{BASE}/{provider['id']}/locations", json=_location_body(), headers=_auth(admin_token)
        ).json()
        resp = client.delete(
            f"{BASE}/{provider['id']}/locations/{loc['id']}", headers=_auth(admin_token)
        )
        assert resp.status_code == 204
        detail = client.get(f"{BASE}/{provider['id']}", headers=_auth(admin_token)).json()
        assert detail["locations"] == []

    def test_single_primary_enforced_on_add(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        first = client.post(
            f"{BASE}/{provider['id']}/locations",
            json=_location_body(is_primary=True),
            headers=_auth(admin_token),
        ).json()
        second = client.post(
            f"{BASE}/{provider['id']}/locations",
            json=_location_body(address_line_1="2 Oak Ave", is_primary=True),
            headers=_auth(admin_token),
        ).json()
        assert second["is_primary"] is True
        detail = client.get(f"{BASE}/{provider['id']}", headers=_auth(admin_token)).json()
        flags = {loc["id"]: loc["is_primary"] for loc in detail["locations"]}
        assert flags[first["id"]] is False
        assert flags[second["id"]] is True
        assert sum(flags.values()) == 1

    def test_single_primary_enforced_on_update(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        first = client.post(
            f"{BASE}/{provider['id']}/locations",
            json=_location_body(is_primary=True),
            headers=_auth(admin_token),
        ).json()
        second = client.post(
            f"{BASE}/{provider['id']}/locations",
            json=_location_body(address_line_1="2 Oak Ave"),
            headers=_auth(admin_token),
        ).json()
        resp = client.patch(
            f"{BASE}/{provider['id']}/locations/{second['id']}",
            json={"is_primary": True},
            headers=_auth(admin_token),
        )
        assert resp.json()["is_primary"] is True
        detail = client.get(f"{BASE}/{provider['id']}", headers=_auth(admin_token)).json()
        flags = {loc["id"]: loc["is_primary"] for loc in detail["locations"]}
        assert flags[first["id"]] is False
        assert sum(flags.values()) == 1

    def test_primary_flag_scoped_per_provider(self, client: TestClient, admin_token: str):
        p1 = _create_provider(client, admin_token, "P1")
        p2 = _create_provider(client, admin_token, "P2")
        for p in (p1, p2):
            resp = client.post(
                f"{BASE}/{p['id']}/locations",
                json=_location_body(is_primary=True),
                headers=_auth(admin_token),
            )
            assert resp.status_code == 201
            assert resp.json()["is_primary"] is True

    def test_unknown_location_returns_404(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        lid = uuid.uuid4()
        assert client.patch(
            f"{BASE}/{provider['id']}/locations/{lid}", json={"city": "X"}, headers=_auth(admin_token)
        ).status_code == 404
        assert client.delete(
            f"{BASE}/{provider['id']}/locations/{lid}", headers=_auth(admin_token)
        ).status_code == 404

    def test_location_of_other_provider_returns_404(self, client: TestClient, admin_token: str):
        p1 = _create_provider(client, admin_token, "Owner")
        p2 = _create_provider(client, admin_token, "Other")
        loc = client.post(
            f"{BASE}/{p1['id']}/locations", json=_location_body(), headers=_auth(admin_token)
        ).json()
        assert client.delete(
            f"{BASE}/{p2['id']}/locations/{loc['id']}", headers=_auth(admin_token)
        ).status_code == 404

    def test_location_missing_required_field_returns_422(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        resp = client.post(
            f"{BASE}/{provider['id']}/locations",
            json={"city": "NoAddress"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422


# ── Photos ────────────────────────────────────────────────────────────────────

class TestPhotos:
    def test_upload_photo_with_multipart_file(self, client: TestClient, admin_token: str):
        """Multipart uploads coexist with the legacy JSON metadata contract."""
        provider = _create_provider(client, admin_token)
        resp = client.post(
            f"{BASE}/{provider['id']}/photos",
            files={"file": ("entrance.png", b"not-a-real-png", "image/png")},
            data={
                "alt_text": "Main entrance",
                "caption": "South-facing entrance",
                "display_order": "2",
                "is_thumbnail": "true",
            },
            headers=_auth(admin_token),
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["storage_reference"].startswith(f"/uploads/providers/{provider['id']}/photos/")
        assert data["alt_text"] == "Main entrance"
        assert data["display_order"] == 2
        assert data["is_thumbnail"] is True

    def test_add_multiple_photos(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        for i in range(3):
            resp = client.post(
                f"{BASE}/{provider['id']}/photos",
                json=_photo_body(storage_reference=f"photos/{i}.jpg", display_order=i),
                headers=_auth(admin_token),
            )
            assert resp.status_code == 201
        detail = client.get(f"{BASE}/{provider['id']}", headers=_auth(admin_token)).json()
        assert len(detail["photos"]) == 3
        assert [p["display_order"] for p in detail["photos"]] == [0, 1, 2]

    def test_update_photo(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        photo = client.post(
            f"{BASE}/{provider['id']}/photos", json=_photo_body(), headers=_auth(admin_token)
        ).json()
        resp = client.patch(
            f"{BASE}/{provider['id']}/photos/{photo['id']}",
            json={"alt_text": "Front entrance", "caption": "Main door"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["alt_text"] == "Front entrance"
        assert resp.json()["caption"] == "Main door"

    def test_delete_photo(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        photo = client.post(
            f"{BASE}/{provider['id']}/photos", json=_photo_body(), headers=_auth(admin_token)
        ).json()
        resp = client.delete(
            f"{BASE}/{provider['id']}/photos/{photo['id']}", headers=_auth(admin_token)
        )
        assert resp.status_code == 204
        detail = client.get(f"{BASE}/{provider['id']}", headers=_auth(admin_token)).json()
        assert detail["photos"] == []

    def test_thumbnail_uniqueness_on_set(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        photos = [
            client.post(
                f"{BASE}/{provider['id']}/photos",
                json=_photo_body(storage_reference=f"photos/t{i}.jpg"),
                headers=_auth(admin_token),
            ).json()
            for i in range(2)
        ]
        resp = client.patch(
            f"{BASE}/{provider['id']}/photos/{photos[0]['id']}/thumbnail",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_thumbnail"] is True

        # Switch thumbnail — the previous one must be cleared automatically.
        client.patch(
            f"{BASE}/{provider['id']}/photos/{photos[1]['id']}/thumbnail",
            headers=_auth(admin_token),
        )
        detail = client.get(f"{BASE}/{provider['id']}", headers=_auth(admin_token)).json()
        flags = {p["id"]: p["is_thumbnail"] for p in detail["photos"]}
        assert flags[photos[0]["id"]] is False
        assert flags[photos[1]["id"]] is True
        assert sum(flags.values()) == 1

    def test_thumbnail_uniqueness_on_create(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        client.post(
            f"{BASE}/{provider['id']}/photos",
            json=_photo_body(storage_reference="a.jpg", is_thumbnail=True),
            headers=_auth(admin_token),
        )
        client.post(
            f"{BASE}/{provider['id']}/photos",
            json=_photo_body(storage_reference="b.jpg", is_thumbnail=True),
            headers=_auth(admin_token),
        )
        detail = client.get(f"{BASE}/{provider['id']}", headers=_auth(admin_token)).json()
        assert sum(p["is_thumbnail"] for p in detail["photos"]) == 1

    def test_thumbnail_scoped_per_provider(self, client: TestClient, admin_token: str):
        p1 = _create_provider(client, admin_token, "T1")
        p2 = _create_provider(client, admin_token, "T2")
        for p in (p1, p2):
            resp = client.post(
                f"{BASE}/{p['id']}/photos",
                json=_photo_body(is_thumbnail=True),
                headers=_auth(admin_token),
            )
            assert resp.status_code == 201
            assert resp.json()["is_thumbnail"] is True

    def test_unknown_photo_returns_404(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        pid = uuid.uuid4()
        assert client.patch(
            f"{BASE}/{provider['id']}/photos/{pid}", json={"caption": "x"}, headers=_auth(admin_token)
        ).status_code == 404
        assert client.delete(
            f"{BASE}/{provider['id']}/photos/{pid}", headers=_auth(admin_token)
        ).status_code == 404
        assert client.patch(
            f"{BASE}/{provider['id']}/photos/{pid}/thumbnail", headers=_auth(admin_token)
        ).status_code == 404

    def test_photo_missing_storage_reference_returns_422(self, client: TestClient, admin_token: str):
        provider = _create_provider(client, admin_token)
        resp = client.post(
            f"{BASE}/{provider['id']}/photos", json={"caption": "no ref"}, headers=_auth(admin_token)
        )
        assert resp.status_code == 422


# ── Phones & Emails (multi-contact) ──────────────────────────────────────────

class TestProviderPhonesEmails:
    def test_create_with_phones_and_emails(self, client: TestClient, admin_token: str):
        p = _create_provider(
            client, admin_token, "Contact Rich",
            phones=[
                {"country_code": "+1", "number": "555 000 1111", "is_primary": True},
                {"country_code": "+44", "number": "7700 900123"},
            ],
            emails=[
                {"email": "primary@x.com", "is_primary": True},
                {"email": "second@x.com"},
            ],
        )
        assert len(p["phones"]) == 2
        assert len(p["emails"]) == 2
        # Primary entries are sorted first.
        assert p["phones"][0]["is_primary"] is True
        assert p["phones"][0]["number"] == "555 000 1111"
        assert p["emails"][0]["email"] == "primary@x.com"
        assert sum(ph["is_primary"] for ph in p["phones"]) == 1
        assert sum(em["is_primary"] for em in p["emails"]) == 1

    def test_create_with_two_primaries_keeps_only_one(self, client: TestClient, admin_token: str):
        p = _create_provider(
            client, admin_token, "Two Primaries",
            phones=[
                {"country_code": "+1", "number": "1", "is_primary": True},
                {"country_code": "+1", "number": "2", "is_primary": True},
            ],
            emails=[
                {"email": "a@x.com", "is_primary": True},
                {"email": "b@x.com", "is_primary": True},
            ],
        )
        assert sum(ph["is_primary"] for ph in p["phones"]) == 1
        assert sum(em["is_primary"] for em in p["emails"]) == 1

    def test_add_primary_phone_demotes_existing(self, client: TestClient, admin_token: str):
        p = _create_provider(
            client, admin_token, "Demote Phone",
            phones=[{"country_code": "+1", "number": "111", "is_primary": True}],
        )
        resp = client.post(
            f"{BASE}/{p['id']}/phones",
            json={"country_code": "+91", "number": "222", "is_primary": True},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201, resp.text
        detail = client.get(f"{BASE}/{p['id']}", headers=_auth(admin_token)).json()
        primaries = [ph for ph in detail["phones"] if ph["is_primary"]]
        assert len(primaries) == 1
        assert primaries[0]["number"] == "222"

    def test_add_primary_email_demotes_existing(self, client: TestClient, admin_token: str):
        p = _create_provider(
            client, admin_token, "Demote Email",
            emails=[{"email": "old@x.com", "is_primary": True}],
        )
        resp = client.post(
            f"{BASE}/{p['id']}/emails",
            json={"email": "new@x.com", "is_primary": True},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201, resp.text
        detail = client.get(f"{BASE}/{p['id']}", headers=_auth(admin_token)).json()
        primaries = [em for em in detail["emails"] if em["is_primary"]]
        assert len(primaries) == 1
        assert primaries[0]["email"] == "new@x.com"

    def test_delete_phone_and_email(self, client: TestClient, admin_token: str):
        p = _create_provider(
            client, admin_token, "Delete Contact",
            phones=[{"country_code": "+1", "number": "111"}],
            emails=[{"email": "a@x.com"}],
        )
        phone_id = p["phones"][0]["id"]
        email_id = p["emails"][0]["id"]
        assert client.delete(
            f"{BASE}/{p['id']}/phones/{phone_id}", headers=_auth(admin_token)
        ).status_code == 204
        assert client.delete(
            f"{BASE}/{p['id']}/emails/{email_id}", headers=_auth(admin_token)
        ).status_code == 204
        detail = client.get(f"{BASE}/{p['id']}", headers=_auth(admin_token)).json()
        assert detail["phones"] == []
        assert detail["emails"] == []

    def test_404s_for_unknown_ids(self, client: TestClient, admin_token: str):
        p = _create_provider(client, admin_token, "404 Contact")
        missing = uuid.uuid4()
        assert client.delete(
            f"{BASE}/{p['id']}/phones/{missing}", headers=_auth(admin_token)
        ).status_code == 404
        assert client.delete(
            f"{BASE}/{p['id']}/emails/{missing}", headers=_auth(admin_token)
        ).status_code == 404
        assert client.post(
            f"{BASE}/{missing}/phones",
            json={"country_code": "+1", "number": "1"},
            headers=_auth(admin_token),
        ).status_code == 404
        assert client.post(
            f"{BASE}/{missing}/emails",
            json={"email": "x@x.com"},
            headers=_auth(admin_token),
        ).status_code == 404

    def test_blank_entries_rejected(self, client: TestClient, admin_token: str):
        p = _create_provider(client, admin_token, "Blank Contact")
        assert client.post(
            f"{BASE}/{p['id']}/phones",
            json={"country_code": "+1", "number": "   "},
            headers=_auth(admin_token),
        ).status_code == 422
        assert client.post(
            f"{BASE}/{p['id']}/emails",
            json={"email": ""},
            headers=_auth(admin_token),
        ).status_code == 422

    def test_list_shows_primary_contact(self, client: TestClient, admin_token: str):
        _create_provider(
            client, admin_token, "Primary In List",
            phones=[
                {"country_code": "+44", "number": "20 1234", "is_primary": True},
                {"country_code": "+1", "number": "999"},
            ],
            emails=[
                {"email": "second@list.com"},
                {"email": "first@list.com", "is_primary": True},
            ],
        )
        resp = client.get(BASE, params={"search": "Primary In List"}, headers=_auth(admin_token))
        item = resp.json()["data"][0]
        assert item["email"] == "first@list.com"
        assert item["phone"] == "+44 20 1234"

    def test_legacy_provider_without_entries_falls_back(self, client: TestClient, admin_token: str):
        # Simulate a provider from before the migration: legacy columns set,
        # no phone/email entries.
        p = _create_provider(
            client, admin_token, "Legacy Fallback",
            email="legacy@x.com", phone="+1 555 legacy",
        )
        detail = client.get(f"{BASE}/{p['id']}", headers=_auth(admin_token)).json()
        assert detail["phones"] == []
        assert detail["emails"] == []
        assert detail["email"] == "legacy@x.com"
        resp = client.get(BASE, params={"search": "Legacy Fallback"}, headers=_auth(admin_token))
        item = resp.json()["data"][0]
        assert item["email"] == "legacy@x.com"
        assert item["phone"] == "+1 555 legacy"


# ── Doctor professional profile via provider endpoints ───────────────────────

class TestDoctorProfessionalFields:
    PROFILE = {
        "professional_title": "Consultant Cardiologist",
        "biography": "20 years in cardiology.",
        "years_experience": 20,
        "experience_description": "Formerly at Mercy Hospital.",
    }

    def test_create_doctor_with_profile(self, client: TestClient, admin_token: str):
        data = _create_provider(
            client, admin_token, "Dr. Alice", provider_type="DOCTOR", **self.PROFILE
        )
        assert data["doctor_profile"] == self.PROFILE

    def test_profile_persists_on_get(self, client: TestClient, admin_token: str):
        created = _create_provider(
            client, admin_token, "Dr. Bob", provider_type="DOCTOR", **self.PROFILE
        )
        resp = client.get(f"{BASE}/{created['id']}", headers=_auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["doctor_profile"] == self.PROFILE

    def test_create_doctor_without_profile_fields(self, client: TestClient, admin_token: str):
        data = _create_provider(client, admin_token, "Dr. Blank", provider_type="DOCTOR")
        assert data["doctor_profile"] is None

    def test_update_doctor_profile_fields(self, client: TestClient, admin_token: str):
        created = _create_provider(client, admin_token, "Dr. Carol", provider_type="DOCTOR")
        resp = client.patch(
            f"{BASE}/{created['id']}",
            json={"professional_title": "Surgeon", "years_experience": 5},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        dp = resp.json()["doctor_profile"]
        assert dp["professional_title"] == "Surgeon"
        assert dp["years_experience"] == 5
        assert dp["biography"] is None

    def test_partial_update_preserves_other_profile_fields(self, client: TestClient, admin_token: str):
        created = _create_provider(
            client, admin_token, "Dr. Dan", provider_type="DOCTOR", **self.PROFILE
        )
        resp = client.patch(
            f"{BASE}/{created['id']}",
            json={"professional_title": "Updated Title"},
            headers=_auth(admin_token),
        )
        dp = resp.json()["doctor_profile"]
        assert dp["professional_title"] == "Updated Title"
        assert dp["biography"] == self.PROFILE["biography"]
        assert dp["years_experience"] == 20

    def test_update_can_clear_profile_field(self, client: TestClient, admin_token: str):
        created = _create_provider(
            client, admin_token, "Dr. Eve", provider_type="DOCTOR", **self.PROFILE
        )
        resp = client.patch(
            f"{BASE}/{created['id']}",
            json={"biography": None},
            headers=_auth(admin_token),
        )
        assert resp.json()["doctor_profile"]["biography"] is None

    def test_profile_fields_ignored_for_hospital(self, client: TestClient, admin_token: str):
        data = _create_provider(
            client, admin_token, "Hosp NoProfile", provider_type="HOSPITAL", **self.PROFILE
        )
        assert data["doctor_profile"] is None
        resp = client.patch(
            f"{BASE}/{data['id']}",
            json={"professional_title": "Nope"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["doctor_profile"] is None

    def test_profile_fields_ignored_for_clinic(self, client: TestClient, admin_token: str):
        data = _create_provider(
            client, admin_token, "Clinic NoProfile", provider_type="CLINIC", **self.PROFILE
        )
        assert data["doctor_profile"] is None

    def test_years_experience_out_of_range_rejected(self, client: TestClient, admin_token: str):
        resp = client.post(
            BASE,
            json=_provider_body("Dr. Bad", provider_type="DOCTOR", years_experience=101),
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422

    def test_professional_title_too_long_rejected(self, client: TestClient, admin_token: str):
        resp = client.post(
            BASE,
            json=_provider_body("Dr. Long", provider_type="DOCTOR", professional_title="x" * 201),
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422

    def test_legacy_doctor_data_visible_via_provider_endpoint(
        self, client: TestClient, admin_token: str
    ):
        """Doctors created through the legacy doctor API keep their profile,
        qualifications, and affiliations when opened via provider records."""
        # Create an organization and a doctor through the legacy doctor API.
        org = _create_provider(client, admin_token, "Affil Hospital", provider_type="HOSPITAL")
        resp = client.post(
            "/api/v1/admin/doctors",
            json={
                "name": "Dr. Legacy",
                "visit_stability": "STABLE_VISIT",
                "professional_title": "Old-School Surgeon",
                "biography": "Bio via legacy API.",
                "years_experience": 30,
                "experience_description": "Long career.",
                "organization_ids": [org["id"]],
                "primary_organization_id": org["id"],
            },
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201, resp.text
        doctor_id = resp.json()["id"]
        client.post(
            f"/api/v1/admin/doctors/{doctor_id}/qualifications",
            json={"title": "MBBS", "institution": "Old University", "year_obtained": 1996},
            headers=_auth(admin_token),
        )

        # The unified provider endpoint returns the professional profile…
        resp = client.get(f"{BASE}/{doctor_id}", headers=_auth(admin_token))
        assert resp.status_code == 200
        dp = resp.json()["doctor_profile"]
        assert dp["professional_title"] == "Old-School Surgeon"
        assert dp["years_experience"] == 30

        # …and updating through the provider endpoint keeps quals/affiliations.
        resp = client.patch(
            f"{BASE}/{doctor_id}",
            json={"professional_title": "Modern Surgeon"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["doctor_profile"]["professional_title"] == "Modern Surgeon"

        resp = client.get(f"/api/v1/admin/doctors/{doctor_id}", headers=_auth(admin_token))
        data = resp.json()
        assert [q["title"] for q in data["qualifications"]] == ["MBBS"]
        assert len(data["organizations"]) == 1
        assert data["organizations"][0]["is_primary"] is True
