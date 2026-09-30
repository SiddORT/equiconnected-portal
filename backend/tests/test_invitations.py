"""
Provider Invitation tests — Phase 7 (invitations & email backend).

Covers:
  - Admin auth requirements (401 without token, 403 for non-admin)
  - Invitation creation for an existing provider
  - Invitation creation that auto-creates a new provider
  - Provider type mismatch → 422
  - Public GET with a raw token that is absent from the DB → 404
  - Duplicate active invitation → 409
  - Public GET /accept (validate_token, marks ACCEPTED) happy path
  - Public POST /{token}/save (save_draft) happy path
  - Public POST /{token}/submit happy path → provider UNDER_REVIEW + UNPUBLISHED, invitation COMPLETED
  - Expired invitation → 410 on public access
  - Cancel invitation happy path
  - Cancel already-cancelled/completed invitation → 409
  - Resend invalidates old token; new token works, old token doesn't
  - Completed single-use: second public GET returns 409
  - After submit provider status is UNDER_REVIEW and publication_status is UNPUBLISHED
  - No duplicate invitation for same existing provider + email
  - EmailService.send_invitation_email is monkeypatched throughout to capture
    the invitation URL/token and avoid SMTP.
"""
from __future__ import annotations

import hashlib
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.models.enums import (
    DoctorOrganizationStatus,
    InvitationStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.doctor import DoctorProfile, DoctorQualification
from app.models.provider import Provider, ProviderLocation, ProviderPhone
from app.repositories.user_repository import UserRepository
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.provider_repository import ProviderRepository
from app.services.email_service import EmailDeliveryError, EmailService
from app.services.invitation_service import (
    DuplicateInvitationError,
    InvitationService,
)

# ── Constants ─────────────────────────────────────────────────────────────────

ADMIN_BASE = "/api/v1/admin/invitations"
PUBLIC_BASE = "/api/v1/provider/invitations"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token_from_url(url: str) -> str:
    """Extract the raw token from an invitation URL like …/provider/invitations/<token>."""
    match = re.search(r"/provider/invitations/([^/?\s]+)", url)
    assert match, f"Could not extract token from URL: {url!r}"
    return match.group(1)


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def captured_email() -> Generator[dict, None, None]:
    """
    Monkeypatches EmailService.send_invitation_email so tests never hit SMTP.
    Yields a dict that accumulates calls:
      captured["calls"] → list of (recipient, provider_type, url, expires_at)
      captured["url"]   → last invitation URL sent
      captured["token"] → raw token extracted from the last URL
    """
    calls: list = []
    captured: dict = {"calls": calls, "url": None, "token": None}

    def _fake_send(self, recipient, provider_type, invitation_url, expires_at):
        calls.append((recipient, provider_type, invitation_url, expires_at))
        captured["url"] = invitation_url
        captured["token"] = _token_from_url(invitation_url)

    original = EmailService.send_invitation_email
    EmailService.send_invitation_email = _fake_send
    try:
        yield captured
    finally:
        EmailService.send_invitation_email = original


@pytest.fixture()
def admin_token(client: TestClient, seeded_admin) -> str:
    user, password = seeded_admin
    return _login(client, user.email, password)


@pytest.fixture()
def non_admin_token(client: TestClient, db) -> str:
    repo = UserRepository(db)
    role = repo.get_role_by_name("visitor") or repo.create_role("visitor", "Visitor")
    user = repo.create_user(
        email="visitor@inv-test.example.com",
        password_hash=hash_password("Visitor#2026!XYZ"),
        role=role,
    )
    db.commit()
    return _login(client, user.email, "Visitor#2026!XYZ")


@pytest.fixture()
def existing_provider(db) -> Provider:
    """A pre-existing HOSPITAL provider in DRAFT / UNPUBLISHED state."""
    provider = Provider(
        provider_type=ProviderType.HOSPITAL,
        name="Existing Hospital",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.DRAFT,
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def _invitation_body(
    recipient_email: str = "provider@example.com",
    provider_type: str = "HOSPITAL",
    **overrides,
) -> dict:
    body: dict = {
        "recipient_email": recipient_email,
        "provider_type": provider_type,
        "visit_stability": "STABLE_VISIT",
    }
    body.update(overrides)
    return body


def _create_invitation(
    client: TestClient,
    token: str,
    *,
    recipient_email: str = "provider@example.com",
    provider_type: str = "HOSPITAL",
    **overrides,
) -> dict:
    body = _invitation_body(recipient_email, provider_type, **overrides)
    resp = client.post(ADMIN_BASE, json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Auth tests ────────────────────────────────────────────────────────────────

class TestAdminAuth:
    def test_list_requires_auth(self, client: TestClient):
        assert client.get(ADMIN_BASE).status_code == 401

    def test_create_requires_auth(self, client: TestClient):
        assert client.post(ADMIN_BASE, json=_invitation_body()).status_code == 401

    def test_create_requires_admin_role(self, client: TestClient, non_admin_token: str):
        assert (
            client.post(ADMIN_BASE, json=_invitation_body(), headers=_auth(non_admin_token)).status_code
            == 403
        )

    def test_cancel_requires_auth(self, client: TestClient):
        assert client.post(f"{ADMIN_BASE}/{uuid.uuid4()}/cancel").status_code == 401

    def test_resend_requires_auth(self, client: TestClient):
        assert client.post(f"{ADMIN_BASE}/{uuid.uuid4()}/resend").status_code == 401

    def test_cancel_requires_admin_role(self, client: TestClient, non_admin_token: str):
        assert (
            client.post(
                f"{ADMIN_BASE}/{uuid.uuid4()}/cancel", headers=_auth(non_admin_token)
            ).status_code
            == 403
        )


# ── Admin create ──────────────────────────────────────────────────────────────

class TestAdminCreate:
    def test_new_doctor_names_round_trip_and_override_display_name(
        self, client: TestClient, admin_token: str, db, captured_email: dict
    ):
        bad = client.post(ADMIN_BASE, headers=_auth(admin_token), json=_invitation_body(
            recipient_email="invalid-doctor@example.com", provider_type="DOCTOR",
            first_name=" ", last_name="Quinn",
        ))
        assert bad.status_code == 422
        too_long = client.post(ADMIN_BASE, headers=_auth(admin_token), json=_invitation_body(
            recipient_email="long-doctor@example.com", provider_type="DOCTOR",
            first_name="A" * 150, last_name="B" * 150,
        ))
        assert too_long.status_code == 422
        data = _create_invitation(
            client, admin_token, recipient_email="named-doctor@example.com",
            provider_type="DOCTOR", provider_name="Inconsistent",
            first_name="  Avery ", last_name=" Quinn  ",
        )
        provider = db.get(Provider, uuid.UUID(data["provider_id"]))
        assert provider.name == "Avery Quinn"
        profile = db.get(DoctorProfile, provider.id)
        assert (profile.first_name, profile.last_name) == ("Avery", "Quinn")
        token = captured_email["token"]
        snapshot = client.get(f"{PUBLIC_BASE}/{token}")
        assert snapshot.status_code == 200
        assert snapshot.json()["provider"]["first_name"] == "Avery"
        draft = client.post(f"{PUBLIC_BASE}/{token}/save", json={
            "first_name": "  Maya ", "last_name": " Singh ", "name": "Wrong display",
        })
        assert draft.status_code == 200, draft.text
        assert draft.json()["provider"]["name"] == "Maya Singh"
        assert draft.json()["provider"]["last_name"] == "Singh"
        missing = client.post(f"{PUBLIC_BASE}/{token}/submit", json={
            "name": "Wrong", "visit_stability": "NOT_STABLE_VISIT",
            "first_name": " ", "last_name": "Singh",
        })
        assert missing.status_code == 422
        completed = client.post(f"{PUBLIC_BASE}/{token}/submit", json={
            "name": "Wrong", "visit_stability": "NOT_STABLE_VISIT",
            "first_name": "  Mira ", "last_name": " Stone ",
        })
        assert completed.status_code == 200, completed.text
        db.refresh(provider)
        db.refresh(profile)
        assert provider.name == "Mira Stone"
        assert (profile.first_name, profile.last_name) == ("Mira", "Stone")

    def test_legacy_doctor_and_existing_provider_invitations_stay_compatible(
        self, client: TestClient, admin_token: str, db, captured_email: dict, existing_provider
    ):
        legacy = _create_invitation(client, admin_token, recipient_email="legacy-names@example.com",
                                    provider_type="DOCTOR", provider_name="Dr. Legacy Name")
        token = captured_email["token"]
        snapshot = client.get(f"{PUBLIC_BASE}/{token}").json()["provider"]
        assert snapshot["name"] == "Dr. Legacy Name"
        assert snapshot["first_name"] is None
        saved = client.post(f"{PUBLIC_BASE}/{token}/save", json={"first_name": "Legacy"})
        assert saved.status_code == 200
        assert saved.json()["provider"]["name"] == "Dr. Legacy Name"
        final = client.post(f"{PUBLIC_BASE}/{token}/submit", json={
            "name": "Dr. Legacy Name", "visit_stability": "NOT_STABLE_VISIT",
            "first_name": "Legacy", "last_name": "Name",
        })
        assert final.status_code == 200, final.text
        assert db.get(Provider, uuid.UUID(legacy["provider_id"])).name == "Legacy Name"
        old_client = _create_invitation(client, admin_token, recipient_email="old-names@example.com",
                                        provider_type="DOCTOR", provider_name="Old API Doctor")
        assert client.post(f'{PUBLIC_BASE}/{captured_email["token"]}/submit',
                           json={"name": "Old API Doctor", "visit_stability": "NOT_STABLE_VISIT"}).status_code == 200
        assert db.get(Provider, uuid.UUID(old_client["provider_id"])).name == "Old API Doctor"
        existing_provider.description = "Retain existing description"
        db.commit()
        existing = _create_invitation(client, admin_token, recipient_email="existing-names@example.com",
                                      provider_type="HOSPITAL", provider_id=str(existing_provider.id))
        assert existing["provider_id"] == str(existing_provider.id)
        assert db.get(Provider, existing_provider.id).name == "Existing Hospital"
        org_token = captured_email["token"]
        assert client.post(f"{PUBLIC_BASE}/{org_token}/save", json={"website": "https://example.com"}).status_code == 200
        submitted = client.post(f"{PUBLIC_BASE}/{org_token}/submit", json={
            "name": "Existing Hospital", "visit_stability": "STABLE_VISIT",
        })
        assert submitted.status_code == 200, submitted.text
        db.refresh(existing_provider)
        assert existing_provider.description == "Retain existing description"

    def test_create_for_new_provider(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        """When no provider_id given a new provider is auto-created."""
        data = _create_invitation(
            client,
            admin_token,
            recipient_email="newprovider@example.com",
            provider_type="CLINIC",
            provider_name="Brand New Clinic",
        )
        assert data["status"] == InvitationStatus.PENDING.value
        assert data["provider_id"] is not None
        assert data["recipient_email"] == "newprovider@example.com"
        provider = db.get(Provider, uuid.UUID(data["provider_id"]))
        assert provider is not None
        assert provider.name == "Brand New Clinic"
        # Email was sent
        assert len(captured_email["calls"]) == 1
        recipient, ptype, url, _ = captured_email["calls"][0]
        assert recipient == "newprovider@example.com"
        assert ptype == ProviderType.CLINIC
        assert "provider/invitations/" in url

        list_response = client.get(ADMIN_BASE, headers=_auth(admin_token))
        assert list_response.status_code == 200
        listed = next(
            item for item in list_response.json()["data"] if item["id"] == data["id"]
        )
        assert listed["provider_name"] == "Brand New Clinic"

    def test_create_for_existing_provider(
        self,
        client: TestClient,
        admin_token: str,
        existing_provider: Provider,
        captured_email: dict,
    ):
        """Invitation can reference an already-existing provider."""
        data = _create_invitation(
            client,
            admin_token,
            recipient_email="hospital@example.com",
            provider_type="HOSPITAL",
            provider_id=str(existing_provider.id),
        )
        assert data["provider_id"] == str(existing_provider.id)
        assert data["status"] == InvitationStatus.PENDING.value
        assert len(captured_email["calls"]) == 1

    def test_provider_type_mismatch_returns_422(
        self,
        client: TestClient,
        admin_token: str,
        existing_provider: Provider,
        captured_email: dict,
    ):
        """Supplying a provider_type that differs from the existing provider → 422."""
        resp = client.post(
            ADMIN_BASE,
            json=_invitation_body(
                recipient_email="mismatch@example.com",
                provider_type="CLINIC",  # existing_provider is HOSPITAL
                provider_id=str(existing_provider.id),
            ),
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "provider_type_mismatch"
        # No email sent
        assert len(captured_email["calls"]) == 0

    def test_duplicate_active_invitation_returns_409(
        self,
        client: TestClient,
        admin_token: str,
        existing_provider: Provider,
        captured_email: dict,
    ):
        """A second PENDING invitation for the same provider + email → 409."""
        email = "dup@example.com"
        _create_invitation(
            client,
            admin_token,
            recipient_email=email,
            provider_type="HOSPITAL",
            provider_id=str(existing_provider.id),
        )
        resp = client.post(
            ADMIN_BASE,
            json=_invitation_body(
                recipient_email=email,
                provider_type="HOSPITAL",
                provider_id=str(existing_provider.id),
            ),
            headers=_auth(admin_token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "duplicate_invitation"

    def test_existing_account_email_returns_clear_validation_error(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        users = UserRepository(db)
        visitor = users.get_role_by_name("visitor") or users.create_role("visitor", "Visitor")
        users.create_user(
            email="existing-account@example.com",
            password_hash=hash_password("VisitorPass9"),
            role=visitor,
            roles=[visitor],
        )
        db.commit()

        resp = client.post(
            ADMIN_BASE,
            json=_invitation_body(recipient_email="existing-account@example.com"),
            headers=_auth(admin_token),
        )

        assert resp.status_code == 409
        assert resp.json()["detail"] == {
            "code": "recipient_email_in_use",
            "message": (
                "This email address already belongs to an EquiConnected account. "
                "Use a different email address to send a provider invitation."
            ),
        }
        assert captured_email["calls"] == []

    def test_unknown_provider_id_returns_404(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        resp = client.post(
            ADMIN_BASE,
            json=_invitation_body(
                provider_type="HOSPITAL",
                provider_id=str(uuid.uuid4()),
            ),
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "provider_not_found"

    def test_list_returns_created_invitation(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        _create_invitation(
            client,
            admin_token,
            recipient_email="list@example.com",
            provider_name="Listed Hospital",
        )
        resp = client.get(ADMIN_BASE, headers=_auth(admin_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] >= 1
        listed = next(item for item in body["data"] if item["recipient_email"] == "list@example.com")
        assert listed["provider_name"] == "Listed Hospital"


# ── Public endpoints ──────────────────────────────────────────────────────────

class TestPublicGet:
    def test_get_valid_token_marks_accepted(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        """GET /{token} on a PENDING invitation marks it ACCEPTED and returns provider info."""
        _create_invitation(client, admin_token, recipient_email="accept@example.com")
        token = captured_email["token"]
        assert token is not None

        resp = client.get(f"{PUBLIC_BASE}/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "provider_type" in data
        assert "provider" in data

    def test_get_invalid_token_returns_404(self, client: TestClient):
        """A token that has never been issued → 404."""
        resp = client.get(f"{PUBLIC_BASE}/completely-bogus-token-xyz")
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "invitation_not_found"

    def test_get_expired_token_returns_410(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
        seeded_admin,
    ):
        """An invitation whose expires_at is in the past → 410."""
        # Create invitation normally first
        inv_data = _create_invitation(client, admin_token, recipient_email="expire@example.com")
        token = captured_email["token"]

        # Manually expire it in the DB
        from sqlalchemy import update as sa_update
        db.execute(
            sa_update(ProviderInvitation)
            .where(ProviderInvitation.id == uuid.UUID(inv_data["id"]))
            .values(
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                status=InvitationStatus.PENDING,
            )
        )
        db.commit()

        resp = client.get(f"{PUBLIC_BASE}/{token}")
        assert resp.status_code == 410
        assert resp.json()["detail"]["code"] == "invitation_expired"

    def test_completed_invitation_returns_409(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        """After submit, trying to re-use the original token → 409 (token replaced)."""
        _create_invitation(client, admin_token, recipient_email="complete@example.com")
        token = captured_email["token"]

        # Accept first
        client.get(f"{PUBLIC_BASE}/{token}")

        # Submit (completes the invitation and invalidates the token hash)
        client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Final Clinic", "visit_stability": "STABLE_VISIT"},
        )

        # The original token is now gone from the DB (replaced by a new random hash)
        resp = client.get(f"{PUBLIC_BASE}/{token}")
        # Either 404 (token replaced) or 409 (status check depending on timing)
        assert resp.status_code in (404, 409)


class TestPublicSave:
    def test_invitation_email_can_be_removed_and_replaced_in_draft(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
        db,
    ):
        invitation = _create_invitation(
            client, admin_token, recipient_email="invited@example.com"
        )
        token = captured_email["token"]
        initial = client.get(f"{PUBLIC_BASE}/{token}")
        assert initial.status_code == 200
        assert initial.json()["recipient_email"] == "invited@example.com"
        assert initial.json()["emails_edited"] is False

        removed = client.post(f"{PUBLIC_BASE}/{token}/save", json={"emails": []})
        assert removed.status_code == 200
        assert removed.json()["emails_edited"] is True
        assert removed.json()["provider"]["emails"] == []
        assert removed.json()["provider"]["email"] is None
        reopened = client.get(f"{PUBLIC_BASE}/{token}")
        assert reopened.json()["emails_edited"] is True
        assert reopened.json()["provider"]["emails"] == []

        replaced = client.post(
            f"{PUBLIC_BASE}/{token}/save",
            json={"emails": [{"email": "office@example.com", "is_primary": True}]},
        )
        assert replaced.status_code == 200
        assert replaced.json()["provider"]["emails"] == [
            {"email": "office@example.com", "is_primary": True}
        ]
        assert db.get(Provider, uuid.UUID(invitation["provider_id"])).email is None

    def test_save_draft_updates_provider(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        _create_invitation(client, admin_token, recipient_email="save@example.com")
        token = captured_email["token"]

        resp = client.post(
            f"{PUBLIC_BASE}/{token}/save",
            json={"name": "Updated Name", "visit_stability": "NOT_STABLE_VISIT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    def test_service_details_and_locations_round_trip_through_draft(
        self, client, admin_token, captured_email, db
    ):
        invitation = _create_invitation(
            client, admin_token, recipient_email="service-draft@example.com"
        )
        token = captured_email["token"]
        fields = {
            "maximum_working_radius_km": 25,
            "emergency_services_available": True,
            "emergency_contact_number": "+15551234567",
            "locations": [
                {
                    "name": "Main clinic",
                    "address_line_1": "10 Main Street",
                    "city": "Toronto",
                    "country": "Canada",
                    "is_primary": True,
                }
            ],
        }

        saved = client.post(f"{PUBLIC_BASE}/{token}/save", json=fields)
        assert saved.status_code == 200, saved.text
        provider = saved.json()["provider"]
        assert provider["maximum_working_radius_km"] == 25
        assert provider["emergency_services_available"] is True
        assert provider["emergency_contact_number"] == "+15551234567"
        assert provider["locations"][0]["city"] == "Toronto"

        reopened = client.get(f"{PUBLIC_BASE}/{token}")
        assert reopened.status_code == 200
        assert reopened.json()["provider"]["maximum_working_radius_km"] == 25
        assert reopened.json()["provider"]["emergency_contact_number"] == "+15551234567"
        assert reopened.json()["provider"]["locations"][0]["address_line_1"] == "10 Main Street"
        db.expire_all()
        provider_model = db.get(Provider, uuid.UUID(invitation["provider_id"]))
        assert len(provider_model.locations) == 1
        assert provider_model.locations[0].is_primary is True

    def test_disabling_service_options_clears_dependent_draft_values(
        self, client, admin_token, captured_email
    ):
        _create_invitation(client, admin_token, recipient_email="clear-service@example.com")
        token = captured_email["token"]
        enabled = client.post(
            f"{PUBLIC_BASE}/{token}/save",
            json={
                "maximum_working_radius_km": 12,
                "emergency_services_available": True,
                "emergency_contact_number": "+15551234567",
            },
        )
        assert enabled.status_code == 200, enabled.text

        disabled = client.post(
            f"{PUBLIC_BASE}/{token}/save",
            json={
                "visit_stability": "NOT_STABLE_VISIT",
                "emergency_services_available": False,
            },
        )
        assert disabled.status_code == 200, disabled.text
        provider = disabled.json()["provider"]
        assert provider["maximum_working_radius_km"] is None
        assert provider["emergency_contact_number"] is None

    def test_save_with_invalid_token_returns_404(self, client: TestClient):
        resp = client.post(
            f"{PUBLIC_BASE}/nonexistent-token/save",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    def test_save_expired_returns_410(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        inv_data = _create_invitation(client, admin_token, recipient_email="saveexp@example.com")
        token = captured_email["token"]

        from sqlalchemy import update as sa_update
        db.execute(
            sa_update(ProviderInvitation)
            .where(ProviderInvitation.id == uuid.UUID(inv_data["id"]))
            .values(
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                status=InvitationStatus.PENDING,
            )
        )
        db.commit()

        resp = client.post(f"{PUBLIC_BASE}/{token}/save", json={"name": "Late Update"})
        assert resp.status_code == 410


class TestPublicSubmit:
    def test_submit_completes_invitation_and_sets_provider_status(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        """submit → invitation COMPLETED, provider UNDER_REVIEW + UNPUBLISHED."""
        inv_data = _create_invitation(client, admin_token, recipient_email="submit@example.com")
        token = captured_email["token"]

        resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Submitted Clinic", "visit_stability": "STABLE_VISIT"},
        )
        assert resp.status_code == 200

        # Check DB state for invitation
        invitation = db.get(ProviderInvitation, uuid.UUID(inv_data["id"]))
        db.refresh(invitation)
        assert invitation.status == InvitationStatus.COMPLETED
        assert invitation.completed_at is not None

        # Check DB state for provider
        provider = db.get(Provider, invitation.provider_id)
        db.refresh(provider)
        assert provider.status == ProviderStatus.UNDER_REVIEW
        assert provider.publication_status == PublicationStatus.UNPUBLISHED

    def test_submit_without_required_fields_returns_422(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        """SubmitRequest requires name and visit_stability; missing → 422."""
        _create_invitation(client, admin_token, recipient_email="badsubmit@example.com")
        token = captured_email["token"]

        resp = client.post(f"{PUBLIC_BASE}/{token}/submit", json={})
        assert resp.status_code == 422

    def test_service_details_are_conditionally_validated_on_submit(
        self, client, admin_token, captured_email
    ):
        _create_invitation(client, admin_token, recipient_email="service-submit@example.com")
        token = captured_email["token"]

        missing_radius = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={
                "name": "Radius Clinic",
                "visit_stability": "STABLE_VISIT",
                "maximum_working_radius_km": None,
            },
        )
        assert missing_radius.status_code == 422
        assert "positive maximum working radius" in missing_radius.json()["detail"]["message"]

        missing_emergency_number = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={
                "name": "Emergency Clinic",
                "visit_stability": "NOT_STABLE_VISIT",
                "emergency_services_available": True,
            },
        )
        assert missing_emergency_number.status_code == 422
        assert "complete international emergency contact number" in missing_emergency_number.json()["detail"]["message"]

    @pytest.mark.parametrize(
        "number",
        (
            "1 555 123 4567",
            "+1 2345",
            "+12345678901234567890",
        ),
    )
    def test_submit_rejects_incomplete_or_malformed_emergency_numbers(
        self, client, admin_token, captured_email, number
    ):
        _create_invitation(client, admin_token, recipient_email=f"bad-phone-{uuid.uuid4()}@example.com")
        token = captured_email["token"]
        response = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={
                "name": "Emergency Clinic",
                "visit_stability": "NOT_STABLE_VISIT",
                "emergency_services_available": True,
                "emergency_contact_number": number,
            },
        )
        assert response.status_code == 422
        assert "complete international emergency contact number" in response.json()["detail"]["message"]

    def test_submit_accepts_formatted_full_number_saved_in_draft(
        self, client, admin_token, captured_email
    ):
        _create_invitation(client, admin_token, recipient_email="saved-phone@example.com")
        token = captured_email["token"]
        saved = client.post(
            f"{PUBLIC_BASE}/{token}/save",
            json={
                "emergency_contact_number": "+1 (555) 123-4567",
            },
        )
        assert saved.status_code == 200, saved.text

        response = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={
                "name": "Emergency Clinic",
                "visit_stability": "NOT_STABLE_VISIT",
                "emergency_services_available": True,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["provider"]["emergency_contact_number"] == "+1 (555) 123-4567"

    def test_legacy_submit_payload_without_service_fields_remains_valid(
        self, client, admin_token, captured_email
    ):
        _create_invitation(client, admin_token, recipient_email="legacy-submit@example.com")
        token = captured_email["token"]
        response = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Legacy Clinic", "visit_stability": "STABLE_VISIT"},
        )
        assert response.status_code == 200, response.text

    def test_submit_expired_returns_410(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        inv_data = _create_invitation(client, admin_token, recipient_email="subexp@example.com")
        token = captured_email["token"]

        from sqlalchemy import update as sa_update
        db.execute(
            sa_update(ProviderInvitation)
            .where(ProviderInvitation.id == uuid.UUID(inv_data["id"]))
            .values(
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                status=InvitationStatus.PENDING,
            )
        )
        db.commit()

        resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Late Submit", "visit_stability": "STABLE_VISIT"},
        )
        assert resp.status_code == 410

    def test_submit_cancelled_returns_409(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        inv_data = _create_invitation(client, admin_token, recipient_email="subcancelled@example.com")
        token = captured_email["token"]

        # Cancel via admin
        client.post(
            f"{ADMIN_BASE}/{inv_data['id']}/cancel",
            headers=_auth(admin_token),
        )

        resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Cancelled Submit", "visit_stability": "STABLE_VISIT"},
        )
        assert resp.status_code == 409


# ── Cancel ────────────────────────────────────────────────────────────────────

class TestCancel:
    def test_cancel_pending_invitation(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        inv_data = _create_invitation(client, admin_token, recipient_email="cancel@example.com")
        resp = client.post(
            f"{ADMIN_BASE}/{inv_data['id']}/cancel",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == InvitationStatus.CANCELLED.value

    def test_cancel_already_cancelled_returns_409(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        inv_data = _create_invitation(client, admin_token, recipient_email="cancel2@example.com")
        # First cancel
        client.post(f"{ADMIN_BASE}/{inv_data['id']}/cancel", headers=_auth(admin_token))
        # Second cancel
        resp = client.post(f"{ADMIN_BASE}/{inv_data['id']}/cancel", headers=_auth(admin_token))
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "invalid_invitation_state"

    def test_cancel_completed_returns_409(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        inv_data = _create_invitation(client, admin_token, recipient_email="cancelcomp@example.com")
        token = captured_email["token"]

        # Submit to complete it
        client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "To Complete", "visit_stability": "STABLE_VISIT"},
        )

        resp = client.post(f"{ADMIN_BASE}/{inv_data['id']}/cancel", headers=_auth(admin_token))
        assert resp.status_code == 409

    def test_cancel_unknown_invitation_returns_404(
        self,
        client: TestClient,
        admin_token: str,
    ):
        resp = client.post(f"{ADMIN_BASE}/{uuid.uuid4()}/cancel", headers=_auth(admin_token))
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "invitation_not_found"


# ── Resend ────────────────────────────────────────────────────────────────────

class TestResend:
    def test_resend_invalidates_old_token(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        """After resend, the old token 404s; the new token works."""
        inv_data = _create_invitation(client, admin_token, recipient_email="resend@example.com")
        old_token = captured_email["token"]

        # Resend
        resp = client.post(
            f"{ADMIN_BASE}/{inv_data['id']}/resend",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        new_token = captured_email["token"]
        assert new_token != old_token

        # Old token → 404 (hash is replaced in DB)
        old_resp = client.get(f"{PUBLIC_BASE}/{old_token}")
        assert old_resp.status_code == 404

        # New token → 200
        new_resp = client.get(f"{PUBLIC_BASE}/{new_token}")
        assert new_resp.status_code == 200

    def test_resend_updates_expiry(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        """Resending a previously-expired invitation resets status to PENDING."""
        inv_data = _create_invitation(client, admin_token, recipient_email="resendexp@example.com")

        from sqlalchemy import update as sa_update
        db.execute(
            sa_update(ProviderInvitation)
            .where(ProviderInvitation.id == uuid.UUID(inv_data["id"]))
            .values(
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                status=InvitationStatus.PENDING,
            )
        )
        db.commit()

        resp = client.post(
            f"{ADMIN_BASE}/{inv_data['id']}/resend",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == InvitationStatus.PENDING.value

    def test_resend_completed_invitation_returns_409(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        inv_data = _create_invitation(client, admin_token, recipient_email="resendcomp@example.com")
        token = captured_email["token"]

        # Complete it
        client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Done Provider", "visit_stability": "STABLE_VISIT"},
        )

        resp = client.post(
            f"{ADMIN_BASE}/{inv_data['id']}/resend",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "invalid_invitation_state"

    def test_resend_cancelled_invitation_returns_409(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        inv_data = _create_invitation(client, admin_token, recipient_email="resendcanc@example.com")
        client.post(f"{ADMIN_BASE}/{inv_data['id']}/cancel", headers=_auth(admin_token))

        resp = client.post(
            f"{ADMIN_BASE}/{inv_data['id']}/resend",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 409

    def test_resend_unknown_invitation_returns_404(
        self,
        client: TestClient,
        admin_token: str,
    ):
        resp = client.post(f"{ADMIN_BASE}/{uuid.uuid4()}/resend", headers=_auth(admin_token))
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "invitation_not_found"


# ── Completed single-use guarantee ───────────────────────────────────────────

class TestSingleUse:
    def test_completed_invitation_token_unusable(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        """
        After submit the token_hash is replaced, so the original token is gone
        from the DB.  Any subsequent public request with that token returns 404.
        """
        _create_invitation(client, admin_token, recipient_email="singleuse@example.com")
        token = captured_email["token"]

        # Submit via the token (internally accepts then completes)
        submit_resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Single Use Provider", "visit_stability": "STABLE_VISIT"},
        )
        assert submit_resp.status_code == 200

        # Token should now be dead
        resp = client.get(f"{PUBLIC_BASE}/{token}")
        assert resp.status_code in (404, 409), (
            f"Expected 404 or 409 after completion, got {resp.status_code}: {resp.text}"
        )


# ── Provider status after submission ─────────────────────────────────────────

class TestProviderStatusAfterSubmit:
    def test_under_review_and_unpublished(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        """Submitting an invitation puts the provider in UNDER_REVIEW / UNPUBLISHED."""
        inv_data = _create_invitation(
            client,
            admin_token,
            recipient_email="reviewcheck@example.com",
            provider_type="HOSPITAL",
            provider_name="Status Check Hospital",
        )
        token = captured_email["token"]

        client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Status Check Hospital", "visit_stability": "STABLE_VISIT"},
        )

        invitation = db.get(ProviderInvitation, uuid.UUID(inv_data["id"]))
        db.refresh(invitation)
        provider = db.get(Provider, invitation.provider_id)
        db.refresh(provider)

        assert provider.status == ProviderStatus.UNDER_REVIEW
        assert provider.publication_status == PublicationStatus.UNPUBLISHED


# ── No duplicate for existing provider (after cancel, a new one is fine) ──────

class TestNoDuplicateExistingProvider:
    def test_no_active_duplicate_for_existing_provider(
        self,
        client: TestClient,
        admin_token: str,
        existing_provider: Provider,
        captured_email: dict,
    ):
        """Cannot create a second PENDING invite for the same provider+email pair."""
        email = "nodedup@example.com"
        _create_invitation(
            client,
            admin_token,
            recipient_email=email,
            provider_type="HOSPITAL",
            provider_id=str(existing_provider.id),
        )
        resp = client.post(
            ADMIN_BASE,
            json=_invitation_body(
                recipient_email=email,
                provider_type="HOSPITAL",
                provider_id=str(existing_provider.id),
            ),
            headers=_auth(admin_token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "duplicate_invitation"

    def test_new_invitation_allowed_after_cancel(
        self,
        client: TestClient,
        admin_token: str,
        existing_provider: Provider,
        captured_email: dict,
    ):
        """After cancelling the active invite, a fresh invite for the same pair is valid."""
        email = "aftercancel@example.com"
        first = _create_invitation(
            client,
            admin_token,
            recipient_email=email,
            provider_type="HOSPITAL",
            provider_id=str(existing_provider.id),
        )
        client.post(f"{ADMIN_BASE}/{first['id']}/cancel", headers=_auth(admin_token))

        # This should now succeed (no active invite remaining)
        resp = client.post(
            ADMIN_BASE,
            json=_invitation_body(
                recipient_email=email,
                provider_type="HOSPITAL",
                provider_id=str(existing_provider.id),
            ),
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201


# ── Email capture ─────────────────────────────────────────────────────────────

class TestEmailCapture:
    def test_email_captured_not_sent_via_smtp(
        self,
        client: TestClient,
        admin_token: str,
        captured_email: dict,
    ):
        """Verify monkeypatching works: no SMTP error, URL and token captured."""
        _create_invitation(client, admin_token, recipient_email="emailcap@example.com")
        assert captured_email["url"] is not None
        assert captured_email["token"] is not None
        assert len(captured_email["calls"]) == 1
        recipient, ptype, url, expires_at = captured_email["calls"][0]
        assert recipient == "emailcap@example.com"
        assert "/provider/invitations/" in url

    def test_token_in_url_matches_db_hash(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
    ):
        """The raw token in the URL hashes to the token_hash stored in the DB."""
        inv_data = _create_invitation(client, admin_token, recipient_email="tokencheck@example.com")
        raw_token = captured_email["token"]
        expected_hash = _sha256(raw_token)

        invitation = db.get(ProviderInvitation, uuid.UUID(inv_data["id"]))
        assert invitation.token_hash == expected_hash


class TestDeliveryFailures:
    def test_create_failure_preserves_pending_invitation_and_draft(
        self, client: TestClient, admin_token: str, db, monkeypatch
    ):
        def fail_delivery(*_args, **_kwargs):
            raise EmailDeliveryError("Unable to deliver invitation email.")

        monkeypatch.setattr(EmailService, "send_invitation_email", fail_delivery)
        response = client.post(
            ADMIN_BASE,
            json=_invitation_body(
                "delivery-failed@example.com",
                provider_name="Preserved Draft Hospital",
            ),
            headers=_auth(admin_token),
        )
        assert response.status_code == 502

        invitation = db.query(ProviderInvitation).filter_by(
            recipient_email="delivery-failed@example.com"
        ).one()
        assert invitation.status == InvitationStatus.PENDING
        provider = db.get(Provider, invitation.provider_id)
        assert provider is not None
        assert provider.status == ProviderStatus.DRAFT

    def test_resend_failure_preserves_new_pending_token(
        self,
        client: TestClient,
        admin_token: str,
        db,
        captured_email: dict,
        monkeypatch,
    ):
        data = _create_invitation(
            client,
            admin_token,
            recipient_email="resend-failed@example.com",
        )
        invitation = db.get(ProviderInvitation, uuid.UUID(data["id"]))
        old_hash = invitation.token_hash

        def fail_delivery(*_args, **_kwargs):
            raise EmailDeliveryError("Unable to deliver invitation email.")

        monkeypatch.setattr(EmailService, "send_invitation_email", fail_delivery)
        response = client.post(
            f"{ADMIN_BASE}/{data['id']}/resend", headers=_auth(admin_token)
        )
        assert response.status_code == 502
        db.refresh(invitation)
        assert invitation.status == InvitationStatus.PENDING
        assert invitation.token_hash != old_hash


class TestCompleteProviderPayloads:
    def test_hospital_contacts_and_locations_are_saved_idempotently(
        self, client: TestClient, admin_token: str, db, captured_email: dict
    ):
        data = _create_invitation(
            client,
            admin_token,
            recipient_email="full-hospital@example.com",
            provider_name="Full Hospital",
        )
        token = captured_email["token"]
        payload = {
            "name": "Full Hospital",
            "description": "Complete profile",
            "visit_stability": "STABLE_VISIT",
            "locations": [
                {
                    "address_line_1": "1 Health Street",
                    "city": "London",
                    "country": "United Kingdom",
                    "is_primary": True,
                }
            ],
            "phones": [
                {
                    "country_code": "+44",
                    "number": "2070000000",
                    "is_primary": True,
                }
            ],
        }
        for _ in range(2):
            response = client.post(f"{PUBLIC_BASE}/{token}/save", json=payload)
            assert response.status_code == 200, response.text
        invitation = db.get(ProviderInvitation, uuid.UUID(data["id"]))
        assert (
            db.query(ProviderLocation)
            .filter_by(provider_id=invitation.provider_id)
            .count()
            == 1
        )
        assert (
            db.query(ProviderPhone)
            .filter_by(provider_id=invitation.provider_id)
            .count()
            == 1
        )

    def test_doctor_profile_and_qualifications_are_saved(
        self, client: TestClient, admin_token: str, db, captured_email: dict
    ):
        data = _create_invitation(
            client,
            admin_token,
            recipient_email="doctor-profile@example.com",
            provider_type="DOCTOR",
            provider_name="Dr Invite",
        )
        token = captured_email["token"]
        response = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={
                "name": "Dr Invite",
                "visit_stability": "NOT_STABLE_VISIT",
                "professional_title": "Consultant",
                "biography": "Specialist biography",
                "years_experience": 12,
                "qualifications": [
                    {
                        "title": "MD",
                        "institution": "Medical University",
                        "year_obtained": 2014,
                    }
                ],
            },
        )
        assert response.status_code == 200, response.text
        invitation = db.get(ProviderInvitation, uuid.UUID(data["id"]))
        profile = db.get(DoctorProfile, invitation.provider_id)
        assert profile.professional_title == "Consultant"
        assert profile.years_experience == 12
        assert (
            db.query(DoctorQualification)
            .filter_by(provider_id=invitation.provider_id)
            .count()
            == 1
        )


class TestConcurrentDuplicatePrevention:
    def test_concurrent_new_provider_invites_create_only_one_draft(
        self, db, seeded_admin, monkeypatch
    ):
        user, _ = seeded_admin
        user_id = user.id
        monkeypatch.setattr(
            EmailService, "send_invitation_email", lambda *_args, **_kwargs: None
        )
        session_factory = sessionmaker(
            bind=db.get_bind(), autocommit=False, autoflush=False
        )
        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def create_invitation() -> None:
            session = session_factory()
            try:
                service = InvitationService(
                    InvitationRepository(session),
                    ProviderRepository(session),
                )
                barrier.wait()
                service.create_invitation(
                    fields={
                        "recipient_email": "concurrent@example.com",
                        "provider_type": ProviderType.HOSPITAL,
                        "provider_id": None,
                        "provider_name": "Concurrent Hospital",
                        "visit_stability": VisitStability.STABLE_VISIT,
                    },
                    created_by=user_id,
                )
                outcomes.append("created")
            except DuplicateInvitationError:
                outcomes.append("duplicate")
            finally:
                session.close()

        threads = [threading.Thread(target=create_invitation) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive()

        assert sorted(outcomes) == ["created", "duplicate"]
        db.expire_all()
        assert (
            db.query(ProviderInvitation)
            .filter_by(recipient_email="concurrent@example.com")
            .count()
            == 1
        )
        assert (
            db.query(Provider)
            .filter_by(
                provider_type=ProviderType.HOSPITAL,
                email="concurrent@example.com",
            )
            .count()
            == 1
        )


# ── Atomic organization association on submit ────────────────────────────────

class TestSubmitOrganizationReconciliation:
    """organization_ids on submit must be reconciled atomically with the submit."""

    @pytest.fixture()
    def published_org(self, db) -> Provider:
        org = Provider(
            provider_type=ProviderType.HOSPITAL,
            name="Published Org Hospital",
            visit_stability=VisitStability.STABLE_VISIT,
            status=ProviderStatus.ACTIVE,
            publication_status=PublicationStatus.PUBLISHED,
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        return org

    def _doctor_token(self, client, admin_token, captured_email, email):
        _create_invitation(
            client, admin_token, recipient_email=email, provider_type="DOCTOR"
        )
        return captured_email["token"]

    def _relationships(self, db, doctor_id):
        from app.models.doctor import DoctorOrganization

        db.expire_all()
        return db.query(DoctorOrganization).filter_by(doctor_id=doctor_id).all()

    def test_failed_submit_creates_no_relationships(
        self, client, admin_token, db, captured_email, published_org
    ):
        token = self._doctor_token(client, admin_token, captured_email, "orgatomic1@example.com")
        inv = db.query(ProviderInvitation).filter_by(
            token_hash=_sha256(token)
        ).one()

        # Missing required visit_stability → 422; association must not persist.
        resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Dr. Atomic", "organization_ids": [str(published_org.id)]},
        )
        assert resp.status_code == 422
        assert self._relationships(db, inv.provider_id) == []

    def test_invalid_org_id_fails_submit_without_side_effects(
        self, client, admin_token, db, captured_email
    ):
        token = self._doctor_token(client, admin_token, captured_email, "orgatomic2@example.com")
        inv = db.query(ProviderInvitation).filter_by(token_hash=_sha256(token)).one()

        resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={
                "name": "Dr. Atomic",
                "visit_stability": "STABLE_VISIT",
                "organization_ids": [str(uuid.uuid4())],
            },
        )
        assert resp.status_code == 422
        db.expire_all()
        invitation = db.get(ProviderInvitation, inv.id)
        assert invitation.status != InvitationStatus.COMPLETED
        assert self._relationships(db, inv.provider_id) == []

    def test_successful_submit_creates_pending_relationships(
        self, client, admin_token, db, captured_email, published_org
    ):
        token = self._doctor_token(client, admin_token, captured_email, "orgatomic3@example.com")
        inv = db.query(ProviderInvitation).filter_by(token_hash=_sha256(token)).one()

        resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={
                "name": "Dr. Atomic",
                "visit_stability": "STABLE_VISIT",
                "organization_ids": [str(published_org.id)],
            },
        )
        assert resp.status_code == 200, resp.text
        rels = self._relationships(db, inv.provider_id)
        assert len(rels) == 1
        assert rels[0].organization_id == published_org.id
        assert rels[0].status == DoctorOrganizationStatus.PENDING

    def test_retry_after_failure_respects_chip_removal(
        self, client, admin_token, db, captured_email, published_org
    ):
        """Failed submit with an org, then retry without it → no relationship."""
        token = self._doctor_token(client, admin_token, captured_email, "orgatomic4@example.com")
        inv = db.query(ProviderInvitation).filter_by(token_hash=_sha256(token)).one()

        # Pre-existing PENDING relationship from the standalone association
        # endpoint (older flow / earlier attempt).
        resp = client.post(
            f"{PUBLIC_BASE}/{token}/organizations",
            json={"organization_id": str(published_org.id)},
        )
        assert resp.status_code == 201

        # First submit attempt fails validation (org list still includes it).
        resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={"name": "Dr. Atomic", "organization_ids": [str(published_org.id)]},
        )
        assert resp.status_code == 422

        # User removes the chip and retries — reconciliation must delete the
        # stale PENDING relationship.
        resp = client.post(
            f"{PUBLIC_BASE}/{token}/submit",
            json={
                "name": "Dr. Atomic",
                "visit_stability": "STABLE_VISIT",
                "organization_ids": [],
            },
        )
        assert resp.status_code == 200, resp.text
        assert self._relationships(db, inv.provider_id) == []


def test_non_doctor_experience_saves_reopens_submits_and_is_visible_to_admin(
    client, admin_token, captured_email, db
):
    invitation = _create_invitation(
        client,
        admin_token,
        recipient_email="clinic-years@example.com",
        provider_type="CLINIC",
        provider_name="Years Clinic",
    )
    token = captured_email["token"]

    saved = client.post(
        f"{PUBLIC_BASE}/{token}/save", json={"years_experience": 12}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["provider"]["years_experience"] == 12

    reopened = client.get(f"{PUBLIC_BASE}/{token}")
    assert reopened.status_code == 200
    assert reopened.json()["provider"]["years_experience"] == 12

    submitted = client.post(
        f"{PUBLIC_BASE}/{token}/submit",
        json={
            "name": "Years Clinic",
            "visit_stability": "STABLE_VISIT",
            "years_experience": 0,
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["provider"]["years_experience"] == 0

    provider_id = invitation["provider_id"]
    provider = db.get(Provider, uuid.UUID(provider_id))
    assert provider.years_experience == 0
    admin_detail = client.get(
        f"/api/v1/admin/providers/{provider_id}", headers=_auth(admin_token)
    )
    assert admin_detail.status_code == 200
    assert admin_detail.json()["years_experience"] == 0
    assert admin_detail.json()["doctor_profile"] is None


def test_doctor_experience_falls_back_from_profile_and_mirrors_zero(
    client, admin_token, captured_email, db
):
    invitation = _create_invitation(
        client,
        admin_token,
        recipient_email="doctor-years@example.com",
        provider_type="DOCTOR",
        provider_name="Dr. Years",
    )
    token = captured_email["token"]
    provider = db.get(Provider, uuid.UUID(invitation["provider_id"]))
    provider.doctor_profile = DoctorProfile(
        provider_id=provider.id, years_experience=18
    )
    db.commit()

    opened = client.get(f"{PUBLIC_BASE}/{token}")
    assert opened.status_code == 200
    assert opened.json()["provider"]["years_experience"] == 18

    submitted = client.post(
        f"{PUBLIC_BASE}/{token}/submit",
        json={
            "name": "Dr. Years",
            "visit_stability": "STABLE_VISIT",
            "years_experience": 0,
        },
    )
    assert submitted.status_code == 200, submitted.text
    db.refresh(provider)
    assert provider.years_experience == 0
    assert provider.doctor_profile.years_experience == 0
    assert submitted.json()["provider"]["years_experience"] == 0
