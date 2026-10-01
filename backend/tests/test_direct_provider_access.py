"""Direct administrator-created provider portal access integration tests."""
from __future__ import annotations

import hashlib
import pytest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock
from urllib.parse import parse_qs, urlparse

from app.core.security import hash_password
from app.models.enums import (
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import ProviderInvitation, ProviderPortalSetupToken
from app.models.provider import DirectProviderPortalAccess, Provider, ProviderEmail
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.user import User
from app.repositories.audit_repository import AuditContext
from app.repositories.user_repository import UserRepository
from app.services.direct_provider_access_service import DirectProviderAccessService
from app.services.email_service import EmailDeliveryError, EmailService
from sqlalchemy.orm import sessionmaker
from app.repositories.audit_repository import AuditRepository


_ADMIN_PROVIDERS = "/api/v1/admin/providers"


def _login(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _provider(db, *, name: str = "Direct Portal Clinic", old: bool = True) -> Provider:
    users = UserRepository(db)
    if users.get_role_by_name("provider") is None:
        users.create_role("provider", "Provider portal")
        db.commit()
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=PublicationStatus.PUBLISHED,
    )
    if old:
        provider.created_at = datetime.now(timezone.utc) - timedelta(days=365)
    db.add(provider)
    db.flush()
    return provider


def _email(db, provider: Provider, address: str, *, primary: bool = False) -> ProviderEmail:
    email = ProviderEmail(provider_id=provider.id, email=address, is_primary=primary)
    db.add(email)
    db.flush()
    return email


def _headers(client, admin) -> dict[str, str]:
    return {"Authorization": f"Bearer {_login(client, admin.email, 'TestAdmin#2026!')}"}


def _setup_token(delivered: list[str]) -> str:
    return parse_qs(urlparse(delivered[-1]).query)["token"][0]


def test_legacy_direct_provider_can_be_selected_and_receive_portal_access(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    provider = _provider(db)
    email = _email(db, provider, "legacy-direct@portal.example.com", primary=True)
    db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, setup_url, _expires: delivered.append(setup_url),
    )
    headers = _headers(client, admin)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"

    status = client.get(path, headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "eligible"
    assert any(
        item["email_id"] == str(email.id)
        for item in status.json()["selectable_emails"]
    )

    sent = client.post(path, headers=headers, json={"email_id": str(email.id)})
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "pending"
    token = _setup_token(delivered)
    direct_access = db.query(DirectProviderPortalAccess).filter_by(provider_id=provider.id).one()
    assert direct_access.recipient_email == email.email
    assert direct_access.sent_at is not None
    setup = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": token,
            "password": "DirectPortalPass9",
            "password_confirmation": "DirectPortalPass9",
        },
    )
    assert setup.status_code == 200, setup.text
    assert client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": token,
            "password": "DirectPortalPass9",
            "password_confirmation": "DirectPortalPass9",
        },
    ).status_code == 409

    active_status = client.get(path, headers=headers)
    assert active_status.status_code == 200, active_status.text
    assert active_status.json()["status"] == "active"

    portal_token = _login(client, email.email, "DirectPortalPass9")
    profile = client.get(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {portal_token}"},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["id"] == str(provider.id)


@pytest.mark.parametrize("failure", ["invalid", "expired", "replaced", "validation", "service"])
def test_setup_failures_leave_account_pending_and_token_unused(
    client, db, seeded_admin, monkeypatch, failure
):
    admin, _ = seeded_admin
    provider = _provider(db)
    email = _email(db, provider, "setup-recovery@portal.example.com")
    db.commit()
    delivered = []
    monkeypatch.setattr(
        EmailService, "send_provider_portal_access_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"
    headers = _headers(client, admin)
    assert client.post(path, headers=headers, json={"email_id": str(email.id)}).status_code == 200
    raw_token = _setup_token(delivered)
    token = db.query(ProviderPortalSetupToken).filter_by(
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest()
    ).one()
    account = db.get(User, token.user_id)
    old_hash = account.password_hash
    if failure == "expired":
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    if failure == "replaced":
        assert client.post(path, headers=headers, json={"email_id": str(email.id)}).status_code == 200
    password = "SyntheticSetup9"
    payload = {"token": raw_token, "password": password, "password_confirmation": password}
    if failure == "invalid":
        payload["token"] = "synthetic-unknown-token"
    if failure == "validation":
        payload["password_confirmation"] = "DifferentSetup9"
    original_log = AuditRepository.log
    if failure == "service":
        def unavailable(*_args, **_kwargs):
            raise RuntimeError("Synthetic audit outage")
        monkeypatch.setattr(AuditRepository, "log", unavailable)
    response = client.post("/api/v1/auth/provider-portal/setup-password", json=payload)
    expected = {
        "invalid": (404, "provider_portal_link_invalid"),
        "expired": (410, "provider_portal_link_expired"),
        "replaced": (409, "provider_portal_link_used"),
        "validation": (422, None),
        "service": (503, "provider_portal_setup_unavailable"),
    }[failure]
    assert response.status_code == expected[0]
    if expected[1]:
        assert response.json()["detail"]["code"] == expected[1]
    db.expire_all()
    assert token.used_at is None
    assert account.is_active is False
    assert account.provider_portal_setup_pending is True
    assert account.email_verified_at is None
    assert account.password_hash == old_hash
    if failure in ("validation", "service"):
        monkeypatch.setattr(AuditRepository, "log", original_log)
        payload["password_confirmation"] = password
        assert client.post("/api/v1/auth/provider-portal/setup-password", json=payload).status_code == 200
        assert _login(client, email.email, password)


def test_direct_access_rejects_email_owned_by_an_unrelated_account(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    provider = _provider(db)
    email = _email(db, provider, "already-used@portal.example.com")
    users = UserRepository(db)
    visitor = users.get_role_by_name("visitor") or users.create_role("visitor", "Visitor")
    users.create_user(
        email=email.email,
        password_hash=hash_password("VisitorPass9"),
        role=visitor,
        roles=[visitor],
    )
    db.commit()
    monkeypatch.setattr(EmailService, "send_provider_portal_access_email", lambda *_args: None)

    response = client.post(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access",
        headers=_headers(client, admin),
        json={"email_id": str(email.id)},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "portal_access_account_conflict"
    assert db.query(DirectProviderPortalAccess).filter_by(provider_id=provider.id).count() == 0


def test_invitation_and_registration_ownership_are_not_directly_reassigned(
    client, db, seeded_admin
):
    admin, _password = seeded_admin
    invitation_provider = _provider(db, name="Invited Provider")
    invitation_email = _email(db, invitation_provider, "invited-direct@portal.example.com")
    db.add(
        ProviderInvitation(
            provider_id=invitation_provider.id,
            provider_type=invitation_provider.provider_type,
            recipient_email=invitation_email.email,
            token_hash="direct-test-invitation-token",
            status=InvitationStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            sent_at=datetime.now(timezone.utc),
            created_by=admin.id,
        )
    )
    completed_provider = _provider(db, name="Completed Invitation Provider")
    completed_email = _email(db, completed_provider, "completed-direct@portal.example.com")
    db.add(
        ProviderInvitation(
            provider_id=completed_provider.id,
            provider_type=completed_provider.provider_type,
            recipient_email=completed_email.email,
            token_hash="completed-direct-test-token",
            status=InvitationStatus.COMPLETED,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            sent_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            created_by=admin.id,
        )
    )

    users = UserRepository(db)
    provider_role = users.get_role_by_name("provider") or users.create_role(
        "provider", "Provider portal"
    )
    registration_provider = _provider(db, name="Registered Provider")
    account = users.create_user(
        email="registered-direct@portal.example.com",
        password_hash=hash_password("RegisteredPass9"),
        role=provider_role,
        roles=[provider_role],
    )
    _email(db, registration_provider, account.email)
    db.add(
        ProviderRegistrationApplication(
            user_id=account.id,
            provider_id=registration_provider.id,
            provider_type=registration_provider.provider_type,
            provider_name=registration_provider.name,
            visit_stability=registration_provider.visit_stability,
            postal_code="12345",
            review_status=ProviderApplicationStatus.APPROVED,
        )
    )
    db.commit()
    headers = _headers(client, admin)

    invited_status = client.get(
        f"{_ADMIN_PROVIDERS}/{invitation_provider.id}/portal-access", headers=headers
    )
    registered_status = client.get(
        f"{_ADMIN_PROVIDERS}/{registration_provider.id}/portal-access", headers=headers
    )
    completed_status = client.get(
        f"{_ADMIN_PROVIDERS}/{completed_provider.id}/portal-access", headers=headers
    )
    assert invited_status.status_code == 200, invited_status.text
    assert invited_status.json()["status"] == "unavailable"
    assert registered_status.status_code == 200, registered_status.text
    assert registered_status.json()["status"] == "registration"
    assert completed_status.status_code == 200, completed_status.text
    assert completed_status.json()["status"] == "invitation"
    assert client.post(
        f"{_ADMIN_PROVIDERS}/{invitation_provider.id}/portal-access",
        headers=headers,
        json={"email_id": str(invitation_email.id)},
    ).status_code == 409
    assert client.post(
        f"{_ADMIN_PROVIDERS}/{registration_provider.id}/portal-access",
        headers=headers,
        json={"email_id": None},
    ).status_code == 409


def test_direct_access_requires_selectable_email_and_rejects_invalid_email_id(
    client, db, seeded_admin
):
    admin, _password = seeded_admin
    provider = _provider(db)
    newly_created_provider = _provider(db, name="New Direct Clinic", old=False)
    new_email = _email(db, newly_created_provider, "new-direct@portal.example.com")
    db.commit()
    headers = _headers(client, admin)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"
    new_status = client.get(
        f"{_ADMIN_PROVIDERS}/{newly_created_provider.id}/portal-access",
        headers=headers,
    )
    assert new_status.status_code == 200, new_status.text
    assert new_status.json()["status"] == "eligible"
    assert new_status.json()["selectable_emails"][0]["email_id"] == str(new_email.id)

    no_email = client.get(path, headers=headers)
    assert no_email.status_code == 200, no_email.text
    assert no_email.json()["status"] == "unavailable"
    assert no_email.json()["selectable_emails"] == []
    missing = client.post(path, headers=headers, json={"email_id": None})
    assert missing.status_code in (409, 422), missing.text

    email = _email(db, provider, "valid-direct@portal.example.com")
    db.commit()
    invalid = client.post(
        path,
        headers=headers,
        json={"email_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert invalid.status_code in (404, 409, 422), invalid.text
    assert db.query(DirectProviderPortalAccess).filter_by(provider_id=provider.id).count() == 0


def test_admin_created_provider_can_receive_access_after_creation(client, db, seeded_admin, monkeypatch):
    admin, _password = seeded_admin
    users = UserRepository(db)
    users.create_role("provider", "Provider portal")
    db.commit()
    headers = _headers(client, admin)
    created = client.post(
        _ADMIN_PROVIDERS, headers=headers,
        json={
            "provider_type": "CLINIC", "name": "Newly Created Clinic",
            "visit_stability": "STABLE_VISIT",
            "emails": [{"email": "new-clinic@portal.example.com", "is_primary": True}],
        },
    )
    assert created.status_code == 201, created.text
    provider_id = created.json()["id"]
    email_id = created.json()["emails"][0]["id"]
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService, "send_provider_portal_access_email",
        lambda _self, recipient, setup_url, _expiry: delivered.append(recipient),
    )
    sent = client.post(
        f"{_ADMIN_PROVIDERS}/{provider_id}/portal-access",
        headers=headers, json={"email_id": email_id},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["recipient_email"] == "new-clinic@portal.example.com"
    assert delivered == ["new-clinic@portal.example.com"]


def test_malformed_contact_email_cannot_receive_access(client, db, seeded_admin, monkeypatch):
    admin, _password = seeded_admin
    provider = _provider(db)
    invalid = _email(db, provider, "not-an-email")
    db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService, "send_provider_portal_access_email",
        lambda _self, recipient, _url, _expiry: delivered.append(recipient),
    )
    headers = _headers(client, admin)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"
    assert client.get(path, headers=headers).json()["selectable_emails"] == []
    assert client.post(path, headers=headers, json={"email_id": str(invalid.id)}).status_code == 409
    assert delivered == []


def test_removing_contact_revokes_link_and_admin_can_correct_recipient(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    provider = _provider(db)
    wrong = _email(db, provider, "wrong-recipient@portal.example.com")
    right = _email(db, provider, "correct-recipient@portal.example.com")
    db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService, "send_provider_portal_access_email",
        lambda _self, _recipient, url, _expiry: delivered.append(url),
    )
    headers = _headers(client, admin)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}"
    assert client.post(f"{path}/portal-access", headers=headers, json={"email_id": str(wrong.id)}).status_code == 200
    old_token = _setup_token(delivered)

    removed = client.delete(f"{path}/emails/{wrong.id}", headers=headers)
    assert removed.status_code == 204, removed.text
    assert client.get(f"{path}/portal-access", headers=headers).json()["can_revoke"] is True
    rejected = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={"token": old_token, "password": "CorrectPass9", "password_confirmation": "CorrectPass9"},
    )
    assert rejected.status_code == 409
    assert client.post(f"{path}/portal-access", headers=headers, json={"email_id": str(right.id)}).status_code == 409
    cancelled = client.post(f"{path}/portal-access/revoke", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "eligible"
    assert UserRepository(db).get_by_email("wrong-recipient@portal.example.com") is None
    corrected = client.post(f"{path}/portal-access", headers=headers, json={"email_id": str(right.id)})
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["recipient_email"] == right.email
    assert client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={"token": old_token, "password": "CorrectPass9", "password_confirmation": "CorrectPass9"},
    ).status_code in (404, 409)


def test_changing_legacy_contact_revokes_old_direct_link(client, db, seeded_admin, monkeypatch):
    admin, _password = seeded_admin
    provider = _provider(db)
    provider.email = "old-legacy@portal.example.com"
    db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService, "send_provider_portal_access_email",
        lambda _self, _recipient, url, _expiry: delivered.append(url),
    )
    headers = _headers(client, admin)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}"
    assert client.post(f"{path}/portal-access", headers=headers, json={"email_id": None}).status_code == 200
    old_token = _setup_token(delivered)
    changed = client.patch(path, headers=headers, json={"email": "corrected-legacy@portal.example.com"})
    assert changed.status_code == 200, changed.text
    assert client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={"token": old_token, "password": "CorrectPass9", "password_confirmation": "CorrectPass9"},
    ).status_code == 409


