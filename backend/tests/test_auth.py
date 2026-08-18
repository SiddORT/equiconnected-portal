"""
Authentication flow tests.
"""
import pytest
from fastapi.testclient import TestClient


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
        assert data["user"]["email"] == user.email
        assert "password" not in data
        assert "password_hash" not in data

    def test_login_wrong_password(self, client: TestClient, seeded_admin):
        user, _ = seeded_admin
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "wrongpassword123"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "invalid_credentials"

    def test_login_unknown_email(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "somepassword123"},
        )
        assert resp.status_code == 401

    def test_login_invalid_email_format(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "notanemail", "password": "somepassword123"},
        )
        assert resp.status_code == 422

    def test_login_short_password_rejected(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "short"},
        )
        assert resp.status_code == 422


class TestMe:
    def test_me_authenticated(self, client: TestClient, seeded_admin):
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
        assert "recent_audit_events" in data
