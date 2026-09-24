"""Public signup and single-use email-verification flow tests."""
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from fastapi import HTTPException
from types import SimpleNamespace
import pytest

from app.models.user import EmailVerificationToken, User, UserRole
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailPurpose
from app.models.role import Role
from app.core.security import create_access_token
from app.core.config import get_settings
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService
from app.services.email_service import EmailDeliveryError
from app.services.auth_service import AuthService, VerificationTokenUsedError


BASE = "/api/v1/auth"


def _payload(**overrides) -> dict:
    data = {
        "first_name": "Amina",
        "last_name": "Rider",
        "email": "amina@example.com",
        "mobile_number": "+971 50 123 4567",
        "country": "United Arab Emirates",
        "state_province": "Dubai",
        "city": "Dubai",
        "password": "HorseCare2026",
        "password_confirmation": "HorseCare2026",
        "role": "BOTH",
        "accept_terms": True,
        "accept_privacy": True,
    }
    data.update(overrides)
    return data


def _seed_public_roles(db) -> None:
    repo = UserRepository(db)
    for name, description in (
        ("horse_owner", "Public horse owner account"),
        ("stable_manager", "Public stable manager account"),
    ):
        if repo.get_role_by_name(name) is None:
            repo.create_role(name, description)
    db.commit()


def _capture_verification_email(monkeypatch) -> list[str]:
    sent_urls: list[str] = []

    def _send(_self, _recipient: str, verification_url: str, _expires_at) -> None:
        sent_urls.append(verification_url)

    monkeypatch.setattr(EmailService, "send_verification_email", _send)
    return sent_urls