def test_resend_replaces_setup_token_and_expired_or_used_links_cannot_be_reused(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    provider = _provider(db)
    email = _email(db, provider, "resend-direct@portal.example.com")
    db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, setup_url, _expires: delivered.append(setup_url),
    )
    headers = _headers(client, admin)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"
    assert client.post(path, headers=headers, json={"email_id": str(email.id)}).status_code == 200
    first_token = _setup_token(delivered)
    other_email = _email(db, provider, "different-contact@portal.example.com")
    db.commit()
    restricted = client.get(path, headers=headers).json()
    assert [item["email"] for item in restricted["selectable_emails"]] == [email.email]
    assert client.post(path, headers=headers, json={"email_id": str(other_email.id)}).status_code == 409
    assert client.post(path, headers=headers, json={"email_id": str(email.id)}).status_code == 200
    second_token = _setup_token(delivered)
    assert second_token != first_token

    stale = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": first_token,
            "password": "DirectPortalPass9",
            "password_confirmation": "DirectPortalPass9",
        },
    )
    assert stale.status_code == 409

    current = (
        db.query(ProviderPortalSetupToken)
        .filter(ProviderPortalSetupToken.direct_provider_id == provider.id)
        .filter(ProviderPortalSetupToken.used_at.is_(None))
        .filter(ProviderPortalSetupToken.invalidated_at.is_(None))
        .one()
    )
    current.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    expired = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": second_token,
            "password": "DirectPortalPass9",
            "password_confirmation": "DirectPortalPass9",
        },
    )
    assert expired.status_code in (400, 409, 410), expired.text


