"""Public signup and single-use email-verification flow tests."""
from datetime import datetime, timedelta, timezone
import threading
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.models.user import EmailVerificationToken, User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService
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
    def test_registers_inactive_account_with_relational_both_roles(
        self, client: TestClient, db, monkeypatch
    ):
        _seed_public_roles(db)
        sent_urls = _capture_verification_email(monkeypatch)

        response = client.post(f"{BASE}/register", json=_payload(email=" AMINA@EXAMPLE.COM "))

        assert response.status_code == 201
        assert "check your email" in response.json()["message"].lower()
        user = db.query(User).filter(User.email == "amina@example.com").one()
        assert user.is_active is False
        assert user.email_verified_at is None
        assert user.country == "United Arab Emirates"
        assert user.state_province == "Dubai"
        assert user.city == "Dubai"
        assert user.terms_accepted_at is not None
        assert user.privacy_accepted_at is not None
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

    def test_inactive_account_cannot_log_in_before_verification(
        self, client: TestClient, db, monkeypatch
    ):
        _seed_public_roles(db)
        _capture_verification_email(monkeypatch)
        client.post(f"{BASE}/register", json=_payload())

        response = client.post(
            f"{BASE}/login",
            json={"email": "amina@example.com", "password": "HorseCare2026"},
        )

        assert response.status_code == 401


class TestEmailVerification:
    def test_token_activates_account_once_and_allows_login(
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
        assert repeated.status_code == 409
        assert repeated.json()["detail"]["code"] == "verification_link_used"
        assert login.status_code == 200
        user = db.query(User).filter(User.email == "amina@example.com").one()
        assert user.is_active is True
        assert user.email_verified_at is not None
        token = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id
        ).one()
        assert token.used_at is not None

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