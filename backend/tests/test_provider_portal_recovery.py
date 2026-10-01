"""Secure password recovery for explicitly linked provider portal accounts."""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock
from urllib.parse import parse_qs, urlparse

from app.core.security import hash_password
from app.models.enums import (
    InvitationStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import (
    ProviderInvitation,
    ProviderPortalRecoveryToken,
)
from app.models.provider import DirectProviderPortalAccess, Provider, ProviderEmail
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.audit_repository import AuditContext
from app.repositories.user_repository import UserRepository
from app.services.direct_provider_access_service import DirectAccessError, DirectProviderAccessService
from app.services.email_service import EmailDeliveryError, EmailService


_ADMIN_PROVIDERS = "/api/v1/admin/providers"


def _provider_and_admin(client, db, seeded_admin, email: str):
    admin, admin_password = seeded_admin
    users = UserRepository(db)
    role = users.get_role_by_name("provider") or users.create_role(
        "provider", "Provider portal"
    )
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name="Recovery Clinic",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=PublicationStatus.PUBLISHED,
    )
    db.add(provider)
    db.flush()
    provider_email = ProviderEmail(
        provider_id=provider.id, email=email, is_primary=True
    )
    db.add(provider_email)
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin_password},
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_headers = {
        "Authorization": f"Bearer {admin_login.json()['access_token']}"
    }
    db.commit()
    return admin_headers, provider, provider_email, role


def _delivered_token(urls: list[str]) -> str:
    return parse_qs(urlparse(urls[-1]).query)["token"][0]


def _establish_direct_provider_account(
    client, db, seeded_admin, monkeypatch, email: str
):
    admin_headers, provider, provider_email, _role = _provider_and_admin(
        client, db, seeded_admin, email
    )
    setup_urls: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_access_email",
        lambda _self, _recipient, url, _expiry: setup_urls.append(url),
    )
    access = client.post(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access",
        headers=admin_headers,
        json={"email_id": str(provider_email.id)},
    )
    assert access.status_code == 200, access.text
    setup_token = _delivered_token(setup_urls)
    setup = client.post(
        "/api/v1/auth/provider-portal/setup-password",
        json={
            "token": setup_token,
            "password": "OriginalProviderPass9",
            "password_confirmation": "OriginalProviderPass9",
        },
    )
    assert setup.status_code == 200, setup.text
    access_row = db.get(DirectProviderPortalAccess, provider.id)
    account = db.get(User, access_row.user_id)
    return admin_headers, provider, provider_email, account


def test_provider_reset_is_hashed_single_use_and_revokes_refresh_sessions(
    client, db, seeded_admin, monkeypatch
):
    admin_headers, provider, _provider_email, account = _establish_direct_provider_account(
        client, db, seeded_admin, monkeypatch, "provider-reset@portal.example.com"
    )
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_recovery_email",
        lambda _self, _recipient, url, _expiry: delivered.append(url),
    )
    status = client.get(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access", headers=admin_headers
    )
    assert status.status_code == 200, status.text
    assert status.json()["action"] == "reset"
    assert status.json()["available"] is True
    assert status.json()["portal_login_email"] == account.email
    listed = client.get(
        f"{_ADMIN_PROVIDERS}?search=Recovery%20Clinic&page_size=100",
        headers=admin_headers,
    )
    assert listed.status_code == 200, listed.text
    list_item = next(
        item for item in listed.json()["data"] if item["id"] == str(provider.id)
    )
    assert list_item["portal_access_action"] == "reset"
    assert list_item["portal_login_email"] == account.email

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": account.email, "password": "OriginalProviderPass9"},
    )
    assert old_login.status_code == 200, old_login.text
    old_hash = account.password_hash
    sent = client.post(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access",
        headers=admin_headers,
        json={},
    )
    assert sent.status_code == 200, sent.text
    assert delivered and "/provider/reset-password?token=" in delivered[-1]
    raw_token = _delivered_token(delivered)
    token = db.query(ProviderPortalRecoveryToken).filter_by(
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest()
    ).one()
    assert token.user_id == account.id
    assert token.provider_id == provider.id
    assert raw_token not in token.token_hash
    db.refresh(account)
    assert account.password_hash == old_hash
    assert account.is_active is True

    # The link has not reset or disabled the account; existing credentials work
    # until the recipient redeems the purpose-specific token.
    assert client.post(
        "/api/v1/auth/login",
        json={"email": account.email, "password": "OriginalProviderPass9"},
    ).status_code == 200
    reset = client.post(
        "/api/v1/auth/provider-portal/reset-password",
        json={
            "token": raw_token,
            "password": "ReplacementProviderPass9",
            "password_confirmation": "ReplacementProviderPass9",
        },
    )
    assert reset.status_code == 200, reset.text
    db.refresh(token)
    assert token.used_at is not None
    db.refresh(account)
    assert account.is_active is True
    assert account.provider_portal_approval_pending is False
    assert db.query(RefreshToken).filter(
        RefreshToken.user_id == account.id,
        RefreshToken.revoked_at.is_(None),
    ).count() == 0
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": account.email, "password": "OriginalProviderPass9"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": account.email, "password": "ReplacementProviderPass9"},
    ).status_code == 200
    replay = client.post(
        "/api/v1/auth/provider-portal/reset-password",
        json={
            "token": raw_token,
            "password": "AnotherReplacementPass9",
            "password_confirmation": "AnotherReplacementPass9",
        },
    )
    assert replay.status_code == 409