def test_direct_portal_smtp_failure_leaves_retry_possible(client, db, seeded_admin, monkeypatch):
    admin, _password = seeded_admin
    provider = _provider(db)
    email = _email(db, provider, "retry-direct@portal.example.com")
    db.commit()
    headers = _headers(client, admin)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"

    def fail_delivery(*_args, **_kwargs):
        raise EmailDeliveryError("SMTP temporarily unavailable")

    monkeypatch.setattr(EmailService, "send_provider_portal_access_email", fail_delivery)
    failed = client.post(path, headers=headers, json={"email_id": str(email.id)})
    assert failed.status_code == 502, failed.text
    assert db.query(DirectProviderPortalAccess).filter_by(provider_id=provider.id).count() == 1
    failed_status = client.get(path, headers=headers).json()
    assert failed_status["status"] == "pending"
    assert "failed to send" in failed_status["message"]

    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, setup_url, _expires: delivered.append(setup_url),
    )
    retry = client.post(path, headers=headers, json={"email_id": str(email.id)})
    assert retry.status_code == 200, retry.text
    assert delivered


def test_disabled_direct_pending_user_cannot_resend_or_redeem(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    provider = _provider(db)
    email = _email(db, provider, "disabled-direct@portal.example.com")
    db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, setup_url, _expires: delivered.append(setup_url),
    )
    headers = _headers(client, admin)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"
    sent = client.post(path, headers=headers, json={"email_id": str(email.id)})
    assert sent.status_code == 200, sent.text
    old_token = _setup_token(delivered)

    access = db.query(DirectProviderPortalAccess).filter_by(provider_id=provider.id).one()
    account = db.get(User, access.user_id)
    assert account is not None and account.provider_portal_setup_pending is True
    # Simulate disabling an account after a pending setup has been activated.
    # The deactivation hook clears pending setup and revokes outstanding links.
    account.is_active = True
    db.commit()
    account.is_active = False
    db.commit()
    db.refresh(account)
    assert account.provider_portal_setup_pending is False

    resend = client.post(path, headers=headers, json={"email_id": str(email.id)})
    assert resend.status_code == 409, resend.text
    assert client.get(path, headers=headers).json()["can_revoke"] is False
    assert client.post(f"{path}/revoke", headers=headers).status_code == 409
    redeem = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": old_token,
            "password": "DirectPortalPass9",
            "password_confirmation": "DirectPortalPass9",
        },
    )
    assert redeem.status_code == 409, redeem.text
    assert account.is_active is False


