"""Administrator email delivery history and transactional-email logging tests."""
from datetime import datetime, timezone
import smtplib
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy import select

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailDeliveryError, EmailService
from app.core.rate_limit import _smtp_test_attempts
from app.repositories.email_delivery_repository import EmailDeliveryRepository


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
        assert verification_failure.status_code == 201
        assert verification_failure.json()["email_sent"] is False

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


class TestSMTPTest:
    URL = f"{URL}/smtp-test"

    def test_admin_only_and_fixed_recipient(self, client, db, seeded_admin, monkeypatch):
        assert client.post(self.URL).status_code == 401
        repo = UserRepository(db)
        visitor = repo.get_role_by_name("visitor") or repo.create_role("visitor", "Visitor")
        repo.create_user(email="smtp-visitor@example.com",
                         password_hash=hash_password("Visitor#2026!"), role=visitor)
        db.commit()
        visitor_token = _login(client, "smtp-visitor@example.com", "Visitor#2026!")
        assert client.post(self.URL, headers=_auth(visitor_token)).status_code == 403

        sent = Mock()
        monkeypatch.setattr(EmailService, "send_smtp_test_email", sent)
        token = _login(client, seeded_admin[0].email, seeded_admin[1])
        response = client.post(self.URL, json={"recipient": "other@example.com", "SMTP_PASSWORD": "secret"},
                               headers=_auth(token))
        assert response.status_code == 200, response.text
        assert response.json() == {"status": "success", "failure_message": None}
        sent.assert_called_once_with(seeded_admin[0].email)
        rows = client.get(URL, headers=_auth(token)).json()["data"]
        assert rows[0]["purpose"] == "smtp_test"
        assert rows[0]["recipient_email"] == seeded_admin[0].email
        assert rows[0]["status"] == "success"
        assert rows[0]["created_at"]
        assert "other@example.com" not in str(rows)
        assert "secret" not in str(rows)
        _smtp_test_attempts.clear()

    def test_real_transport_settings_and_plain_message_with_mocked_smtp(self, monkeypatch):
        smtp = Mock()
        smtp.__enter__ = Mock(return_value=smtp)
        smtp.__exit__ = Mock(return_value=None)
        smtp.sendmail.return_value = {}
        factory = Mock(return_value=smtp)
        monkeypatch.setattr(smtplib, "SMTP", factory)
        monkeypatch.setattr("app.services.email_service.get_settings", lambda: SimpleNamespace(
            SMTP_HOST="mail.example.com", SMTP_PORT=587, EMAIL_TLS=True,
            SMTP_USER="mailer", SMTP_PASSWORD="private",
            resolved_email_from="sender@example.com",
        ))
        EmailService().send_smtp_test_email("admin@example.com")
        factory.assert_called_once_with("mail.example.com", 587, timeout=15)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("mailer", "private")
        sender, recipients, message = smtp.sendmail.call_args.args
        assert sender == "sender@example.com"
        assert recipients == ["admin@example.com"]
        assert "EquiConnected SMTP test" in message
        assert "private" not in message
        assert "http" not in message

    def test_failure_is_allow_listed_and_durable(self, client, db, seeded_admin, monkeypatch):
        token = _login(client, seeded_admin[0].email, seeded_admin[1])
        def fail(_self, _recipient):
            raise EmailDeliveryError("SMTP authentication failed.")
        monkeypatch.setattr(EmailService, "send_smtp_test_email", fail)
        response = client.post(self.URL, headers=_auth(token))
        assert response.json() == {"status": "failed", "failure_message": "SMTP authentication failed."}
        db.rollback()
        row = db.scalar(select(EmailDeliveryLog).where(EmailDeliveryLog.purpose == "smtp_test"))
        assert row.status == "failed"
        assert row.failure_message == "SMTP authentication failed."
        monkeypatch.setattr(EmailService, "send_smtp_test_email",
                            lambda *_: (_ for _ in ()).throw(EmailDeliveryError("password=private")))
        response = client.post(self.URL, headers=_auth(token))
        assert response.json() == {"status": "failed", "failure_message": "Unable to deliver email."}
        assert "private" not in str(client.get(URL, headers=_auth(token)).json())
        _smtp_test_attempts.clear()

    def test_rate_limit_and_pending_on_outcome_storage_failure(self, client, db, seeded_admin, monkeypatch):
        token = _login(client, seeded_admin[0].email, seeded_admin[1])
        monkeypatch.setattr(EmailService, "send_smtp_test_email", lambda *_: None)
        def cannot_complete(*_args, **_kwargs):
            raise RuntimeError("private server response")
        monkeypatch.setattr(EmailDeliveryRepository, "complete_durable_attempt", cannot_complete)
        try:
            for _ in range(3):
                response = client.post(self.URL, headers=_auth(token))
                assert response.json() == {"status": "pending", "failure_message": None}
            response = client.post(self.URL, headers=_auth(token))
            assert response.status_code == 429
            assert response.json()["detail"]["code"] == "rate_limited"
            db.rollback()
            rows = db.scalars(select(EmailDeliveryLog).where(EmailDeliveryLog.purpose == "smtp_test")).all()
            assert len(rows) == 3
            assert all(row.status == "pending" for row in rows)
        finally:
            _smtp_test_attempts.clear()

    def test_attempt_recorded_before_smtp_and_no_send_when_log_unavailable(
        self, client, db, seeded_admin, monkeypatch
    ):
        token = _login(client, seeded_admin[0].email, seeded_admin[1])
        def inspect_pending(_self, recipient):
            with db.get_bind().connect() as connection:
                assert connection.execute(
                    select(EmailDeliveryLog.status).where(
                        EmailDeliveryLog.recipient_email == recipient,
                        EmailDeliveryLog.purpose == "smtp_test",
                    )
                ).scalar_one() == "pending"
        monkeypatch.setattr(EmailService, "send_smtp_test_email", inspect_pending)
        assert client.post(self.URL, headers=_auth(token)).json()["status"] == "success"
        monkeypatch.setattr(EmailDeliveryRepository, "record_durable_attempt",
                            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("private")))
        sent = Mock()
        monkeypatch.setattr(EmailService, "send_smtp_test_email", sent)
        response = client.post(self.URL, headers=_auth(token))
        assert response.status_code == 503
        assert "private" not in response.text
        sent.assert_not_called()
        _smtp_test_attempts.clear()