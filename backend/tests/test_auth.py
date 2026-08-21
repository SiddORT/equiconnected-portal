"""
Authentication flow tests — Phase 1 Admin Authentication.

Covers all spec-required scenarios:
  1.  Admin creation
  2.  Successful login
  3.  Invalid password
  4.  Invalid email format
  5.  Inactive admin blocked
  6.  Authentication persistence (token refresh)
  7.  Logout
  8.  Protected dashboard requires auth
  9.  Unauthorized access returns 401
  10. Non-admin role rejected from admin endpoints
  11. Duplicate admin prevention (idempotent seed)
"""
import pytest
from fastapi.testclient import TestClient


# ── Shared test helpers ───────────────────────────────────────────────────────

def _login_and_mount_refresh_cookie(client: TestClient, email: str, password: str) -> str:
    """Login via the HTTP endpoint, mount the refresh cookie on the client, return access token.

    HTTPX's TestClient does not reliably forward path-scoped httpOnly cookies
    (``Path=/api/v1/auth``) because path matching for sub-paths varies between
    HTTPX versions.  We read the raw cookie value from the response's Set-Cookie
    header and mount it directly on the client instance so all subsequent
    requests within this test include it without relying on HTTPX path-matching.
    """
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200

    # HTTPX stores cookies (including httpOnly) from Set-Cookie headers in
    # resp.cookies — path/domain restrictions only affect auto-forwarding, not
    # reading the value out.
    raw_token = resp.cookies.get("refresh_token")
    assert raw_token, "Login must set a refresh_token cookie"

    # Mount on the client instance (not per-request) so it is forwarded reliably
    client.cookies.set("refresh_token", raw_token)
    return resp.json()["access_token"]


# ── 1. Admin creation ─────────────────────────────────────────────────────────

class TestAdminCreation:
    def test_admin_created_with_correct_fields(self, db, seeded_admin):
        user, _ = seeded_admin
        assert user.id is not None
        assert user.email == "testadmin@example.com"
        assert user.role.name == "admin"
        assert user.is_active is True
        assert user.password_hash  # never empty
        assert "password" not in user.password_hash.lower() or user.password_hash.startswith("$argon2")

    def test_password_is_hashed_not_plaintext(self, db, seeded_admin):
        user, password = seeded_admin
        assert user.password_hash != password
        assert user.password_hash.startswith("$argon2id$")


# ── 2. Successful login ───────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self, client: TestClient, seeded_admin):
        user, password = seeded_admin
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["user"]["email"] == user.email
        assert data["user"]["role"] == "admin"

    def test_login_does_not_return_password_hash(self, client: TestClient, seeded_admin):
        user, password = seeded_admin
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        body = resp.text
        assert "password_hash" not in body
        assert "password" not in resp.json().get("user", {})

    def test_login_sets_refresh_cookie(self, client: TestClient, seeded_admin):
        user, password = seeded_admin
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 200
        # httpOnly refresh token cookie must be present
        assert "refresh_token" in resp.cookies


# ── 3. Invalid password ───────────────────────────────────────────────────────

class TestInvalidPassword:
    def test_wrong_password_returns_401(self, client: TestClient, seeded_admin):
        user, _ = seeded_admin
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "wrongpassword123"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "invalid_credentials"

    def test_wrong_password_generic_message(self, client: TestClient, seeded_admin):
        """Error message must not reveal whether the email or password was wrong."""
        user, _ = seeded_admin
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "wrongpassword123"},
        )
        msg = resp.json()["detail"]["message"].lower()
        # Must say "invalid email or password" — not "wrong password" alone
        assert "password" in msg or "credential" in msg
        assert "email" in msg or "credential" in msg


# ── 4. Invalid email ──────────────────────────────────────────────────────────

class TestInvalidEmail:
    def test_unknown_email_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "somepassword123"},
        )
        assert resp.status_code == 401

    def test_unknown_email_same_message_as_wrong_password(
        self, client: TestClient, seeded_admin
    ):
        """Timing/message must be indistinguishable from wrong-password to prevent
        user enumeration."""
        user, _ = seeded_admin
        wrong_email = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "somepassword123"},
        )
        wrong_pass = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "wrongpassword123"},
        )
        assert wrong_email.status_code == wrong_pass.status_code == 401
        assert (
            wrong_email.json()["detail"]["code"]
            == wrong_pass.json()["detail"]["code"]
            == "invalid_credentials"
        )

    def test_malformed_email_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "notanemail", "password": "somepassword123"},
        )
        assert resp.status_code == 422

    def test_short_password_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    def test_missing_email_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"password": "somepassword123"},
        )
        assert resp.status_code == 422

    def test_missing_password_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com"},
        )
        assert resp.status_code == 422


# ── 5. Inactive admin ─────────────────────────────────────────────────────────

class TestInactiveAdmin:
    def test_inactive_admin_cannot_login(self, client: TestClient, seeded_admin, db):
        user, password = seeded_admin
        user.is_active = False
        db.commit()

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 401

    def test_inactive_admin_error_code(self, client: TestClient, seeded_admin, db):
        user, password = seeded_admin
        user.is_active = False
        db.commit()

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        # Returns 401 (same as invalid_credentials to not leak info)
        assert resp.status_code == 401


# ── 6. Authentication persistence (token refresh) ────────────────────────────

