"""
Specialization module tests — Phase 3.

Covers:
  1.  Unauthenticated users cannot access endpoints
  2.  Non-admin users cannot access endpoints
  3.  Admin can list specializations (empty state)
  4.  Admin can create a specialization
  5.  Required name validation
  6.  Duplicate name prevention
  7.  Admin can get a single specialization
  8.  Admin can update name
  9.  Admin can update description
  10. Duplicate name prevention on update
  11. Admin can deactivate a specialization
  12. Admin can reactivate a specialization
  13. Search filters by name substring
  14. Active/inactive filter works
  15. Pagination works
  16. Database unique constraint enforced at DB level
  17. Non-existent ID returns 404
  18. Name is trimmed of whitespace
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, create_access_token
from app.repositories.specialization_repository import SpecializationRepository
from app.repositories.user_repository import UserRepository


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_spec(client: TestClient, token: str, name: str, description: str | None = None) -> dict:
    body: dict = {"name": name}
    if description is not None:
        body["description"] = description
    resp = client.post("/api/v1/admin/specializations", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def admin_token(client: TestClient, seeded_admin) -> str:
    user, password = seeded_admin
    return _login(client, user.email, password)


@pytest.fixture()
def non_admin_token(client: TestClient, db) -> str:
    """Create a non-admin user and return their access token."""
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


# ── 1. Unauthenticated access ─────────────────────────────────────────────────

class TestUnauthenticated:
    def test_list_requires_auth(self, client: TestClient):
        assert client.get("/api/v1/admin/specializations").status_code == 401

    def test_create_requires_auth(self, client: TestClient):
        assert client.post("/api/v1/admin/specializations", json={"name": "X"}).status_code == 401

    def test_get_requires_auth(self, client: TestClient):
        import uuid
        assert client.get(f"/api/v1/admin/specializations/{uuid.uuid4()}").status_code == 401

    def test_update_requires_auth(self, client: TestClient):
        import uuid
        assert client.patch(f"/api/v1/admin/specializations/{uuid.uuid4()}", json={"name": "X"}).status_code == 401

    def test_status_requires_auth(self, client: TestClient):
        import uuid
        assert client.patch(f"/api/v1/admin/specializations/{uuid.uuid4()}/status", json={"is_active": False}).status_code == 401


# ── 2. Non-admin access ───────────────────────────────────────────────────────

class TestNonAdmin:
    def test_list_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        assert client.get("/api/v1/admin/specializations", headers=_auth(non_admin_token)).status_code == 403

    def test_create_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        assert client.post("/api/v1/admin/specializations", json={"name": "X"}, headers=_auth(non_admin_token)).status_code == 403


# ── 3. Empty list ─────────────────────────────────────────────────────────────

class TestListEmpty:
    def test_list_returns_empty_when_no_specializations(self, client: TestClient, admin_token: str):
        resp = client.get("/api/v1/admin/specializations", headers=_auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 0
        assert data["meta"]["page"] == 1


# ── 4. Create ─────────────────────────────────────────────────────────────────

class TestCreate:
    def test_create_returns_201(self, client: TestClient, admin_token: str):
        resp = client.post(
            "/api/v1/admin/specializations",
            json={"name": "Cardiology", "description": "Heart and cardiovascular system"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Cardiology"
        assert data["description"] == "Heart and cardiovascular system"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_without_description(self, client: TestClient, admin_token: str):
        resp = client.post(
            "/api/v1/admin/specializations",
            json={"name": "Neurology"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["description"] is None

    def test_create_inactive_specialization(self, client: TestClient, admin_token: str):
        resp = client.post(
            "/api/v1/admin/specializations",
            json={"name": "Archived", "is_active": False},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["is_active"] is False

    def test_create_appears_in_list(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Orthopedics")
        resp = client.get("/api/v1/admin/specializations", headers=_auth(admin_token))
        names = [s["name"] for s in resp.json()["data"]]
        assert "Orthopedics" in names


# ── 5. Required name validation ───────────────────────────────────────────────

class TestNameValidation:
    def test_empty_name_rejected(self, client: TestClient, admin_token: str):
        resp = client.post(
            "/api/v1/admin/specializations",
            json={"name": ""},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422

    def test_whitespace_only_name_rejected(self, client: TestClient, admin_token: str):
        resp = client.post(
            "/api/v1/admin/specializations",
            json={"name": "   "},
            headers=_auth(admin_token),
        )
        # After stripping, name becomes "" which fails min_length=1
        assert resp.status_code == 422

    def test_missing_name_rejected(self, client: TestClient, admin_token: str):
        resp = client.post(
            "/api/v1/admin/specializations",
            json={"description": "No name"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422

    def test_name_is_trimmed(self, client: TestClient, admin_token: str):
        resp = client.post(
            "/api/v1/admin/specializations",
            json={"name": "  Dermatology  "},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Dermatology"


# ── 6. Duplicate prevention ───────────────────────────────────────────────────

class TestDuplicatePrevention:
    def test_duplicate_name_returns_409(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Pediatrics")
        resp = client.post(
            "/api/v1/admin/specializations",
            json={"name": "Pediatrics"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "duplicate_specialization"

    def test_database_unique_constraint_enforced(self, client: TestClient, admin_token: str, db):
        """Constraint fires even if bypassing the service layer."""
        from app.models.specialization import Specialization
        spec1 = Specialization(name="Radiology", is_active=True)
        spec2 = Specialization(name="Radiology", is_active=True)
        db.add(spec1)
        db.flush()
        db.add(spec2)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


# ── 7. Get single ─────────────────────────────────────────────────────────────

class TestGetSingle:
    def test_get_existing_specialization(self, client: TestClient, admin_token: str):
        created = _create_spec(client, admin_token, "Oncology", "Cancer treatment")
        resp = client.get(f"/api/v1/admin/specializations/{created['id']}", headers=_auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Oncology"

    def test_get_nonexistent_returns_404(self, client: TestClient, admin_token: str):
        import uuid
        resp = client.get(f"/api/v1/admin/specializations/{uuid.uuid4()}", headers=_auth(admin_token))
        assert resp.status_code == 404


# ── 8–10. Update ──────────────────────────────────────────────────────────────

class TestUpdate:
    def test_update_name(self, client: TestClient, admin_token: str):
        created = _create_spec(client, admin_token, "OldName")
        resp = client.patch(
            f"/api/v1/admin/specializations/{created['id']}",
            json={"name": "NewName"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    def test_update_description(self, client: TestClient, admin_token: str):
        created = _create_spec(client, admin_token, "Psychiatry")
        resp = client.patch(
            f"/api/v1/admin/specializations/{created['id']}",
            json={"description": "Mental health"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Mental health"

    def test_update_to_duplicate_name_returns_409(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Allergy")
        b = _create_spec(client, admin_token, "Endocrinology")
        resp = client.patch(
            f"/api/v1/admin/specializations/{b['id']}",
            json={"name": "Allergy"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 409

    def test_update_nonexistent_returns_404(self, client: TestClient, admin_token: str):
        import uuid
        resp = client.patch(
            f"/api/v1/admin/specializations/{uuid.uuid4()}",
            json={"name": "X"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404

    def test_update_name_is_trimmed(self, client: TestClient, admin_token: str):
        created = _create_spec(client, admin_token, "Urology")
        resp = client.patch(
            f"/api/v1/admin/specializations/{created['id']}",
            json={"name": "  Urology Updated  "},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Urology Updated"


# ── 11–12. Activate / Deactivate ─────────────────────────────────────────────

class TestStatus:
    def test_deactivate_specialization(self, client: TestClient, admin_token: str):
        created = _create_spec(client, admin_token, "Geriatrics")
        resp = client.patch(
            f"/api/v1/admin/specializations/{created['id']}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_reactivate_specialization(self, client: TestClient, admin_token: str):
        created = _create_spec(client, admin_token, "Hematology")
        client.patch(
            f"/api/v1/admin/specializations/{created['id']}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        resp = client.patch(
            f"/api/v1/admin/specializations/{created['id']}/status",
            json={"is_active": True},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    def test_status_nonexistent_returns_404(self, client: TestClient, admin_token: str):
        import uuid
        resp = client.patch(
            f"/api/v1/admin/specializations/{uuid.uuid4()}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404

    def test_deactivated_record_persists_in_db(self, client: TestClient, admin_token: str):
        """Deactivation must NOT delete the record."""
        created = _create_spec(client, admin_token, "Nephrology")
        client.patch(
            f"/api/v1/admin/specializations/{created['id']}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        resp = client.get(f"/api/v1/admin/specializations/{created['id']}", headers=_auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


# ── 13. Search ────────────────────────────────────────────────────────────────

class TestSearch:
    def test_search_matches_substring(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Gastroenterology")
        _create_spec(client, admin_token, "Neurology")
        resp = client.get(
            "/api/v1/admin/specializations",
            params={"search": "gastro"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Gastroenterology"

    def test_search_is_case_insensitive(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Immunology")
        resp = client.get(
            "/api/v1/admin/specializations",
            params={"search": "IMMUNO"},
            headers=_auth(admin_token),
        )
        assert resp.json()["meta"]["total"] == 1

    def test_search_returns_empty_when_no_match(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Pulmonology")
        resp = client.get(
            "/api/v1/admin/specializations",
            params={"search": "zzznomatch"},
            headers=_auth(admin_token),
        )
        assert resp.json()["meta"]["total"] == 0


# ── 14. Active/Inactive filter ────────────────────────────────────────────────

class TestFilter:
    def test_filter_active_only(self, client: TestClient, admin_token: str):
        active = _create_spec(client, admin_token, "Rheumatology")
        inactive = _create_spec(client, admin_token, "OldSpec")
        client.patch(
            f"/api/v1/admin/specializations/{inactive['id']}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        resp = client.get(
            "/api/v1/admin/specializations",
            params={"is_active": "true"},
            headers=_auth(admin_token),
        )
        names = [s["name"] for s in resp.json()["data"]]
        assert "Rheumatology" in names
        assert "OldSpec" not in names

    def test_filter_inactive_only(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "ActiveSpec")
        inactive = _create_spec(client, admin_token, "InactiveSpec")
        client.patch(
            f"/api/v1/admin/specializations/{inactive['id']}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        resp = client.get(
            "/api/v1/admin/specializations",
            params={"is_active": "false"},
            headers=_auth(admin_token),
        )
        names = [s["name"] for s in resp.json()["data"]]
        assert "InactiveSpec" in names
        assert "ActiveSpec" not in names

    def test_no_filter_returns_all(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "S1")
        s2 = _create_spec(client, admin_token, "S2")
        client.patch(
            f"/api/v1/admin/specializations/{s2['id']}/status",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        resp = client.get("/api/v1/admin/specializations", headers=_auth(admin_token))
        assert resp.json()["meta"]["total"] == 2


# ── 15. Pagination ────────────────────────────────────────────────────────────

class TestPagination:
    def test_pagination_page_size(self, client: TestClient, admin_token: str):
        for i in range(5):
            _create_spec(client, admin_token, f"Spec{i:02d}")
        resp = client.get(
            "/api/v1/admin/specializations",
            params={"page": 1, "page_size": 3},
            headers=_auth(admin_token),
        )
        data = resp.json()
        assert len(data["data"]) == 3
        assert data["meta"]["total"] == 5
        assert data["meta"]["total_pages"] == 2

    def test_pagination_page_2(self, client: TestClient, admin_token: str):
        for i in range(5):
            _create_spec(client, admin_token, f"Page{i:02d}")
        resp = client.get(
            "/api/v1/admin/specializations",
            params={"page": 2, "page_size": 3},
            headers=_auth(admin_token),
        )
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["meta"]["page"] == 2

    def test_results_sorted_alphabetically(self, client: TestClient, admin_token: str):
        for name in ["Zebra", "Alpha", "Middle"]:
            _create_spec(client, admin_token, name)
        resp = client.get("/api/v1/admin/specializations", headers=_auth(admin_token))
        names = [s["name"] for s in resp.json()["data"]]
        assert names == sorted(names)