def test_concurrent_direct_sends_keep_one_account_and_only_latest_token_valid(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    provider = _provider(db)
    email = _email(db, provider, "concurrent-direct@portal.example.com")
    db.commit()

    delivered: list[str] = []
    delivered_lock = Lock()

    def capture_delivery(_self, _recipient, setup_url, _expires):
        with delivered_lock:
            delivered.append(setup_url)

    monkeypatch.setattr(EmailService, "send_provider_portal_access_email", capture_delivery)
    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    start_together = Barrier(2)
    context = AuditContext(user_id=admin.id)

    def send_from_independent_session():
        with sessions() as session:
            start_together.wait(timeout=10)
            return DirectProviderAccessService(session).send(
                provider.id, email.id, context=context
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: send_from_independent_session(), range(2)))

    assert [result["status"] for result in results] == ["pending", "pending"]
    assert len(delivered) == 2
    sent_tokens = [_setup_token([url]) for url in delivered]
    assert len(set(sent_tokens)) == 2

    db.expire_all()
    access_rows = (
        db.query(DirectProviderPortalAccess)
        .filter(DirectProviderPortalAccess.provider_id == provider.id)
        .all()
    )
    assert len(access_rows) == 1
    access = access_rows[0]
    assert db.query(User).filter(User.email == email.email).count() == 1
    account = db.get(User, access.user_id)
    assert account is not None and account.provider_portal_setup_pending is True

    token_rows = (
        db.query(ProviderPortalSetupToken)
        .filter(ProviderPortalSetupToken.direct_provider_id == provider.id)
        .all()
    )
    assert len(token_rows) == 2
    usable = [
        token
        for token in token_rows
        if token.invalidated_at is None and token.used_at is None
    ]
    assert len(usable) == 1
    assert usable[0].token_hash in {
        hashlib.sha256(token.encode()).hexdigest() for token in sent_tokens
    }
    usable_token = next(
        token
        for token in sent_tokens
        if hashlib.sha256(token.encode()).hexdigest() == usable[0].token_hash
    )
    replaced_token = next(token for token in sent_tokens if token != usable_token)

    replaced = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": replaced_token,
            "password": "DirectPortalPass9",
            "password_confirmation": "DirectPortalPass9",
        },
    )
    assert replaced.status_code == 409, replaced.text
    redeemed = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": usable_token,
            "password": "DirectPortalPass9",
            "password_confirmation": "DirectPortalPass9",
        },
    )
    assert redeemed.status_code == 200, redeemed.text