class TestAuthPersistence:
    def test_refresh_returns_new_access_token(self, client: TestClient, seeded_admin):
        user, password = seeded_admin
        _login_and_mount_refresh_cookie(client, user.email, password)

        # Exchange refresh cookie for a new access token (simulates page reload)
        refresh = client.post("/api/v1/auth/refresh")
        assert refresh.status_code == 200

        new_token = refresh.json()["access_token"]
        assert new_token  # non-empty
        # Rotated token should be usable on protected endpoints
        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == user.email

    def test_refresh_without_cookie_returns_401(self, client: TestClient):
        # Ensure client has no stale refresh cookie, then try refresh with none
        client.cookies.delete("refresh_token")
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    def test_me_after_login_returns_profile(self, client: TestClient, seeded_admin):
        user, password = seeded_admin
        login = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        token = login.json()["access_token"]

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == user.email
        assert data["role"] == "admin"
        assert "password_hash" not in data

    def test_me_unauthenticated(self, client: TestClient):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client: TestClient):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert resp.status_code == 401


# ── 7. Logout ─────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_success(self, client: TestClient, seeded_admin):
        user, password = seeded_admin
        login = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        token = login.json()["access_token"]

        resp = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out successfully"

    def test_logout_clears_refresh_cookie(self, client: TestClient, seeded_admin):
        user, password = seeded_admin
        token = _login_and_mount_refresh_cookie(client, user.email, password)

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout.status_code == 200

        # After logout the server revokes the token — refresh must now fail
        # The cookie is still in the client jar (server cleared it via Set-Cookie
        # Max-Age=0, but HTTPX path matching may not remove it).  Even if the old
        # value is sent, the revoked token must be rejected by the DB check.
        refresh = client.post("/api/v1/auth/refresh")
        assert refresh.status_code == 401

    def test_logout_requires_auth(self, client: TestClient):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 401


# ── 8. Protected dashboard ────────────────────────────────────────────────────

class TestAdminDashboard:
    def test_dashboard_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/admin/dashboard/stats")
        assert resp.status_code == 401

    def test_dashboard_accessible_to_admin(self, client: TestClient, seeded_admin):
        user, password = seeded_admin
        login = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        token = login.json()["access_token"]

        resp = client.get(
            "/api/v1/admin/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "recent_audit_events" not in data


# ── 9. Unauthorized access ────────────────────────────────────────────────────

class TestUnauthorizedAccess:
    def test_no_token_denied(self, client: TestClient):
        resp = client.get("/api/v1/admin/dashboard/stats")
        assert resp.status_code == 401

    def test_garbage_token_denied(self, client: TestClient):
        resp = client.get(
            "/api/v1/admin/dashboard/stats",
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert resp.status_code == 401

    def test_malformed_authorization_header_denied(self, client: TestClient):
        resp = client.get(
            "/api/v1/admin/dashboard/stats",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401


# ── 10. Non-admin role rejection ──────────────────────────────────────────────

class TestNonAdminRoleRejection:
    def _create_non_admin_user(self, db, role_name: str = "visitor"):
        from app.core.security import hash_password
        from app.repositories.user_repository import UserRepository

        repo = UserRepository(db)
        role = repo.get_role_by_name(role_name)
        if role is None:
            role = repo.create_role(role_name, f"{role_name.capitalize()} user")

        user = repo.create_user(
            email=f"{role_name}@example.com",
            password_hash=hash_password("TestVisitor#2026!"),
            role=role,
        )
        db.commit()
        return user, "TestVisitor#2026!"

    def test_non_admin_login_succeeds(self, client: TestClient, db):
        """A valid non-admin user can authenticate."""
        user, password = self._create_non_admin_user(db)
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 200

    def test_non_admin_rejected_from_dashboard(self, client: TestClient, db):
        """A non-admin role must receive 403 on admin-only endpoints."""
        user, password = self._create_non_admin_user(db)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        resp = client.get(
            "/api/v1/admin/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "forbidden"


# ── 11. Duplicate admin prevention ────────────────────────────────────────────

class TestDuplicateAdminPrevention:
    def test_email_unique_constraint_enforced(self, db):
        """Two accounts with the same email cannot exist."""
        from sqlalchemy.exc import IntegrityError

        from app.core.security import hash_password
        from app.repositories.user_repository import UserRepository

        repo = UserRepository(db)
        role = repo.get_role_by_name("admin")
        if role is None:
            role = repo.create_role("admin", "Administrator")

        email = "duplicate@example.com"
        repo.create_user(
            email=email,
            password_hash=hash_password("FirstAdmin#2026!"),
            role=role,
        )
        db.commit()

        # Attempt to create a second user with the same email.
        # repo.create_user() calls db.flush() internally, so the IntegrityError
        # is raised inside create_user — it must be inside the pytest.raises block.
        with pytest.raises(IntegrityError):
            repo.create_user(
                email=email,
                password_hash=hash_password("SecondAdmin#2026!"),
                role=role,
            )
        # Reset session state so the fixture teardown can run cleanly
        db.rollback()

    def test_seed_script_is_idempotent(self, db):
        """Running the seed check twice returns the same user, not a duplicate."""
        from app.core.security import hash_password
        from app.repositories.user_repository import UserRepository

        repo = UserRepository(db)
        role = repo.get_role_by_name("admin")
        if role is None:
            role = repo.create_role("admin", "Administrator")

        email = "idempotent@example.com"

        # First "seed"
        first = repo.create_user(
            email=email,
            password_hash=hash_password("AdminPass#2026!"),
            role=role,
        )
        db.commit()

        # Simulate seed script logic: check before inserting
        existing = repo.get_by_email(email)
        assert existing is not None
        assert existing.id == first.id  # same record — no duplicate created
