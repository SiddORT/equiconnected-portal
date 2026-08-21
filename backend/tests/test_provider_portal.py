"""Invitation-created provider portal access and ownership boundaries."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from app.core.security import hash_password
from app.models.enums import InvitationStatus, ProviderStatus, ProviderType, PublicationStatus, VisitStability
from app.models.invitation import ProviderInvitation
from app.models.provider import Provider, ProviderReview
from app.models.doctor import DoctorProfile
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService


def _login(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _completed_invitation(db, admin, *, email: str = "invitee@portal.example.com"):
    provider = Provider(
        provider_type=ProviderType.HOSPITAL,
        name="Portal Clinic",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.UNDER_REVIEW,
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    db.add(provider)
    db.flush()
    invitation = ProviderInvitation(
        provider_id=provider.id,
        provider_type=ProviderType.HOSPITAL,
        recipient_email=email,
        token_hash="completed-invitation-token",
        status=InvitationStatus.COMPLETED,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        sent_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        created_by=admin.id,
    )
    db.add(invitation)
    db.commit()
    return invitation, provider


def test_portal_setup_is_single_use_and_provider_profile_is_owned(client, db, seeded_admin, monkeypatch):
    admin, password = seeded_admin
    invitation, provider = _completed_invitation(db, admin)
    users = UserRepository(db)
    if users.get_role_by_name("provider") is None:
        users.create_role("provider", "Provider portal")
        db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, setup_url, _expires: delivered.append(setup_url),
    )
    admin_token = _login(client, admin.email, password)

    first = client.post(
        f"/api/v1/admin/invitations/{invitation.id}/portal-access",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["portal_access_sent_at"]
    first_token = parse_qs(urlparse(delivered[-1]).query)["token"][0]

    # A resend invalidates, rather than coexists with, the first link.
    resend = client.post(
        f"/api/v1/admin/invitations/{invitation.id}/portal-access",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resend.status_code == 200
    second_token = parse_qs(urlparse(delivered[-1]).query)["token"][0]
    assert second_token != first_token
    replaced = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={"token": first_token, "password": "PortalPass9", "password_confirmation": "PortalPass9"},
    )
    assert replaced.status_code == 409

    setup = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={"token": second_token, "password": "PortalPass9", "password_confirmation": "PortalPass9"},
    )
    assert setup.status_code == 200, setup.text
    assert client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={"token": second_token, "password": "PortalPass9", "password_confirmation": "PortalPass9"},
    ).status_code == 409

    provider_token = _login(client, invitation.recipient_email, "PortalPass9")
    visitor = users.get_role_by_name("visitor") or users.create_role("visitor", "Visitor")
    hidden_reviewer = users.create_user(
        email="hidden-reviewer@portal.example.com",
        password_hash=hash_password("ReviewerPass9"),
        role=visitor,
        first_name="Hidden",
        last_name="Reviewer",
        roles=[visitor],
    )
    db.add_all([
        ProviderReview(
            provider_id=provider.id,
            member_id=admin.id,
            rating=5,
            comment="Visible member comment",
            comment_visible=True,
        ),
        ProviderReview(
            provider_id=provider.id,
            member_id=hidden_reviewer.id,
            rating=1,
            comment="Hidden moderation comment",
            comment_visible=False,
        ),
    ])
    db.commit()
    profile = client.get(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {provider_token}"},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["id"] == str(provider.id)
    assert "status" not in profile.json()
    assert "provider_type" not in profile.json()
    assert [review["comment"] for review in profile.json()["visible_reviews"]] == ["Visible member comment"]
    assert "email" not in profile.json()["visible_reviews"][0]
    assert client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {provider_token}"},
        json={"name": "Updated Portal Clinic", "status": "ACTIVE", "publication_status": "PUBLISHED"},
    ).status_code == 200
    db.refresh(provider)
    assert provider.name == "Updated Portal Clinic"
    assert provider.status == ProviderStatus.UNDER_REVIEW
    assert provider.publication_status == PublicationStatus.UNPUBLISHED


def test_portal_access_rejects_unrelated_existing_account(client, db, seeded_admin, monkeypatch):
    admin, password = seeded_admin
    invitation, _provider = _completed_invitation(db, admin, email="conflict@portal.example.com")
    users = UserRepository(db)
    if users.get_role_by_name("provider") is None:
        users.create_role("provider", "Provider portal")
        db.commit()
    visitor = users.get_role_by_name("visitor") or users.create_role("visitor", "Visitor")
    users.create_user(
        email=invitation.recipient_email,
        password_hash=hash_password("VisitorPass9"),
        role=visitor,
        roles=[visitor],
    )
    db.commit()
    monkeypatch.setattr(EmailService, "send_provider_portal_access_email", lambda *_args: None)
    admin_token = _login(client, admin.email, password)
    response = client.post(
        f"/api/v1/admin/invitations/{invitation.id}/portal-access",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "portal_access_account_conflict"


def test_disabling_pending_provider_revokes_setup_link(client, db, seeded_admin, monkeypatch):
    admin, password = seeded_admin
    invitation, _provider = _completed_invitation(db, admin, email="disabled@portal.example.com")
    users = UserRepository(db)
    if users.get_role_by_name("provider") is None:
        users.create_role("provider", "Provider portal")
        db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, setup_url, _expires: delivered.append(setup_url),
    )
    admin_token = _login(client, admin.email, password)
    assert client.post(
        f"/api/v1/admin/invitations/{invitation.id}/portal-access",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).status_code == 200
    setup_token = parse_qs(urlparse(delivered[0]).query)["token"][0]

    account = users.get_by_email(invitation.recipient_email)
    assert account is not None and account.provider_portal_setup_pending is True
    # Exercise the same persistent active→disabled state transition used by
    # administrator account controls. The model hook clears pending setup and
    # invalidates all outstanding public setup tokens atomically.
    account.is_active = True
    db.commit()
    account.is_active = False
    db.commit()
    db.refresh(account)
    assert account.provider_portal_setup_pending is False
    denied = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={"token": setup_token, "password": "PortalPass9", "password_confirmation": "PortalPass9"},
    )
    assert denied.status_code == 409
    assert account.is_active is False


def test_doctor_portal_exposes_and_persists_clinical_profile_fields(client, db, seeded_admin):
    admin, _password = seeded_admin
    users = UserRepository(db)
    provider_role = users.get_role_by_name("provider") or users.create_role("provider", "Provider portal")
    doctor = Provider(
        provider_type=ProviderType.DOCTOR,
        name="Dr. Portal",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.UNDER_REVIEW,
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    db.add(doctor)
    db.flush()
    db.add(DoctorProfile(provider_id=doctor.id, professional_title="DVM", biography="Original biography"))
    account = users.create_user(
        email="doctor@portal.example.com",
        password_hash=hash_password("DoctorPass9"),
        role=provider_role,
        roles=[provider_role],
    )
    account.email_verified_at = datetime.now(timezone.utc)
    db.add(ProviderInvitation(
        provider_id=doctor.id,
        provider_type=ProviderType.DOCTOR,
        recipient_email=account.email,
        token_hash="doctor-completed-token",
        status=InvitationStatus.COMPLETED,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        sent_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        portal_user_id=account.id,
        created_by=admin.id,
    ))
    db.commit()
    token = _login(client, account.email, "DoctorPass9")
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["doctor_fields_available"] is True
    assert initial.json()["doctor_profile"]["professional_title"] == "DVM"

    updated = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={
            "professional_title": "Equine Surgeon",
            "biography": "Updated biography",
            "years_experience": 12,
            "qualifications": [{"title": "Equine Medicine", "institution": "Portal University"}],
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["doctor_profile"]["professional_title"] == "Equine Surgeon"
    assert body["qualifications"][0]["title"] == "Equine Medicine"