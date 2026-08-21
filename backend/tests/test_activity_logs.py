"""Activity-log API and safe audit event coverage."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService

URL = "/api/v1/admin/activity-logs"


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_token(client: TestClient, seeded_admin) -> str:
    user, password = seeded_admin
    return _login(client, user.email, password)


class TestActivityLogsSecurity:
    def test_requires_an_administrator(self, client: TestClient, db):
        assert client.get(URL).status_code == 401
        repo = UserRepository(db)
        visitor = repo.get_role_by_name("visitor") or repo.create_role("visitor", "Visitor")
        repo.create_user(
            email="visitor@example.com",
            password_hash=hash_password("Visitor#2026!"),
            role=visitor,
        )
        db.commit()
        token = _login(client, "visitor@example.com", "Visitor#2026!")
        assert client.get(URL, headers=_auth(token)).status_code == 403


class TestActivityLogQuery:
    def test_newest_first_pagination_and_inclusive_date_boundaries(
        self, client: TestClient, db, admin_token: str
    ):
        events = [
            ("test.older", datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc)),
            ("test.boundary", datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)),
            ("test.newer", datetime(2026, 1, 2, 23, 59, tzinfo=timezone.utc)),
        ]
        for action, created_at in events:
            entry = AuditRepository(db).log(action=action, summary=action)
            entry.created_at = created_at
        db.commit()

        response = client.get(
            URL,
            params={"date_from": "2026-01-02", "date_to": "2026-01-02", "page_size": 1},
            headers=_auth(admin_token),
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["meta"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}
        assert payload["data"][0]["action"] == "test.newer"
        next_page = client.get(
            URL,
            params={"date_from": "2026-01-02", "date_to": "2026-01-02", "page": 2, "page_size": 1},
            headers=_auth(admin_token),
        ).json()
        assert next_page["data"][0]["action"] == "test.boundary"

    def test_redacts_sensitive_values_and_validates_ranges(
        self, client: TestClient, db, admin_token: str
    ):
        AuditRepository(db).log(
            action="test.safe",
            summary="Test safe audit event.",
            metadata={"recipient_email": "private@example.com", "token": "secret-token"},
            changes=[{"field": "phone", "before": "123", "after": "456"}],
        )
        db.commit()
        payload = client.get(URL, headers=_auth(admin_token)).json()["data"]
        event = next(row for row in payload if row["action"] == "test.safe")
        assert event["metadata"]["recipient_email"] == "[redacted]"
        assert event["metadata"]["token"] == "[redacted]"
        assert event["changes"][0]["before"] == "[redacted]"
        assert "private@example.com" not in str(event)
        invalid = client.get(
            URL,
            params={"date_from": "2026-02-01", "date_to": "2026-01-01"},
            headers=_auth(admin_token),
        )
        assert invalid.status_code == 422


class TestActivityEvents:
    def test_provider_specialization_and_invitation_actions_are_recorded(
        self, client: TestClient, admin_token: str, monkeypatch
    ):
        monkeypatch.setattr(EmailService, "send_invitation_email", lambda *args, **kwargs: None)
        specialization = client.post(
            "/api/v1/admin/specializations",
            json={"name": "Audit specialty", "is_active": True},
            headers=_auth(admin_token),
        )
        assert specialization.status_code == 201, specialization.text
        provider = client.post(
            "/api/v1/admin/providers",
            json={
                "provider_type": "HOSPITAL",
                "name": "Audit Hospital",
                "visit_stability": "STABLE_VISIT",
            },
            headers=_auth(admin_token),
        )
        assert provider.status_code == 201, provider.text
        invitation = client.post(
            "/api/v1/admin/invitations",
            json={
                "provider_id": provider.json()["id"],
                "provider_type": "HOSPITAL",
                "recipient_email": "invitee@example.com",
            },
            headers=_auth(admin_token),
        )
        assert invitation.status_code == 201, invitation.text
        actions = {
            item["action"]
            for item in client.get(URL, params={"page_size": 100}, headers=_auth(admin_token)).json()["data"]
        }
        assert {"provider.created", "specialization.created", "provider_invitation.created"} <= actions