def test_completed_invitation_portal_access_still_works_and_direct_status_identifies_it(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    provider = _provider(db, name="Completed Invitation Portal Clinic")
    invitation = ProviderInvitation(
        provider_id=provider.id,
        provider_type=provider.provider_type,
        recipient_email="completed-portal@portal.example.com",
        token_hash="completed-direct-setup-test-token",
        status=InvitationStatus.COMPLETED,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        sent_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        created_by=admin.id,
    )
    db.add(invitation)
    db.commit()

    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, setup_url, _expires: delivered.append(setup_url),
    )
    headers = _headers(client, admin)
    sent = client.post(
        f"/api/v1/admin/invitations/{invitation.id}/portal-access",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    token = _setup_token(delivered)

    direct_status = client.get(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access",
        headers=headers,
    )
    assert direct_status.status_code == 200, direct_status.text
    assert direct_status.json()["status"] == "invitation"
    assert direct_status.json()["invitation_id"] == str(invitation.id)
    assert direct_status.json()["selectable_emails"] == []

    setup = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": token,
            "password": "InvitationPortalPass9",
            "password_confirmation": "InvitationPortalPass9",
        },
    )
    assert setup.status_code == 200, setup.text
    provider_token = _login(
        client, invitation.recipient_email, "InvitationPortalPass9"
    )
    profile = client.get(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {provider_token}"},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["id"] == str(provider.id)


def test_direct_provider_portal_is_exclusive_to_its_owner_and_admin_route_requires_admin(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    provider = _provider(db)
    email = _email(db, provider, "owner-direct@portal.example.com")
    other_provider = _provider(db, name="Other Direct Clinic")
    _email(db, other_provider, "other-direct@portal.example.com")
    db.commit()
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, setup_url, _expires: delivered.append(setup_url),
    )
    admin_headers = _headers(client, admin)
    assert client.post(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access",
        headers=admin_headers,
        json={"email_id": str(email.id)},
    ).status_code == 200
    token = _setup_token(delivered)
    assert client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": token,
            "password": "DirectPortalPass9",
            "password_confirmation": "DirectPortalPass9",
        },
    ).status_code == 200
    owner_token = _login(client, email.email, "DirectPortalPass9")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    assert client.get(
        "/api/v1/provider/portal/profile", headers=owner_headers
    ).json()["id"] == str(provider.id)

    status = client.get(
        f"{_ADMIN_PROVIDERS}/{other_provider.id}/portal-access",
        headers=owner_headers,
    )
    assert status.status_code == 403