def test_recovery_failure_preserves_old_password_and_allows_retry(
    client, db, seeded_admin, monkeypatch
):
    admin_headers, provider, provider_email, account = _establish_direct_provider_account(
        client, db, seeded_admin, monkeypatch, "provider-retry@portal.example.com"
    )
    original_hash = account.password_hash
    failed = []

    def smtp_failure(_self, *_args):
        failed.append(True)
        raise EmailDeliveryError("synthetic delivery failure")

    monkeypatch.setattr(EmailService, "send_provider_portal_recovery_email", smtp_failure)
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"
    failure = client.post(path, headers=admin_headers, json={})
    assert failure.status_code == 502
    assert failure.json()["detail"]["code"] == "portal_access_delivery_failed"
    db.refresh(account)
    assert account.password_hash == original_hash
    assert account.is_active is True
    failed_token = db.query(ProviderPortalRecoveryToken).filter_by(
        user_id=account.id
    ).one()
    assert failed_token.used_at is None
    assert failed_token.invalidated_at is None

    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_recovery_email",
        lambda _self, _recipient, url, _expiry: delivered.append(url),
    )
    retry = client.post(path, headers=admin_headers, json={})
    assert retry.status_code == 200, retry.text
    db.refresh(failed_token)
    assert failed_token.invalidated_at is not None
    assert delivered
    assert client.post(
        "/api/v1/auth/login",
        json={"email": account.email, "password": "OriginalProviderPass9"},
    ).status_code == 200


def test_recovery_cooldown_and_expiry_are_enforced(
    client, db, seeded_admin, monkeypatch
):
    admin_headers, provider, _provider_email, account = _establish_direct_provider_account(
        client, db, seeded_admin, monkeypatch, "provider-expiry@portal.example.com"
    )
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_recovery_email",
        lambda _self, _recipient, url, _expiry: delivered.append(url),
    )
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"
    sent = client.post(path, headers=admin_headers, json={})
    assert sent.status_code == 200, sent.text
    cooldown = client.post(path, headers=admin_headers, json={})
    assert cooldown.status_code == 409
    assert cooldown.json()["detail"]["code"] == "portal_access_cooldown"
    token = db.query(ProviderPortalRecoveryToken).filter_by(user_id=account.id).one()
    token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    raw = _delivered_token(delivered)
    expired = client.post(
        "/api/v1/auth/provider-portal/reset-password",
        json={
            "token": raw,
            "password": "ExpiredProviderPass9",
            "password_confirmation": "ExpiredProviderPass9",
        },
    )
    assert expired.status_code == 410


def test_invitation_owner_can_receive_reset_at_its_login_email(
    client, db, seeded_admin, monkeypatch
):
    admin, admin_password = seeded_admin
    users = UserRepository(db)
    provider_role = users.get_role_by_name("provider") or users.create_role(
        "provider", "Provider portal"
    )
    provider = Provider(
        provider_type=ProviderType.HOSPITAL,
        name="Invitation Recovery Hospital",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.UNDER_REVIEW,
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    db.add(provider)
    db.flush()
    account = users.create_user(
        email="invitation-login@portal.example.com",
        password_hash=hash_password("InvitationOriginalPass9"),
        role=provider_role,
        roles=[provider_role],
    )
    invitation = ProviderInvitation(
        provider_id=provider.id,
        provider_type=provider.provider_type,
        recipient_email=account.email,
        token_hash="invitation-recovery-token-hash",
        status=InvitationStatus.COMPLETED,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        sent_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        portal_user_id=account.id,
        created_by=admin.id,
    )
    db.add(invitation)
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin_password},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    delivered: list[tuple[str, str]] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_recovery_email",
        lambda _self, recipient, url, _expiry: delivered.append((recipient, url)),
    )

    portal_status = client.get(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access", headers=headers
    )
    assert portal_status.status_code == 200, portal_status.text
    assert portal_status.json()["action"] == "reset"
    assert portal_status.json()["portal_login_email"] == account.email
    sent = client.post(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access",
        headers=headers,
        json={},
    )
    assert sent.status_code == 200, sent.text
    assert delivered[0][0] == account.email


