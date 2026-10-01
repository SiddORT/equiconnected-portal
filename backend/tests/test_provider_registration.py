"""Provider account registration, verification, review, and staged-listing tests."""
import threading
from uuid import UUID
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from pydantic import ValidationError

from app.models.enums import (
    ProviderApplicationStatus,
    ProviderStatus,
    PublicationStatus,
)
from app.models.provider import Provider, ProviderLocation, ProviderSpecialization
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.specialization import Specialization
from app.models.language import Language, ProviderLanguage, ProviderRegistrationLanguage
from app.schemas.auth import ProviderRegistrationRequest
from app.models.user import User
from app.models.user import EmailVerificationToken
from app.models.email_delivery_log import EmailDeliveryLog
from app.repositories.user_repository import UserRepository
from app.repositories.provider_registration_repository import ProviderRegistrationRepository
from app.services.email_service import EmailService
from app.services.email_service import EmailDeliveryError
from app.services.provider_registration_service import (
    ProviderApplicationDecisionError,
    ProviderRegistrationService,
)


AUTH = "/api/v1/auth"
APPLICATIONS = "/api/v1/admin/provider-applications"


def _payload(**overrides) -> dict:
    data = {
        "first_name": "Amina",
        "last_name": "Veterinarian",
        "email": "amina.provider@example.com",
        "mobile_number": "+971 50 123 4567",
        "country": "United Arab Emirates",
        "state_province": "Dubai",
        "city": "Dubai",
        "postal_code": "00000",
        "password": "HorseCare2026",
        "password_confirmation": "HorseCare2026",
        "role": "PROVIDER",
        "provider_type": "CLINIC",
        "provider_name": "Amina Equine Clinic",
        "visit_stability": "STABLE_VISIT",
        "professional_title": "Equine veterinarian",
        "specialization_ids": ["dc06ab91-4687-44cf-acef-47fa29ef80ad"],
        "years_experience": 8,
        "working_address": "12 Stable Lane",
        "stable_visit": True,
        "maximum_working_radius_km": 40,
        "emergency_services_available": True,
        "emergency_contact_number": "+971 50 555 1212",
        "accept_terms": True,
        "accept_privacy": True,
    }
    data.update(overrides)
    return data


def _seed_provider_role(db) -> None:
    repo = UserRepository(db)
    if repo.get_role_by_name("provider") is None:
        repo.create_role("provider", "Provider account application")
    db.commit()


def _capture_verification_email(monkeypatch) -> list[str]:
    sent_urls: list[str] = []

    def send(_self, _recipient: str, verification_url: str, _expires_at) -> None:
        sent_urls.append(verification_url)

    monkeypatch.setattr(EmailService, "send_verification_email", send)
    return sent_urls


