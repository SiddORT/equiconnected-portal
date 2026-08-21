"""Global time-standard persistence, access, and DST boundary coverage."""
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.time_standards import local_date_bounds
from app.models.audit_log import AuditLog
from app.repositories.audit_repository import AuditRepository


PUBLIC_URL = "/api/v1/system-settings"
ADMIN_URL = "/api/v1/admin/system-settings"


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_token(client: TestClient, seeded_admin) -> str:
    return _login(client, seeded_admin[0].email, seeded_admin[1])


class TestSystemSettingsAccess:
    def test_public_read_initializes_safe_persisted_defaults(self, client: TestClient):
        response = client.get(PUBLIC_URL)
        assert response.status_code == 200, response.text
        assert response.json() == {
            "timezone": "UTC",
            "date_format": "month_day_year",
            "time_format": "12_hour",
        }
        assert client.get(PUBLIC_URL).json() == response.json()
        assert client.patch(PUBLIC_URL, json={}).status_code == 405

    def test_admin_only_read_and_update_with_validation(self, client: TestClient, admin_token: str):
        assert client.get(ADMIN_URL).status_code == 401
        payload = {
            "timezone": "America/New_York",
            "date_format": "day_month_year",
            "time_format": "24_hour",
        }
        updated = client.patch(ADMIN_URL, json=payload, headers=_auth(admin_token))
        assert updated.status_code == 200, updated.text
        assert updated.json() == payload
        assert client.get(PUBLIC_URL).json() == payload
        assert client.get(ADMIN_URL, headers=_auth(admin_token)).json() == payload

        invalid_timezone = client.patch(
            ADMIN_URL,
            json={**payload, "timezone": "Not/A_Zone"},
            headers=_auth(admin_token),
        )
        assert invalid_timezone.status_code == 422
        invalid_format = client.patch(
            ADMIN_URL,
            json={**payload, "date_format": "local_browser_default"},
            headers=_auth(admin_token),
        )
        assert invalid_format.status_code == 422


class TestSystemTimezoneCalendarBoundaries:
    def test_dst_day_uses_the_next_local_midnight_as_the_exclusive_end(self):
        start, end = local_date_bounds(
            date(2026, 3, 8),
            date(2026, 3, 8),
            "America/New_York",
        )
        assert start == datetime(2026, 3, 8, 5, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 3, 9, 4, 0, tzinfo=timezone.utc)

    def test_activity_filter_uses_the_saved_system_calendar_day(
        self, client: TestClient, db, admin_token: str
    ):
        update = client.patch(
            ADMIN_URL,
            json={
                "timezone": "America/New_York",
                "date_format": "month_day_year",
                "time_format": "12_hour",
            },
            headers=_auth(admin_token),
        )
        assert update.status_code == 200, update.text
        before = AuditRepository(db).log(action="before.local.day", summary="Before")
        inside = AuditRepository(db).log(action="inside.local.day", summary="Inside")
        after = AuditRepository(db).log(action="after.local.day", summary="After")
        before.created_at = datetime(2026, 1, 2, 4, 59, tzinfo=timezone.utc)
        inside.created_at = datetime(2026, 1, 2, 5, 0, tzinfo=timezone.utc)
        after.created_at = datetime(2026, 1, 3, 5, 0, tzinfo=timezone.utc)
        db.commit()

        response = client.get(
            "/api/v1/admin/activity-logs",
            params={"date_from": "2026-01-02", "date_to": "2026-01-02", "page_size": 100},
            headers=_auth(admin_token),
        )
        assert response.status_code == 200, response.text
        assert [row["action"] for row in response.json()["data"]] == ["inside.local.day"]