def test_unapproved_disabled_ambiguous_and_unauthorized_access_is_blocked(
    client, db, seeded_admin, monkeypatch
):
    admin_headers, provider, provider_email, account = _establish_direct_provider_account(
        client, db, seeded_admin, monkeypatch, "provider-boundary@portal.example.com"
    )
    path = f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access"
    assert client.get(path).status_code == 401
    assert client.post(path, json={}).status_code == 401

    account.provider_portal_approval_pending = True
    db.commit()
    pending = client.get(path, headers=admin_headers)
    assert pending.status_code == 200
    assert pending.json()["available"] is False
    assert pending.json()["action"] is None
    assert "approval" in pending.json()["reason"].lower()
    pending_login = client.post(
        "/api/v1/auth/login",
        json={"email": account.email, "password": "OriginalProviderPass9"},
    )
    assert pending_login.status_code == 403
    blocked_send = client.post(path, headers=admin_headers, json={})
    assert blocked_send.status_code == 409

    account.provider_portal_approval_pending = False
    account.is_active = False
    account.provider_portal_setup_pending = False
    db.commit()
    disabled = client.get(path, headers=admin_headers)
    assert disabled.json()["action"] is None
    assert "disabled" in disabled.json()["reason"].lower()

    account.is_active = True
    db.commit()
    provider_role = UserRepository(db).get_role_by_name("provider")
    other = UserRepository(db).create_user(
        email="ambiguous-owner@portal.example.com",
        password_hash=hash_password("AmbiguousOwnerPass9"),
        role=provider_role,
        roles=[provider_role],
    )
    db.add(
        ProviderInvitation(
            provider_id=provider.id,
            provider_type=provider.provider_type,
            recipient_email=other.email,
            token_hash="ambiguous-owner-invitation-token",
            status=InvitationStatus.COMPLETED,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            sent_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            portal_user_id=other.id,
            created_by=db.query(User).filter(User.role.has(name="admin")).first().id,
        )
    )
    db.commit()
    ambiguous = client.get(path, headers=admin_headers)
    assert ambiguous.status_code == 200
    assert ambiguous.json()["action"] is None
    assert "conflicting" in ambiguous.json()["reason"].lower()
    assert client.post(path, headers=admin_headers, json={}).status_code == 409


def test_recovery_redemption_is_atomic_under_concurrent_replay(
    client, db, seeded_admin, monkeypatch
):
    admin_headers, provider, _email, account = _establish_direct_provider_account(
        client, db, seeded_admin, monkeypatch, "provider-race@portal.example.com"
    )
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_portal_recovery_email",
        lambda _self, _recipient, url, _expiry: delivered.append(url),
    )
    sent = client.post(
        f"{_ADMIN_PROVIDERS}/{provider.id}/portal-access",
        headers=admin_headers,
        json={},
    )
    assert sent.status_code == 200, sent.text
    token = _delivered_token(delivered)

    from sqlalchemy.orm import sessionmaker

    from app.services.auth_service import AuthService
    from app.services.provider_portal_recovery_service import (
        ProviderPortalRecoveryTokenUsedError,
    )

    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    start_together = Barrier(2)

    def redeem():
        with sessions() as session:
            start_together.wait(timeout=10)
            try:
                AuthService(session).reset_provider_portal_password(
                    token, "ConcurrentNewPass9"
                )
                return 200
            except ProviderPortalRecoveryTokenUsedError:
                return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _n: redeem(), range(2)))
    assert sorted(statuses) == [200, 409]


def test_concurrent_reset_deliveries_are_cooldown_limited(
    client, db, seeded_admin, monkeypatch
):
    admin, _password = seeded_admin
    _admin_headers, provider, _email, _account = _establish_direct_provider_account(
        client, db, seeded_admin, monkeypatch, "provider-send-race@portal.example.com"
    )
    delivered: list[str] = []
    delivery_lock = Lock()

    def capture(_self, _recipient, url, _expires):
        with delivery_lock:
            delivered.append(url)

    monkeypatch.setattr(EmailService, "send_provider_portal_recovery_email", capture)
    from sqlalchemy.orm import sessionmaker

    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    start_together = Barrier(2)
    context = AuditContext(user_id=admin.id)

    def send():
        with sessions() as session:
            start_together.wait(timeout=10)
            try:
                DirectProviderAccessService(session).send(
                    provider.id, None, context=context
                )
                return "sent"
            except DirectAccessError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _n: send(), range(2)))
    assert sorted(results) == ["portal_access_cooldown", "sent"]
    assert len(delivered) == 1