def _admin_headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _verified_application(client: TestClient, db, monkeypatch) -> ProviderRegistrationApplication:
    _seed_provider_role(db)
    db.add(Specialization(id=_payload()["specialization_ids"][0], name="Equine medicine", is_active=True))
    db.commit()
    sent_urls = _capture_verification_email(monkeypatch)
    response = client.post(f"{AUTH}/provider-register", json=_payload())
    assert response.status_code == 201
    assert db.query(Provider).count() == 0
    token = parse_qs(urlparse(sent_urls[0]).query)["token"][0]
    verified = client.post(f"{AUTH}/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert verified.json()["redirect_to"] == "/provider/login"
    return db.query(ProviderRegistrationApplication).one()


class TestProviderRegistration:
    def test_failed_verification_handoff_keeps_application_pending_until_resend(self, client, db, monkeypatch):
        _seed_provider_role(db)
        db.add(Specialization(id=_payload()["specialization_ids"][0], name="Equine medicine", is_active=True))
        db.commit()
        def fail(*_args):
            raise EmailDeliveryError("SMTP TLS negotiation failed.")
        monkeypatch.setattr(EmailService, "send_verification_email", fail)
        created = client.post(f"{AUTH}/provider-register", json=_payload())
        assert created.status_code == 201
        assert created.json()["email_sent"] is False
        application = db.query(ProviderRegistrationApplication).one()
        assert application.review_status == ProviderApplicationStatus.AWAITING_EMAIL_VERIFICATION
        assert db.query(User).filter_by(email="amina.provider@example.com").one().is_active is False
        assert db.query(EmailDeliveryLog).one().failure_message == "SMTP TLS negotiation failed."
        assert client.post(f"{AUTH}/provider-register", json=_payload()).status_code == 409
        assert client.post(f"{AUTH}/login", json={
            "email": "amina.provider@example.com", "password": "HorseCare2026",
        }).json()["detail"]["code"] == "email_not_verified"
        sent = _capture_verification_email(monkeypatch)
        assert client.post(f"{AUTH}/resend-verification", json={"email": "amina.provider@example.com"}).status_code == 200
        assert len(sent) == 1
        token = parse_qs(urlparse(sent[0]).query)["token"][0]
        assert client.post(f"{AUTH}/verify-email", json={"token": token}).status_code == 200
        db.expire_all()
        assert db.query(ProviderRegistrationApplication).one().review_status == ProviderApplicationStatus.PENDING_REVIEW
        assert db.query(EmailVerificationToken).count() == 1
        assert db.query(User).count() == 1

    def test_expired_provider_link_can_request_replacement_without_exposing_account(self, client, db, monkeypatch):
        from datetime import datetime, timedelta, timezone
        _seed_provider_role(db)
        db.add(Specialization(id=_payload()["specialization_ids"][0], name="Equine medicine", is_active=True))
        db.commit()
        sent = _capture_verification_email(monkeypatch)
        assert client.post(f"{AUTH}/provider-register", json=_payload()).status_code == 201
        original = parse_qs(urlparse(sent[0]).query)["token"][0]
        db.query(EmailVerificationToken).one().expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.query(EmailDeliveryLog).one().created_at = datetime.now(timezone.utc) - timedelta(minutes=6)
        db.commit()
        route = f"{AUTH}/resend-verification-token"
        recovered = client.post(route, json={"token": original})
        assert recovered.status_code == 200
        assert recovered.json() == client.post(route, json={"token": "unknown" * 5}).json()
        assert len(sent) == 2
        replacement = parse_qs(urlparse(sent[-1]).query)["token"][0]
        assert client.post(f"{AUTH}/verify-email", json={"token": replacement}).status_code == 200
        assert client.post(route, json={"token": original}).json() == recovered.json()
        assert len(sent) == 2

    def test_language_master_admin_and_public_selection(
        self, client: TestClient, db, seeded_admin, monkeypatch
    ):
        admin, _password = seeded_admin
        headers = _admin_headers(admin)
        created = client.post(
            "/api/v1/admin/languages",
            headers=headers,
            json={"name": "Hindi", "code": "HI"},
        )
        assert created.status_code == 201
        language_id = created.json()["id"]
        assert created.json()["code"] == "hi"
        assert {"id": language_id, "name": "Hindi", "code": "hi"} in client.get(
            f"{AUTH}/provider-languages"
        ).json()
        duplicate = client.post(
            "/api/v1/admin/languages", headers=headers, json={"name": "Another", "code": "hi"}
        )
        assert duplicate.status_code == 409
        edited = client.patch(
            f"/api/v1/admin/languages/{language_id}", headers=headers,
            json={"name": "Hindi language"},
        )
        assert edited.status_code == 200
        assert edited.json()["name"] == "Hindi language"

        _seed_provider_role(db)
        db.add(Specialization(id=_payload()["specialization_ids"][0], name="Equine medicine", is_active=True))
        db.commit()
        sent_urls = _capture_verification_email(monkeypatch)
        response = client.post(
            f"{AUTH}/provider-register", json=_payload(language_ids=[language_id])
        )
        assert response.status_code == 201
        application = db.query(ProviderRegistrationApplication).one()
        assert db.query(ProviderRegistrationLanguage).filter_by(application_id=application.id).one().language_id == UUID(language_id)

        deleted = client.delete(f"/api/v1/admin/languages/{language_id}", headers=headers)
        assert deleted.status_code == 200
        assert all(
            item["id"] != language_id
            for item in client.get(f"{AUTH}/provider-languages").json()
        )
        token = parse_qs(urlparse(sent_urls[0]).query)["token"][0]
        assert client.post(f"{AUTH}/verify-email", json={"token": token}).status_code == 200
        approval_emails = []
        monkeypatch.setattr(
            EmailService,
            "send_provider_approval_email",
            lambda _self, recipient, login_url: approval_emails.append(
                (recipient, login_url)
            ),
        )
        approved = client.post(
            f"{APPLICATIONS}/{application.id}/approve", headers=headers
        )
        assert approved.status_code == 200
        assert approved.json()["email_sent"] is True
        assert approval_emails[0][0] == application.user.email
        assert approved.json()["languages"] == [{"id": language_id, "name": "Hindi language"}]
        provider_id = db.query(ProviderRegistrationApplication).one().provider_id
        assert db.query(ProviderLanguage).filter_by(provider_id=provider_id).count() == 1
        assert db.query(Language).filter_by(id=language_id).one().is_active is False

    def test_provider_registration_verification_and_atomic_approval(
        self, client: TestClient, db, seeded_admin, monkeypatch
    ):
        application = _verified_application(client, db, monkeypatch)
        provider_user = db.query(User).filter(User.id == application.user_id).one()
        assert application.review_status == ProviderApplicationStatus.PENDING_REVIEW
        assert provider_user.is_active is False

        pending_login = client.post(
            f"{AUTH}/login",
            json={"email": provider_user.email, "password": "HorseCare2026"},
        )
        assert pending_login.status_code == 403
        assert pending_login.json()["detail"]["code"] == "provider_application_pending_review"

        admin, _password = seeded_admin
        listed = client.get(
            APPLICATIONS,
            params={"review_status": "PENDING_REVIEW", "provider_type": "CLINIC"},
            headers=_admin_headers(admin),
        )
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()["data"]] == [str(application.id)]

        approval_emails = []
        monkeypatch.setattr(
            EmailService,
            "send_provider_approval_email",
            lambda _self, recipient, login_url: approval_emails.append(
                (recipient, login_url)
            ),
        )
        approved = client.post(
            f"{APPLICATIONS}/{application.id}/approve",
            headers=_admin_headers(admin),
        )
        assert approved.status_code == 200
        body = approved.json()
        assert body["email_sent"] is True
        assert approval_emails[0][0] == provider_user.email
        assert approval_emails[0][1].endswith("/provider/login")
        assert body["review_status"] == "APPROVED"
        assert body["provider_id"]
        assert body["professional_title"] == "Equine veterinarian"
        assert body["specialization_ids"] == [_payload()["specialization_ids"][0]]
        assert body["specializations"] == [{
            "id": _payload()["specialization_ids"][0],
            "name": "Equine medicine",
        }]
        assert body["years_experience"] == 8
        assert body["postal_code"] == "00000"
        assert body["working_address"] == "12 Stable Lane"
        assert body["stable_visit"] is True
        assert body["maximum_working_radius_km"] == 40
        assert body["emergency_services_available"] is True
        assert body["emergency_contact_number"] == "+971 50 555 1212"
        assert body["terms_accepted_at"] is not None
        assert body["privacy_accepted_at"] is not None
        assert "password_hash" not in body
        assert "password" not in body

        db.expire_all()
        application = db.query(ProviderRegistrationApplication).one()
        provider = db.query(Provider).filter(Provider.id == application.provider_id).one()
        provider_user = db.query(User).filter(User.id == application.user_id).one()
        assert provider.status == ProviderStatus.DRAFT
        assert provider.publication_status == PublicationStatus.UNPUBLISHED
        assert provider.name == "Amina Equine Clinic"
        assert provider.email == provider_user.email
        assert provider.phone == provider_user.mobile_number
        assert provider.professional_title == "Equine veterinarian"
        assert provider.years_experience == 8
        assert provider.clinic_hospital_visit is None
        assert provider.maximum_working_radius_km == 40
        assert provider.emergency_services_available is True
        assert provider.emergency_contact_number == "+971 50 555 1212"
        assert db.query(ProviderLocation).filter_by(provider_id=provider.id).one().address_line_1 == "12 Stable Lane"
        assert db.query(ProviderLocation).filter_by(provider_id=provider.id).one().postal_code == "00000"
        assert db.query(ProviderSpecialization).filter_by(provider_id=provider.id).count() == 1
        assert provider_user.is_active is True

        repeated = client.post(
            f"{APPLICATIONS}/{application.id}/approve",
            headers=_admin_headers(admin),
        )
        assert repeated.status_code == 409
        assert db.query(Provider).count() == 1

        approved_login = client.post(
            f"{AUTH}/login",
            json={"email": provider_user.email, "password": "HorseCare2026"},
        )
        assert approved_login.status_code == 200
        assert approved_login.json()["user"]["roles"] == ["provider"]
        forbidden = client.get(
            APPLICATIONS, headers=_admin_headers(provider_user)
        )
        assert forbidden.status_code == 403

    def test_admin_application_details_include_saved_fields_and_inactive_selections(
        self, client: TestClient, db, seeded_admin, monkeypatch
    ):
        _seed_provider_role(db)
        specialization_ids = [
            "dc06ab91-4687-44cf-acef-47fa29ef80ad",
            "c2032431-395a-4711-9c82-83be849718fd",
        ]
        language_ids = [
            "b6052449-3086-40b9-9268-180093a38f39",
            "287b9ed0-7822-4b8e-b290-fab74d5cfd2c",
        ]
        db.add_all([
            Specialization(
                id=UUID(specialization_ids[0]), name="Equine medicine", is_active=True
            ),
            Specialization(
                id=UUID(specialization_ids[1]), name="Dentistry", is_active=True
            ),
            Language(id=UUID(language_ids[0]), name="Arabic", code="ar", is_active=True),
            Language(id=UUID(language_ids[1]), name="Hindi", code="hi", is_active=True),
        ])
        db.commit()
        sent_urls = _capture_verification_email(monkeypatch)
        created = client.post(
            f"{AUTH}/provider-register",
            json=_payload(
                specialization_ids=specialization_ids,
                language_ids=language_ids,
                years_experience=0,
                visit_stability="NOT_STABLE_VISIT",
                stable_visit=False,
                maximum_working_radius_km=None,
                emergency_services_available=False,
                emergency_contact_number=None,
            ),
        )
        assert created.status_code == 201
        application = db.query(ProviderRegistrationApplication).one()
        token = parse_qs(urlparse(sent_urls[0]).query)["token"][0]
        assert client.post(f"{AUTH}/verify-email", json={"token": token}).status_code == 200

        db.query(Specialization).filter(
            Specialization.id == specialization_ids[1]
        ).update({"is_active": False})
        db.query(Language).filter(Language.id == language_ids[1]).update(
            {"is_active": False}
        )
        db.commit()
        admin, _password = seeded_admin
        headers = _admin_headers(admin)

        listed = client.get(APPLICATIONS, headers=headers)
        assert listed.status_code == 200
        detail = client.get(f"{APPLICATIONS}/{application.id}", headers=headers)
        assert detail.status_code == 200
        for body in (listed.json()["data"][0], detail.json()):
            assert body["id"] == str(application.id)
            assert body["professional_title"] == "Equine veterinarian"
            assert body["specialization_ids"] == specialization_ids
            assert body["specializations"] == [
                {"id": specialization_ids[0], "name": "Equine medicine"},
                {"id": specialization_ids[1], "name": "Dentistry"},
            ]
            assert body["languages"] == [
                {"id": language_ids[0], "name": "Arabic"},
                {"id": language_ids[1], "name": "Hindi"},
            ]
            assert body["years_experience"] == 0
            assert body["postal_code"] == "00000"
            assert body["working_address"] == "12 Stable Lane"
            assert body["stable_visit"] is False
            assert body["maximum_working_radius_km"] is None
            assert body["emergency_services_available"] is False
            assert body["emergency_contact_number"] is None
            assert body["terms_accepted_at"] is not None
            assert body["privacy_accepted_at"] is not None
            assert "password_hash" not in body
            assert "password" not in body
        assert "HorseCare2026" not in detail.text

    def test_legacy_application_details_keep_missing_values_nullable(
        self, client: TestClient, db, seeded_admin, monkeypatch
    ):
        application = _verified_application(client, db, monkeypatch)
        application.professional_title = None
        application.specialization_ids = None
        application.years_experience = None
        application.working_address = None
        application.stable_visit = None
        application.maximum_working_radius_km = None
        application.emergency_services_available = None
        application.emergency_contact_number = None
        application.user.terms_accepted_at = None
        application.user.privacy_accepted_at = None
        db.commit()

        admin, _password = seeded_admin
        response = client.get(
            f"{APPLICATIONS}/{application.id}", headers=_admin_headers(admin)
        )
        assert response.status_code == 200
        body = response.json()
        for field in (
            "professional_title",
            "specialization_ids",
            "specializations",
            "years_experience",
            "working_address",
            "stable_visit",
            "maximum_working_radius_km",
            "emergency_services_available",
            "emergency_contact_number",
            "terms_accepted_at",
            "privacy_accepted_at",
        ):
            assert body[field] is None
        assert body["languages"] == []
        assert body["postal_code"] == "00000"
        assert client.get(f"{APPLICATIONS}/{application.id}").status_code == 401

    def test_signup_conditional_validation(self):
        for provider_type in ("DOCTOR", "CLINIC", "HOSPITAL"):
            base = _payload(provider_type=provider_type)
            no_stable = ProviderRegistrationRequest.model_validate({
                **base, "stable_visit": False, "visit_stability": "NOT_STABLE_VISIT",
                "maximum_working_radius_km": 50, "emergency_services_available": False,
                "emergency_contact_number": "+971 50 555 1212",
            })
            assert no_stable.maximum_working_radius_km is None
            assert no_stable.emergency_contact_number is None
            for updates in (
                {"maximum_working_radius_km": None},
                {"maximum_working_radius_km": 0},
                {"emergency_services_available": True, "emergency_contact_number": None},
                {"emergency_services_available": True, "emergency_contact_number": "   "},
                {"specialization_ids": []},
                {"professional_title": "  "},
            ):
                try:
                    ProviderRegistrationRequest.model_validate({**base, **updates})
                except ValidationError:
                    pass
                else:
                    raise AssertionError(f"Expected validation error for {updates}")

    def test_signup_specializations_are_public_active_only_and_validated(
        self, client: TestClient, db, monkeypatch
    ):
        _seed_provider_role(db)
        active_id = _payload()["specialization_ids"][0]
        db.add(Specialization(id=active_id, name="Equine medicine", is_active=True))
        db.add(Specialization(name="Inactive field", is_active=False))
        db.commit()
        result = client.get(f"{AUTH}/provider-specializations")
        assert result.status_code == 200
        assert result.json() == [{"id": active_id, "name": "Equine medicine"}]
        sent = _capture_verification_email(monkeypatch)
        rejected = client.post(
            f"{AUTH}/provider-register",
            json=_payload(specialization_ids=["c2032431-395a-4711-9c82-83be849718fd"]),
        )
        assert rejected.status_code == 422
        assert db.query(ProviderRegistrationApplication).count() == 0
        assert db.query(User).filter_by(email="amina.provider@example.com").count() == 0
        assert not sent

    def test_rejection_preserves_application_without_listing(
        self, client: TestClient, db, seeded_admin, monkeypatch
    ):
        application = _verified_application(client, db, monkeypatch)
        admin, _password = seeded_admin
        rejected = client.post(
            f"{APPLICATIONS}/{application.id}/reject",
            json={"rejection_reason": "This account cannot be verified at this time."},
            headers=_admin_headers(admin),
        )
        assert rejected.status_code == 200
        assert rejected.json()["review_status"] == "REJECTED"
        assert rejected.json()["rejection_reason"] == "This account cannot be verified at this time."
        assert rejected.json()["professional_title"] == "Equine veterinarian"
        assert rejected.json()["specialization_ids"] == [_payload()["specialization_ids"][0]]
        assert rejected.json()["specializations"] == [{
            "id": _payload()["specialization_ids"][0],
            "name": "Equine medicine",
        }]
        assert rejected.json()["terms_accepted_at"] is not None
        assert rejected.json()["privacy_accepted_at"] is not None
        assert db.query(Provider).count() == 0

        denied = client.post(
            f"{AUTH}/login",
            json={"email": "amina.provider@example.com", "password": "HorseCare2026"},
        )
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "provider_application_rejected"

    def test_concurrent_approvals_create_exactly_one_staged_listing(
        self, client: TestClient, db, seeded_admin, monkeypatch
    ):
        """The application-row lock serializes competing administrator decisions."""
        from tests.conftest import TestingSessionLocal

        application = _verified_application(client, db, monkeypatch)
        admin, _password = seeded_admin
        monkeypatch.setattr(
            EmailService,
            "send_provider_approval_email",
            lambda *_args: None,
        )
        application_id = application.id
        admin_id = admin.id
        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def approve() -> None:
            session = TestingSessionLocal()
            try:
                barrier.wait(timeout=5)
                ProviderRegistrationService(
                    ProviderRegistrationRepository(session)
                ).approve(application_id, admin_id)
                outcomes.append("approved")
            except ProviderApplicationDecisionError:
                outcomes.append("conflict")
            finally:
                session.close()

        first = threading.Thread(target=approve)
        second = threading.Thread(target=approve)
        first.start()
        second.start()
        first.join(timeout=10)
        second.join(timeout=10)

        assert not first.is_alive()
        assert not second.is_alive()
        assert sorted(outcomes) == ["approved", "conflict"]
        db.expire_all()
        assert db.query(Provider).count() == 1
        assert db.query(ProviderRegistrationApplication).one().review_status == (
            ProviderApplicationStatus.APPROVED
        )