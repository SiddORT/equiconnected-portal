"""Verified member profile access, ownership, validation, and persistence tests."""
from datetime import datetime, timezone
from app.core.security import create_access_token, hash_password
from app.repositories.user_repository import UserRepository
from app.api.v1 import profile as profile_router

BASE = "/api/v1/profile"


def _member(db, *, email: str, roles: list[str]):
    repo = UserRepository(db)
    resolved = []
    for name in roles:
        role = repo.get_role_by_name(name)
        if role is None:
            role = repo.create_role(name)
        resolved.append(role)
    user = repo.create_user(
        email=email,
        password_hash=hash_password("MemberPassword1"),
        role=resolved[0],
        roles=resolved,
        first_name="Member",
        last_name="Person",
        mobile_number="+1 555 123 4567",
        country="United States",
        city="Austin",
    )
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _personal():
    return {
        "first_name": "Amina", "last_name": "Rider", "mobile_number": "+1 555 123 4567",
        "address": "12 Oak Lane", "country": "United States", "state_province": "Texas",
        "city": "Austin", "postal_code": "78701",
    }


class TestMemberProfile:
    def test_requires_verified_member_and_returns_only_current_profile(self, client, db, seeded_admin):
        admin, _ = seeded_admin
        assert client.get(BASE).status_code == 401
        assert client.get(f"{BASE}/postal-lookup", params={"country": "United States", "postal_code": "78701"}).status_code == 401
        assert client.get(BASE, headers=_headers(admin)).status_code == 403

        owner = _member(db, email="owner@example.com", roles=["horse_owner"])
        response = client.get(BASE, headers=_headers(owner))
        assert response.status_code == 200
        assert response.json()["roles"] == ["horse_owner"]
        assert response.json()["email"] == "owner@example.com"

    def test_personal_and_stable_sections_save_independently(self, client, db):
        member = _member(db, email="stable@example.com", roles=["stable_manager"])
        headers = _headers(member)
        assert client.put(f"{BASE}/personal", headers=headers, json=_personal()).status_code == 200
        stable = {
            "name": "Oak Valley Stables", "description": "Boarding and training",
            "address": "14 Oak Lane", "country": "United States", "state_province": "Texas",
            "city": "Austin", "postal_code": "78701", "contact_name": "Amina Rider",
            "contact_phone": "+1 555 123 4567", "contact_email": "stable@example.com",
        }
        response = client.put(f"{BASE}/stable", headers=headers, json=stable)
        assert response.status_code == 200
        saved = client.get(BASE, headers=headers).json()
        assert saved["address"] == "12 Oak Lane"
        assert saved["stable_profile"]["name"] == "Oak Valley Stables"
        assert client.post(f"{BASE}/horses", headers=headers, json={"name": "Nope", "sex": "MARE"}).status_code == 403

    def test_horses_are_role_gated_validated_and_owner_scoped(self, client, db):
        owner = _member(db, email="owner@example.com", roles=["horse_owner"])
        other = _member(db, email="other@example.com", roles=["horse_owner"])
        headers = _headers(owner)
        assert client.post(f"{BASE}/horses", headers=headers, json={"sex": "MARE"}).status_code == 422
        created = client.post(
            f"{BASE}/horses", headers=headers,
            json={"name": "Juniper", "sex": "MARE", "registered_name": "Juniper Rose", "breed": "Warmblood"},
        )
        assert created.status_code == 201
        horse_id = created.json()["id"]
        assert client.put(f"{BASE}/horses/{horse_id}", headers=_headers(other), json={"name": "Stolen", "sex": "MARE"}).status_code == 404
        assert client.delete(f"{BASE}/horses/{horse_id}", headers=_headers(other)).status_code == 404
        update = client.put(f"{BASE}/horses/{horse_id}", headers=headers, json={"name": "Juniper", "sex": "MARE", "color": "Bay"})
        assert update.status_code == 200
        assert update.json()["color"] == "Bay"
        assert client.delete(f"{BASE}/horses/{horse_id}", headers=headers).status_code == 204

    def test_photo_rules_and_postal_lookup_fallback(self, client, db, monkeypatch):
        owner = _member(db, email="photo@example.com", roles=["horse_owner"])
        headers = _headers(owner)
        horse = client.post(f"{BASE}/horses", headers=headers, json={"name": "Comet", "sex": "COLT"}).json()
        assert client.post(
            f"{BASE}/horses/{horse['id']}/photo", headers=headers,
            files={"file": ("not-an-image.txt", b"nope", "text/plain")},
        ).status_code == 422
        assert client.post(
            f"{BASE}/horses/{horse['id']}/photo", headers=headers,
            files={"file": ("big.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")},
        ).status_code == 413
        monkeypatch.setattr(
            profile_router,
            "get_settings",
            lambda: type("Settings", (), {"POSTAL_LOOKUP_URL": ""})(),
        )
        lookup = client.get(
            f"{BASE}/postal-lookup",
            headers=headers,
            params={"country": "United States", "postal_code": "78701"},
        )
        assert lookup.status_code == 200
        # The real default is exercised in the success test below. This test
        # verifies an intentionally disabled deployment remains non-fatal.
        assert lookup.json()["status"] == "unavailable"

    def test_postal_lookup_normalizes_default_source_result(self, client, db, monkeypatch):
        class Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"places": [{"place name": "Round Rock", "state": "Texas"}]}

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def get(self, *_args, **_kwargs):
                return Response()

        requested = []
        original_get = Client.get

        async def record_get(self, url, *args, **kwargs):
            requested.append(url)
            return await original_get(self, url, *args, **kwargs)

        Client.get = record_get
        monkeypatch.setattr(profile_router.httpx, "AsyncClient", lambda **_kwargs: Client())
        member = _member(db, email="lookup@example.com", roles=["horse_owner"])
        response = client.get(
            f"{BASE}/postal-lookup",
            headers=_headers(member),
            params={"country": "United States", "postal_code": "78664"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "match", "city": "Round Rock", "state_province": "Texas"}
        assert requested and "nominatim.openstreetmap.org" in requested[0]