class TestPublicRegistration:
    def test_resend_is_rate_limited_per_ip(self):
        from app.core.rate_limit import (
            _verification_resend_attempts, check_verification_resend_rate_limit,
        )
        request = SimpleNamespace(client=SimpleNamespace(host="rate-limit-test"))
        try:
            for _ in range(5):
                check_verification_resend_rate_limit(request)
            with pytest.raises(HTTPException) as exc:
                check_verification_resend_rate_limit(request)
            assert exc.value.status_code == 429
        finally:
            _verification_resend_attempts.pop("rate-limit-test", None)

    def test_failed_handoff_persists_and_resend_recovers_without_duplicate(self, client, db, monkeypatch):
        _seed_public_roles(db)
        def fail(*_args):
            raise EmailDeliveryError("SMTP authentication failed.")
        monkeypatch.setattr(EmailService, "send_verification_email", fail)
        created = client.post(f"{BASE}/register", json=_payload())
        assert created.status_code == 201
        assert created.json()["email_sent"] is False
        assert "could not be sent" in created.json()["message"]
        assert db.query(User).count() == 1
        assert db.query(EmailVerificationToken).count() == 0
        assert db.query(EmailDeliveryLog).one().failure_message == "SMTP authentication failed."
        assert client.post(f"{BASE}/login", json={
            "email": "amina@example.com", "password": "HorseCare2026",
        }).json()["detail"]["code"] == "email_not_verified"
        assert client.post(f"{BASE}/register", json=_payload()).status_code == 409
        sent = _capture_verification_email(monkeypatch)
        generic = client.post(f"{BASE}/resend-verification", json={"email": "AMINA@example.com"})
        unknown = client.post(f"{BASE}/resend-verification", json={"email": "unknown@example.com"})
        assert generic.status_code == unknown.status_code == 200
        assert generic.json() == unknown.json()
        assert len(sent) == 1
        assert f"{urlparse(sent[0]).scheme}://{urlparse(sent[0]).netloc}" == (
            get_settings().PUBLIC_APP_URL.rstrip("/")
        )
        assert client.post(f"{BASE}/resend-verification", json={"email": "amina@example.com"}).status_code == 200
        assert len(sent) == 1
        raw = parse_qs(urlparse(sent[0]).query)["token"][0]
        assert client.post(f"{BASE}/verify-email", json={"token": raw}).status_code == 200
        assert client.post(f"{BASE}/resend-verification", json={"email": "amina@example.com"}).json() == generic.json()
        assert len(sent) == 1
        assert db.query(User).count() == 1
        assert [row.status for row in db.query(EmailDeliveryLog).order_by(EmailDeliveryLog.created_at)] == ["failed", "success"]

    def test_concurrent_resends_only_send_once(self, client, db, monkeypatch):
        from tests.conftest import TestingSessionLocal
        _seed_public_roles(db)
        monkeypatch.setattr(EmailService, "send_verification_email", lambda *_: (_ for _ in ()).throw(EmailDeliveryError("SMTP connection failed.")))
        assert client.post(f"{BASE}/register", json=_payload()).json()["email_sent"] is False
        sent = _capture_verification_email(monkeypatch)
        barrier = threading.Barrier(2)
        results = []
        def resend():
            session = TestingSessionLocal()
            try:
                barrier.wait(timeout=5)
                results.append(AuthService(session).send_verification("amina@example.com"))
            finally:
                session.close()
        threads = [threading.Thread(target=resend) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        assert all(not thread.is_alive() for thread in threads)
        assert sorted(results) == [False, True]
        assert len(sent) == 1
        assert db.query(EmailVerificationToken).count() == 1

    def test_public_role_repair_migration_is_idempotent_and_preserves_existing_data(
        self, db, monkeypatch
    ):
        repo = UserRepository(db)
        horse_owner = repo.create_role("horse_owner", "Existing horse owner description")
        existing_user = repo.create_user(
            email="existing-owner@example.com",
            password_hash="not-a-real-password-hash",
            role=horse_owner,
        )
        db.commit()

        migration_path = (
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "d4b7e9a1c203_restore_public_registration_roles.py"
        )
        spec = spec_from_file_location("restore_public_registration_roles", migration_path)
        assert spec is not None and spec.loader is not None
        migration = module_from_spec(spec)
        spec.loader.exec_module(migration)
        operations = Operations(MigrationContext.configure(db.connection()))
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()
        migration.upgrade()
        db.expire_all()

        roles = {role.name: role for role in db.query(Role).all()}
        restored_user = db.query(User).filter(User.id == existing_user.id).one()
        assert {"horse_owner", "stable_manager"} <= set(roles)
        assert roles["horse_owner"].description == "Existing horse owner description"
        assert restored_user.role_id == horse_owner.id
        assert (
            db.query(UserRole)
            .filter(
                UserRole.user_id == existing_user.id,
                UserRole.role_id == horse_owner.id,
            )
            .count()
            == 1
        )

    def test_all_public_role_selections_reach_verification_flow(
        self, client: TestClient, db, monkeypatch
    ):
        _seed_public_roles(db)
        sent_urls = _capture_verification_email(monkeypatch)

        for index, role in enumerate(("HORSE_OWNER", "STABLE_MANAGER", "BOTH")):
            response = client.post(
                f"{BASE}/register",
                json=_payload(
                    email=f"role-{index}@example.com",
                    role=role,
                ),
            )
            assert response.status_code == 201

        assert len(sent_urls) == 3
        users = db.query(User).order_by(User.email).all()
        assert len(users) == 3
        assigned_roles = {
            user.email: {
                assignment.role.name
                for assignment in db.query(UserRole)
                .filter(UserRole.user_id == user.id)
                .all()
            }
            for user in users
        }
        assert assigned_roles["role-0@example.com"] == {"horse_owner"}
        assert assigned_roles["role-1@example.com"] == {"stable_manager"}
        assert assigned_roles["role-2@example.com"] == {"horse_owner", "stable_manager"}

    def test_missing_public_role_returns_temporary_unavailability_without_user(
        self, client: TestClient, db, monkeypatch
    ):
        _seed_public_roles(db)
        missing_role = db.query(Role).filter(Role.name == "stable_manager").one()
        db.delete(missing_role)
        db.commit()
        _capture_verification_email(monkeypatch)

        response = client.post(f"{BASE}/register", json=_payload())

        assert response.status_code == 503
        assert response.json()["detail"] == {
            "code": "registration_unavailable",
            "message": "Registration is temporarily unavailable. Please try again later.",
        }
        assert db.query(User).count() == 0
        assert "stable_manager" not in response.text

    def test_registers_inactive_account_with_relational_both_roles(
        self, client: TestClient, db, monkeypatch
    ):
        _seed_public_roles(db)
        sent_urls = _capture_verification_email(monkeypatch)

        response = client.post(f"{BASE}/register", json=_payload(email=" AMINA@EXAMPLE.COM "))
        assert response.status_code == 201

        assert "check your email" in response.json()["message"].lower()

        user = db.query(User).filter(User.email == "amina@example.com").one()

        assert user.password_hash != "HorseCare2026"
        assert user.password_hash.startswith("$argon2id$")

        assigned_roles = {
            assignment.role.name
            for assignment in db.query(UserRole).filter(UserRole.user_id == user.id).all()
        }
        assert assigned_roles == {"horse_owner", "stable_manager"}
        token = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id
        ).one()
        assert len(sent_urls) == 1
        raw_token = parse_qs(urlparse(sent_urls[0]).query)["token"][0]
        assert raw_token not in token.token_hash
        assert len(token.token_hash) == 64

    def test_duplicate_email_is_rejected(self, client: TestClient, db, monkeypatch):
        _seed_public_roles(db)
        _capture_verification_email(monkeypatch)
        assert client.post(f"{BASE}/register", json=_payload()).status_code == 201

        response = client.post(f"{BASE}/register", json=_payload(email="AMINA@example.com"))

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "email_already_registered"

    def test_rejects_missing_required_consent(self, client: TestClient, db, monkeypatch):
        _seed_public_roles(db)
        _capture_verification_email(monkeypatch)

        response = client.post(f"{BASE}/register", json=_payload(accept_privacy=False))

        assert response.status_code == 422
        assert db.query(User).count() == 0

    def test_unverified_account_cannot_log_in_or_access_member_profile(
        self, client: TestClient, db, monkeypatch
    ):
        _seed_public_roles(db)
        _capture_verification_email(monkeypatch)
        client.post(f"{BASE}/register", json=_payload())

        response = client.post(
            f"{BASE}/login",
            json={"email": "amina@example.com", "password": "HorseCare2026"},
        )

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "email_not_verified"
        user = db.query(User).filter(User.email == "amina@example.com").one()
        profile = client.get(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {create_access_token(subject=user.id)}"},
        )
        assert profile.status_code == 403
        assert profile.json()["detail"]["code"] == "email_not_verified"


