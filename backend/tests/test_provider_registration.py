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
from app.repositories.user_repository import UserRepository
from app.repositories.provider_registration_repository import ProviderRegistrationRepository
from app.services.email_service import EmailService
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
        assert client.get(f"{AUTH}/provider-languages").json() == [
            {"id": language_id, "name": "Hindi", "code": "hi"}
        ]
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
        assert client.get(f"{AUTH}/provider-languages").json() == []
        token = parse_qs(urlparse(sent_urls[0]).query)["token"][0]
        assert client.post(f"{AUTH}/verify-email", json={"token": token}).status_code == 200
        assert client.post(f"{APPLICATIONS}/{application.id}/approve", headers=headers).status_code == 200
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

        approved = client.post(
            f"{APPLICATIONS}/{application.id}/approve",
            headers=_admin_headers(admin),
        )
        assert approved.status_code == 200
        body = approved.json()
        assert body["review_status"] == "APPROVED"
        assert body["provider_id"]

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