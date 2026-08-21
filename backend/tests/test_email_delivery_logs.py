"""Administrator email delivery history and transactional-email logging tests."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailDeliveryError, EmailService


URL = "/api/v1/admin/email-logs"


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_public_roles(db) -> None:
    repo = UserRepository(db)
    for name in ("horse_owner", "stable_manager"):
        if repo.get_role_by_name(name) is None:
            repo.create_role(name, name.replace("_", " ").title())
    db.commit()


def _registration_payload(email: str) -> dict:
    return {
        "first_name": "Amina",
        "last_name": "Rider",
        "email": email,
        "mobile_number": "+971 50 123 4567",
        "country": "United Arab Emirates",
        "state_province": "Dubai",
        "city": "Dubai",
        "password": "HorseCare2026",
        "password_confirmation": "HorseCare2026",
        "role": "HORSE_OWNER",
        "accept_terms": True,
        "accept_privacy": True,
    }


class TestEmailLogAccessAndFilters:
    def test_requires_an_administrator(self, client: TestClient, db):
        assert client.get(URL).status_code == 401
        repo = UserRepository(db)
        visitor = repo.get_role_by_name("visitor") or repo.create_role("visitor", "Visitor")
        repo.create_user(
            email="email-log-visitor@example.com",
            password_hash=hash_password("Visitor#2026!"),
            role=visitor,
        )
        db.commit()
        token = _login(client, "email-log-visitor@example.com", "Visitor#2026!")
        assert client.get(URL, headers=_auth(token)).status_code == 403

    def test_all_date_filter_modes_are_inclusive_and_newest_first(
        self, client: TestClient, db, seeded_admin
    ):
        token = _login(client, seeded_admin[0].email, seeded_admin[1])
        entries = [
            ("old@example.com", datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)),
            ("jan-one@example.com", datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)),
            ("day-start@example.com", datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)),
            ("day-end@example.com", datetime(2026, 1, 2, 23, 59, tzinfo=timezone.utc)),
            ("feb@example.com", datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)),
        ]
        for recipient, created_at in entries:
            db.add(
                EmailDeliveryLog(
                    recipient_email=recipient,
                    purpose=EmailPurpose.ACCOUNT_VERIFICATION.value,
                    status=EmailDeliveryStatus.SUCCESS.value,
                    created_at=created_at,
                )
            )
        db.commit()

        day = client.get(
            URL,
            params={"filter_mode": "day", "date": "2026-01-02"},
            headers=_auth(token),
        ).json()
        assert [row["recipient_email"] for row in day["data"]] == [
            "day-end@example.com",
            "day-start@example.com",
        ]

        month = client.get(
            URL,
            params={"filter_mode": "month", "year": 2026, "month": 1},
            headers=_auth(token),
        ).json()
        assert month["meta"]["total"] == 3

        year = client.get(
            URL,
            params={"filter_mode": "year", "year": 2026},
            headers=_auth(token),
        ).json()
        assert year["meta"]["total"] == 4

        custom_range = client.get(
            URL,
            params={
                "filter_mode": "range",
                "date_from": "2026-01-02",
                "date_to": "2026-01-02",
                "page_size": 1,
            },
            headers=_auth(token),
        ).json()
        assert custom_range["meta"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}
        assert custom_range["data"][0]["recipient_email"] == "day-end@example.com"

        db.add(
            EmailDeliveryLog(
                recipient_email="terminal@example.com",
                purpose=EmailPurpose.ACCOUNT_VERIFICATION.value,
                status=EmailDeliveryStatus.SUCCESS.value,
                created_at=datetime(9999, 12, 31, 12, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()
        terminal = client.get(
            URL,
            params={"filter_mode": "day", "date": "9999-12-31"},
            headers=_auth(token),
        )
        assert terminal.status_code == 200, terminal.text
        assert terminal.json()["data"][0]["recipient_email"] == "terminal@example.com"

        invalid = client.get(
            URL,
            params={"filter_mode": "range", "date_from": "2026-02-02", "date_to": "2026-02-01"},
            headers=_auth(token),
        )
        assert invalid.status_code == 422


class TestTransactionalEmailDeliveryLogs:
    def test_verification_and_invitation_attempts_record_safe_success_and_failure(
        self, client: TestClient, db, seeded_admin, monkeypatch
    ):
        _seed_public_roles(db)
        admin_token = _login(client, seeded_admin[0].email, seeded_admin[1])
        monkeypatch.setattr(EmailService, "send_verification_email", lambda *_args, **_kwargs: None)

        verification_success = client.post(
            "/api/v1/auth/register",
            json=_registration_payload("verified-log@example.com"),
        )
        assert verification_success.status_code == 201, verification_success.text

        def failed_verification(*_args, **_kwargs):
            raise EmailDeliveryError("smtp-password=not-for-display")

        monkeypatch.setattr(EmailService, "send_verification_email", failed_verification)
        verification_failure = client.post(
            "/api/v1/auth/register",
            json=_registration_payload("failed-verified-log@example.com"),
        )
        assert verification_failure.status_code == 502

        monkeypatch.setattr(EmailService, "send_invitation_email", lambda *_args, **_kwargs: None)
        invitation = client.post(
            "/api/v1/admin/invitations",
            json={
                "recipient_email": "invite-log@example.com",
                "provider_type": "HOSPITAL",
                "visit_stability": "STABLE_VISIT",
            },
            headers=_auth(admin_token),
        )
        assert invitation.status_code == 201, invitation.text
        resent = client.post(
            f"/api/v1/admin/invitations/{invitation.json()['id']}/resend",
            headers=_auth(admin_token),
        )
        assert resent.status_code == 200, resent.text

        def failed_invitation(*_args, **_kwargs):
            raise EmailDeliveryError("smtp-password=not-for-display")

        monkeypatch.setattr(EmailService, "send_invitation_email", failed_invitation)
        resend_failure = client.post(
            f"/api/v1/admin/invitations/{invitation.json()['id']}/resend",
            headers=_auth(admin_token),
        )
        assert resend_failure.status_code == 502

        response = client.get(URL, params={"page_size": 25}, headers=_auth(admin_token))
        assert response.status_code == 200, response.text
        rows = response.json()["data"]
        verification_rows = [
            row for row in rows if row["purpose"] == EmailPurpose.ACCOUNT_VERIFICATION.value
        ]
        invitation_rows = [
            row for row in rows if row["purpose"] == EmailPurpose.PROVIDER_INVITATION.value
        ]
        assert {row["status"] for row in verification_rows} == {"success", "failed"}
        assert [row["status"] for row in invitation_rows].count("success") == 2
        failed = next(row for row in invitation_rows if row["status"] == "failed")
        assert failed["failure_message"] == "Unable to deliver email."
        assert "smtp-password" not in str(rows)
        assert "token" not in str(rows).lower()