class TestEmailVerification:
    def test_resend_replaces_expired_link_only_after_successful_handoff(self, client, db, monkeypatch):
        _seed_public_roles(db)
        sent = _capture_verification_email(monkeypatch)
        assert client.post(f"{BASE}/register", json=_payload()).status_code == 201
        original = parse_qs(urlparse(sent[0]).query)["token"][0]
        old = db.query(EmailVerificationToken).one()
        old.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        # A failed resend must not remove the existing token.
        def fail(*_args):
            raise EmailDeliveryError("SMTP connection failed.")
        monkeypatch.setattr(EmailService, "send_verification_email", fail)
        # Remove the successful-send cooldown by aging the attempt.
        from app.models.email_delivery_log import EmailDeliveryLog
        first_log = db.query(EmailDeliveryLog).one()
        first_log.created_at = datetime.now(timezone.utc) - timedelta(minutes=6)
        db.commit()
        assert client.post(f"{BASE}/resend-verification", json={"email": "amina@example.com"}).status_code == 200
        db.expire_all()
        assert db.query(EmailVerificationToken).count() == 1
        assert db.query(EmailVerificationToken).one().used_at is None
        sent = _capture_verification_email(monkeypatch)
        client.post(f"{BASE}/resend-verification", json={"email": "amina@example.com"})
        assert len(sent) == 1
        replacement = parse_qs(urlparse(sent[0]).query)["token"][0]
        assert replacement != original
        db.expire_all()
        assert client.post(f"{BASE}/verify-email", json={"token": original}).status_code == 409
        assert client.post(f"{BASE}/verify-email", json={"token": replacement}).status_code == 200

    def test_verification_allows_immediate_member_login_and_returns_verified_email(
        self, client: TestClient, db, monkeypatch
    ):
        _seed_public_roles(db)
        sent_urls = _capture_verification_email(monkeypatch)
        client.post(f"{BASE}/register", json=_payload(role="HORSE_OWNER"))
        raw_token = parse_qs(urlparse(sent_urls[0]).query)["token"][0]

        verified = client.post(f"{BASE}/verify-email", json={"token": raw_token})
        repeated = client.post(f"{BASE}/verify-email", json={"token": raw_token})
        login = client.post(
            f"{BASE}/login",
            json={"email": "amina@example.com", "password": "HorseCare2026"},
        )

        assert verified.status_code == 200
        assert verified.json() == {
            "message": "Your email has been verified. You can now sign in.",
            "email": "amina@example.com",
        }
        assert repeated.status_code == 409
        assert repeated.json()["detail"]["code"] == "verification_link_used"
        assert login.status_code == 200
        assert login.json()["user"]["email"] == "amina@example.com"
        assert "approval_status" not in login.json()["user"]
        last_sign_in = login.json()["user"]["last_successful_login_at"]
        assert last_sign_in is not None
        assert datetime.fromisoformat(last_sign_in.replace("Z", "+00:00")).tzinfo is not None
        user = db.query(User).filter(User.email == "amina@example.com").one()
        assert user.is_active is True
        assert user.email_verified_at is not None
        assert user.last_successful_login_at is not None
        token = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id
        ).one()
        assert token.used_at is not None

        # Session restoration returns the persisted sign-in event without
        # recording a new credential authentication.
        refresh_token = login.cookies.get("refresh_token")
        assert refresh_token
        client.cookies.set("refresh_token", refresh_token)
        refresh = client.post(f"{BASE}/refresh")
        assert refresh.status_code == 200
        assert refresh.json()["user"]["last_successful_login_at"] == last_sign_in

        me = client.get(
            f"{BASE}/me",
            headers={"Authorization": f"Bearer {refresh.json()['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["last_successful_login_at"] == last_sign_in

    def test_expired_token_is_not_accepted(self, client: TestClient, db, monkeypatch):
        _seed_public_roles(db)
        sent_urls = _capture_verification_email(monkeypatch)
        client.post(f"{BASE}/register", json=_payload())
        raw_token = parse_qs(urlparse(sent_urls[0]).query)["token"][0]
        token = db.query(EmailVerificationToken).one()
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        response = client.post(f"{BASE}/verify-email", json={"token": raw_token})

        assert response.status_code == 410
        assert response.json()["detail"]["code"] == "verification_link_expired"

    def test_concurrent_redemption_only_allows_one_success(
        self, client: TestClient, db, monkeypatch
    ):
        """A row lock prevents parallel requests from redeeming a token twice."""
        from tests.conftest import TestingSessionLocal

        _seed_public_roles(db)
        sent_urls = _capture_verification_email(monkeypatch)
        assert client.post(f"{BASE}/register", json=_payload()).status_code == 201
        raw_token = parse_qs(urlparse(sent_urls[0]).query)["token"][0]
        barrier = threading.Barrier(2)
        results: list[str] = []

        def _redeem() -> None:
            session = TestingSessionLocal()
            try:
                barrier.wait(timeout=5)
                AuthService(session).verify_email(raw_token)
                results.append("verified")
            except VerificationTokenUsedError:
                results.append("used")
            finally:
                session.close()

        first = threading.Thread(target=_redeem)
        second = threading.Thread(target=_redeem)
        first.start()
        second.start()
        first.join(timeout=10)
        second.join(timeout=10)

        assert not first.is_alive()
        assert not second.is_alive()
        assert sorted(results) == ["used", "verified"]
