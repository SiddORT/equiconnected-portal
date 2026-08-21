"""Read-only administrator visibility for public member registrations."""
from datetime import datetime, timezone

from app.core.security import hash_password
from app.repositories.user_repository import UserRepository


USERS_URL = "/api/v1/admin/users"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_token(client, seeded_admin) -> str:
    admin, password = seeded_admin
    response = client.post("/api/v1/auth/login", json={"email": admin.email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _registrant(db, *, email: str, roles: tuple[str, ...] = ("horse_owner",), verified: bool = False):
    repo = UserRepository(db)
    available = {
        name: repo.get_role_by_name(name) or repo.create_role(name, f"Public {name}")
        for name in ("horse_owner", "stable_manager")
    }
    selected = [available[name] for name in roles]
    user = repo.create_user(
        email=email,
        password_hash=hash_password("HorseCare2026"),
        role=selected[0],
        roles=selected,
        first_name="Amina",
        last_name="Rider",
        mobile_number="+971 50 123 4567",
        country="United Arab Emirates",
        city="Dubai",
    )
    if verified:
        user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return user


class TestAdminUserDirectory:
    def test_lists_filters_and_excludes_administrators(self, client, db, seeded_admin):
        token = _admin_token(client, seeded_admin)
        _registrant(db, email="verified-owner@example.com", verified=True)
        _registrant(db, email="unverified-manager@example.com", roles=("stable_manager",))

        response = client.get(
            USERS_URL,
            params={"search": "Amina", "role": "stable_manager", "email_verified": "false"},
            headers=_auth(token),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["total"] == 1
        account = body["data"][0]
        assert account["email"] == "unverified-manager@example.com"
        assert account["roles"] == ["stable_manager"]
        assert account["email_verified_at"] is None
        assert "password_hash" not in account
        assert not any(key.startswith("approval") for key in account)

    def test_details_are_read_only_and_decision_routes_do_not_exist(self, client, db, seeded_admin):
        token = _admin_token(client, seeded_admin)
        registrant = _registrant(db, email="member@example.com", verified=True)

        detail = client.get(f"{USERS_URL}/{registrant.id}", headers=_auth(token))
        assert detail.status_code == 200
        assert detail.json()["email_verified_at"] is not None
        assert client.post(f"{USERS_URL}/{registrant.id}/approve", headers=_auth(token)).status_code == 404
        assert client.post(f"{USERS_URL}/{registrant.id}/reject", headers=_auth(token)).status_code == 404

    def test_directory_remains_admin_only(self, client, db, seeded_admin):
        registrant = _registrant(db, email="member@example.com", verified=True)
        assert client.get(USERS_URL).status_code == 401
        login = client.post(
            "/api/v1/auth/login",
            json={"email": registrant.email, "password": "HorseCare2026"},
        )
        assert login.status_code == 200
        assert client.get(USERS_URL, headers=_auth(login.json()["access_token"])).status_code == 403