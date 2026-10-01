"""Member-only password recovery boundary and redemption tests."""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock
from urllib.parse import urlparse

from app.core.security import hash_password
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import (
    EmailDeliveryStatus,
    EmailPurpose,
    InvitationStatus,
    ProviderType,
)
from app.models.invitation import ProviderInvitation
from app.models.member_recovery_token import MemberPasswordRecoveryToken
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailDeliveryError, EmailService


_REQUEST = "/api/v1/auth/member-password-recovery/request"
_REQUEST_CURRENT = "/api/v1/auth/member-password-recovery/request-current"
_RESET = "/api/v1/auth/member-password-recovery/reset"


def _create_user(db, email: str, roles: list[str], *, verified=True, active=True):
    repository = UserRepository(db)
    role_models = []
    for role_name in roles:
        role = repository.get_role_by_name(role_name)
        if role is None:
            role = repository.create_role(role_name, role_name.replace("_", " ").title())
        role_models.append(role)
    user = repository.create_user(
        email=email,
        password_hash=hash_password("OriginalMemberPass9"),
        role=role_models[0],
        roles=role_models,
        first_name="Member",
        last_name="Rider",
        is_active=active,
    )
    if verified:
        user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return user


def _raw_token(url: str) -> str:
    assert urlparse(url).path == "/reset-password"
    assert not urlparse(url).query
    return urlparse(url).fragment.removeprefix("token=")


def _login_headers(client, user: User):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "OriginalMemberPass9"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_anonymous_request_is_uniform_and_delivers_hashed_fragment_link(
    client, db, monkeypatch
):
    member = _create_user(db, "Member.Reset@Example.com", ["horse_owner"])
    delivered: list[tuple[str, str]] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, recipient, url, _expires: delivered.append((recipient, url)),
    )

    known = client.post(_REQUEST, json={"email": "MEMBER.RESET@example.com"})
    unknown = client.post(_REQUEST, json={"email": "missing@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert known.json()["message"].startswith("If an eligible member account")
    assert delivered == [("member.reset@example.com", delivered[0][1])]
    assert "/reset-password#token=" in delivered[0][1]

    raw = _raw_token(delivered[0][1])
    token = db.query(MemberPasswordRecoveryToken).filter_by(user_id=member.id).one()
    assert token.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in token.token_hash
    attempt = db.query(EmailDeliveryLog).filter_by(
        purpose=EmailPurpose.MEMBER_PASSWORD_RECOVERY.value
    ).one()
    assert attempt.status == EmailDeliveryStatus.SUCCESS.value
    assert attempt.recipient_email == member.email


def test_current_member_request_uses_session_email_and_enforces_cooldown(
    client, db, monkeypatch
):
    member = _create_user(db, "self-service@example.com", ["stable_manager"])
    headers = _login_headers(client, member)
    delivered: list[tuple[str, str]] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, recipient, url, _expires: delivered.append((recipient, url)),
    )

    sent = client.post(_REQUEST_CURRENT, headers=headers, json={"email": "other@example.com"})
    assert sent.status_code == 200, sent.text
    assert delivered[0][0] == member.email
    assert "/reset-password#token=" in delivered[0][1]
    limited = client.post(_REQUEST_CURRENT, headers=headers)
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "member_recovery_cooldown"
    assert len(delivered) == 1


def test_unknown_ineligible_and_cooldown_requests_are_opaque(
    client, db, monkeypatch
):
    _create_user(db, "unverified@example.com", ["horse_owner"], verified=False)
    _create_user(db, "disabled@example.com", ["stable_manager"], active=False)
    _create_user(db, "admin-role@example.com", ["admin"])
    _create_user(db, "provider-role@example.com", ["provider"])
    _create_user(db, "mixed-role@example.com", ["horse_owner", "provider"])
    provider_linked = _create_user(db, "provider-linked-member@example.com", ["horse_owner"])
    creator = _create_user(db, "invitation-creator@example.com", ["admin"])
    db.add(
        ProviderInvitation(
            provider_id=None,
            provider_type=ProviderType.CLINIC,
            recipient_email=provider_linked.email,
            token_hash="linked-provider-invitation-token-hash",
            status=InvitationStatus.COMPLETED,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            sent_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            portal_user_id=provider_linked.id,
            created_by=creator.id,
        )
    )
    db.commit()
    successful = _create_user(db, "opaque@example.com", ["horse_owner"])
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )

    first = client.post(_REQUEST, json={"email": successful.email})
    assert first.status_code == 200
    assert len(delivered) == 1
    for email in (
        "unknown@example.com",
        "unverified@example.com",
        "disabled@example.com",
        "admin-role@example.com",
        "provider-role@example.com",
        "mixed-role@example.com",
        "provider-linked-member@example.com",
        successful.email,
    ):
        response = client.post(_REQUEST, json={"email": email})
        assert response.status_code == first.status_code
        assert response.json() == first.json()
    assert len(delivered) == 1
    assert db.query(MemberPasswordRecoveryToken).count() == 1


def test_current_recovery_reads_role_assignments_again_under_lock(db, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from app.services.member_password_recovery_service import (
        MemberPasswordRecoveryService,
        MemberPasswordRecoveryUnavailableError,
    )

    member = _create_user(db, "fresh-role-member@example.com", ["horse_owner"])
    # Prime the identity map with a member-only assignment collection.
    assert [assignment.role.name for assignment in UserRepository(db).get_by_id(member.id).role_assignments] == [
        "horse_owner"
    ]
    provider_role = UserRepository(db).get_role_by_name("provider")
    if provider_role is None:
        provider_role = UserRepository(db).create_role("provider", "Provider")
        db.commit()
    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    with sessions() as another_session:
        another_session.add(UserRole(user_id=member.id, role_id=provider_role.id))
        another_session.commit()

    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not deliver")),
    )
    try:
        MemberPasswordRecoveryService(db).request_for_current_member(member.id)
    except MemberPasswordRecoveryUnavailableError:
        pass
    else:
        raise AssertionError("fresh provider assignment should disqualify member recovery")


def test_password_reset_is_atomic_single_use_and_revokes_refresh_sessions(
    client, db, monkeypatch
):
    member = _create_user(db, "redeem-member@example.com", ["horse_owner", "stable_manager"])
    original_role_id = member.role_id
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )
    assert client.post(_REQUEST, json={"email": member.email}).status_code == 200
    raw = _raw_token(delivered[0])
    original_verified_at = member.email_verified_at

    login_headers = _login_headers(client, member)
    replacement = "ChangedMemberPassword9"
    reset = client.post(
        _RESET,
        json={
            "token": raw,
            "password": replacement,
            "password_confirmation": replacement,
        },
    )
    assert reset.status_code == 200, reset.text
    assert "Sign in" in reset.json()["message"]
    token = db.query(MemberPasswordRecoveryToken).one()
    db.refresh(token)
    assert token.used_at is not None
    db.refresh(member)
    assert member.role_id == original_role_id
    assert member.email_verified_at == original_verified_at
    assert member.is_active is True
    assert db.query(RefreshToken).filter(
        RefreshToken.user_id == member.id,
        RefreshToken.revoked_at.is_(None),
    ).count() == 0
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": "OriginalMemberPass9"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": replacement},
    ).status_code == 200
    replay = client.post(
        _RESET,
        json={
            "token": raw,
            "password": "AnotherMemberPassword9",
            "password_confirmation": "AnotherMemberPassword9",
        },
    )
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "member_recovery_link_used"
    assert login_headers["Authorization"]


def test_reset_reports_expired_invalid_and_policy_errors(client, db, monkeypatch):
    member = _create_user(db, "expired-member@example.com", ["horse_owner"])
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )
    client.post(_REQUEST, json={"email": member.email})
    expired_token = db.query(MemberPasswordRecoveryToken).one()
    expired_token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    payload = {
        "token": _raw_token(delivered[0]),
        "password": "ReplacementMemberPass9",
        "password_confirmation": "ReplacementMemberPass9",
    }
    expired = client.post(_RESET, json=payload)
    assert expired.status_code == 410
    assert expired.json()["detail"]["code"] == "member_recovery_link_expired"
    payload["token"] = "a" * 48
    assert client.post(_RESET, json=payload).json()["detail"]["code"] == "member_recovery_link_invalid"
    payload["password"] = payload["password_confirmation"] = "lowercasepassword9"
    assert client.post(_RESET, json=payload).status_code == 422


def test_failed_replacement_delivery_preserves_previous_delivered_link(
    client, db, monkeypatch
):
    member = _create_user(db, "preserved-link@example.com", ["horse_owner"])
    headers = _login_headers(client, member)
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )
    assert client.post(_REQUEST, json={"email": member.email}).status_code == 200
    original = db.query(MemberPasswordRecoveryToken).one()
    original_raw = _raw_token(delivered[0])
    monkeypatch.setattr(
        "app.services.member_password_recovery_service.MEMBER_RECOVERY_COOLDOWN",
        timedelta(0),
    )

    def fail_delivery(_self, *_args):
        raise EmailDeliveryError("synthetic SMTP failure")

    monkeypatch.setattr(EmailService, "send_member_password_recovery_email", fail_delivery)
    failed = client.post(_REQUEST_CURRENT, headers=headers)
    assert failed.status_code == 503
    db.refresh(original)
    assert original.invalidated_at is None
    assert original.used_at is None
    assert db.query(MemberPasswordRecoveryToken).count() == 1

    reset = client.post(
        _RESET,
        json={
            "token": original_raw,
            "password": "RecoveredMemberPassword9",
            "password_confirmation": "RecoveredMemberPassword9",
        },
    )
    assert reset.status_code == 200, reset.text


def test_competing_recovery_redemptions_have_one_winner(
    client, db, monkeypatch
):
    member = _create_user(db, "competing-member@example.com", ["horse_owner"])
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )
    client.post(_REQUEST, json={"email": member.email})
    raw = _raw_token(delivered[0])

    from sqlalchemy.orm import sessionmaker

    from app.services.member_password_recovery_service import (
        MemberPasswordRecoveryService,
        MemberPasswordRecoveryTokenUsedError,
    )

    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    start_together = Barrier(2)

    def redeem():
        with sessions() as session:
            start_together.wait(timeout=10)
            try:
                MemberPasswordRecoveryService(session).redeem(
                    raw, "ConcurrentMemberPassword9"
                )
                return 200
            except MemberPasswordRecoveryTokenUsedError:
                return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _n: redeem(), range(2)))
    assert sorted(statuses) == [200, 409]


def test_refresh_racing_password_reset_cannot_leave_a_new_session(
    client, db, monkeypatch
):
    member = _create_user(db, "refresh-reset-race@example.com", ["horse_owner"])
    _login_headers(client, member)
    old_refresh_token = client.cookies.get("refresh_token")
    assert old_refresh_token
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )
    client.post(_REQUEST, json={"email": member.email})
    raw_recovery_token = _raw_token(delivered[0])

    from sqlalchemy.orm import sessionmaker

    from app.services.auth_service import AuthService, InvalidTokenError
    from app.services.member_password_recovery_service import MemberPasswordRecoveryService

    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    start_together = Barrier(2)

    def refresh():
        with sessions() as session:
            start_together.wait(timeout=10)
            try:
                pair = AuthService(session).refresh(old_refresh_token)
                return pair.refresh_token
            except InvalidTokenError:
                return None

    def reset():
        with sessions() as session:
            start_together.wait(timeout=10)
            MemberPasswordRecoveryService(session).redeem(
                raw_recovery_token, "RacedMemberPassword9"
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        refresh_job = pool.submit(refresh)
        reset_job = pool.submit(reset)
        rotated_refresh = refresh_job.result()
        reset_job.result()

    assert db.query(RefreshToken).filter(
        RefreshToken.user_id == member.id,
        RefreshToken.revoked_at.is_(None),
    ).count() == 0
    if rotated_refresh:
        rotated_hash = hashlib.sha256(rotated_refresh.encode()).hexdigest()
        rotated_record = db.query(RefreshToken).filter_by(token_hash=rotated_hash).one()
        assert rotated_record.revoked_at is not None


def test_member_password_recovery_limits_requests_per_ip(client):
    from app.core.rate_limit import (
        check_member_password_recovery_rate_limit,
        _member_password_recovery_attempts,
    )
    from app.main import app

    app.dependency_overrides.pop(check_member_password_recovery_rate_limit, None)
    _member_password_recovery_attempts.clear()
    responses = [
        client.post(_REQUEST, json={"email": "not-a-member@example.com"})
        for _ in range(6)
    ]
    assert [response.status_code for response in responses[:5]] == [200] * 5
    assert responses[5].status_code == 429
    assert responses[5].json()["detail"]["code"] == "rate_limited"


def test_login_cannot_use_a_stale_password_after_recovery(client, db, monkeypatch):
    """A long-lived Session must reread the password before issuing a session."""
    from sqlalchemy.orm import sessionmaker
    from app.services.auth_service import AuthService, AuthenticationError
    from app.services.member_password_recovery_service import MemberPasswordRecoveryService

    member = _create_user(db, "stale-login@example.com", ["horse_owner"])
    delivered = []
    monkeypatch.setattr(
        EmailService, "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expiry: delivered.append(url),
    )
    client.post(_REQUEST, json={"email": member.email})
    # Hold a stale loaded object while another transaction commits recovery.
    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    with sessions() as stale, sessions() as recovery:
        stale_member = UserRepository(stale).get_by_email(member.email)
        MemberPasswordRecoveryService(recovery).redeem(
            _raw_token(delivered[0]), "NewRecoveredPassword9"
        )
        assert stale_member.password_hash != UserRepository(recovery).get_by_email(member.email).password_hash
        try:
            AuthService(stale).login(member.email, "OriginalMemberPass9")
        except AuthenticationError:
            pass
        else:
            raise AssertionError("A stale password must not create a post-reset session")
    assert db.query(RefreshToken).filter(
        RefreshToken.user_id == member.id, RefreshToken.revoked_at.is_(None)
    ).count() == 0


def test_member_recovery_rejects_mismatched_and_oversized_passwords(client):
    for password, confirmation in (
        ("SecureHorse7", "DifferentHorse7"),
        ("Aa1" + "x" * 126, "Aa1" + "x" * 126),
    ):
        rejected = client.post(_RESET, json={
            "token": "fake-token-never-issued",
            "password": password,
            "password_confirmation": confirmation,
        })
        assert rejected.status_code == 422


def test_disabled_member_cannot_redeem_an_existing_link(client, db, monkeypatch):
    from app.core.security import verify_password
    member = _create_user(db, "disabled-after-issuance@example.com", ["horse_owner"])
    delivered = []
    monkeypatch.setattr(
        EmailService, "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expiry: delivered.append(url),
    )
    client.post(_REQUEST, json={"email": member.email})
    member.is_active = False
    db.commit()
    rejected = client.post(_RESET, json={
        "token": _raw_token(delivered[0]),
        "password": "ReplacementMember9",
        "password_confirmation": "ReplacementMember9",
    })
    assert rejected.status_code == 409
    db.refresh(member)
    assert not member.is_active
    assert verify_password("OriginalMemberPass9", member.password_hash)
    assert db.query(MemberPasswordRecoveryToken).filter_by(user_id=member.id).one().used_at is None


def test_anonymous_smtp_failure_keeps_same_public_ack_and_records_failure(
    client, db, monkeypatch
):
    from app.services.member_password_recovery_service import (
        MEMBER_PASSWORD_RECOVERY_ACKNOWLEDGEMENT,
    )

    _create_user(db, "failed-delivery@example.com", ["horse_owner"])

    def fail_delivery(_self, *_args):
        raise EmailDeliveryError("sensitive smtp credential should not reach logs")

    monkeypatch.setattr(EmailService, "send_member_password_recovery_email", fail_delivery)

    known = client.post(_REQUEST, json={"email": "failed-delivery@example.com"})
    unknown = client.post(_REQUEST, json={"email": "no-account@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {
        "message": MEMBER_PASSWORD_RECOVERY_ACKNOWLEDGEMENT,
    }
    attempt = db.query(EmailDeliveryLog).filter_by(
        purpose=EmailPurpose.MEMBER_PASSWORD_RECOVERY.value,
        recipient_email="failed-delivery@example.com",
    ).one()
    assert attempt.status == EmailDeliveryStatus.FAILED.value
    assert "credential" not in (attempt.failure_message or "").lower()
    assert db.query(MemberPasswordRecoveryToken).count() == 0


def test_concurrent_anonymous_requests_send_only_one_link_and_preserve_latest(
    db, monkeypatch
):
    from sqlalchemy.orm import sessionmaker

    from app.services.member_password_recovery_service import (
        MemberPasswordRecoveryService,
    )

    member = _create_user(db, "concurrent-request@example.com", ["horse_owner"])
    member_email = member.email
    delivered: list[str] = []
    delivery_lock = Lock()
    start_together = Barrier(2)

    def record_delivery(_self, _recipient, url, _expires):
        with delivery_lock:
            delivered.append(url)

    monkeypatch.setattr(
        EmailService, "send_member_password_recovery_email", record_delivery
    )
    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)

    def request():
        with sessions() as session:
            start_together.wait(timeout=10)
            return MemberPasswordRecoveryService(session).request_for_email(member_email)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: request(), range(2)))

    assert sorted(results) == [False, True]
    assert len(delivered) == 1
    token = db.query(MemberPasswordRecoveryToken).filter_by(user_id=member.id).one()
    assert token.invalidated_at is None
    assert token.used_at is None
    assert db.query(EmailDeliveryLog).filter_by(
        purpose=EmailPurpose.MEMBER_PASSWORD_RECOVERY.value,
        status=EmailDeliveryStatus.SUCCESS.value,
    ).count() == 1


def test_successful_reissue_invalidates_previous_delivered_link(
    client, db, monkeypatch
):
    member = _create_user(db, "rotated-link@example.com", ["horse_owner"])
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )
    assert client.post(_REQUEST, json={"email": member.email}).status_code == 200
    first_raw = _raw_token(delivered[0])
    first_token = db.query(MemberPasswordRecoveryToken).one()
    monkeypatch.setattr(
        "app.services.member_password_recovery_service.MEMBER_RECOVERY_COOLDOWN",
        timedelta(0),
    )

    assert client.post(_REQUEST, json={"email": member.email}).status_code == 200

    assert len(delivered) == 2
    db.refresh(first_token)
    assert first_token.invalidated_at is not None
    assert first_token.used_at is None
    assert db.query(MemberPasswordRecoveryToken).filter_by(user_id=member.id).count() == 2
    invalidated = client.post(
        _RESET,
        json={
            "token": first_raw,
            "password": "ReplacementMemberPassword9",
            "password_confirmation": "ReplacementMemberPassword9",
        },
    )
    assert invalidated.status_code == 409
    assert invalidated.json()["detail"]["code"] == "member_recovery_link_used"
    assert client.post(
        _RESET,
        json={
            "token": _raw_token(delivered[1]),
            "password": "ReplacementMemberPassword9",
            "password_confirmation": "ReplacementMemberPassword9",
        },
    ).status_code == 200


def test_revoked_or_newly_privileged_accounts_cannot_redeem_member_links(
    client, db, monkeypatch
):
    member = _create_user(db, "revoked-link@example.com", ["horse_owner"])
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, _recipient, url, _expires: delivered.append(url),
    )
    assert client.post(_REQUEST, json={"email": member.email}).status_code == 200
    raw = _raw_token(delivered[0])
    provider_role = UserRepository(db).get_role_by_name("provider")
    if provider_role is None:
        provider_role = UserRepository(db).create_role("provider", "Provider")
    db.add(UserRole(user_id=member.id, role_id=provider_role.id))
    db.commit()

    rejected = client.post(
        _RESET,
        json={
            "token": raw,
            "password": "ReplacementMemberPassword9",
            "password_confirmation": "ReplacementMemberPassword9",
        },
    )

    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "member_recovery_link_used"
    assert client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": "OriginalMemberPass9"},
    ).status_code == 200
    assert db.query(MemberPasswordRecoveryToken).filter_by(user_id=member.id).one().used_at is None


def test_current_recovery_rejects_anonymous_and_provider_accounts(
    client, db, monkeypatch
):
    member = _create_user(db, "mixed-recovery@example.com", ["horse_owner"])
    provider_role = UserRepository(db).get_role_by_name("provider")
    if provider_role is None:
        provider_role = UserRepository(db).create_role("provider", "Provider")
    db.add(UserRole(user_id=member.id, role_id=provider_role.id))
    db.commit()
    sends: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_member_password_recovery_email",
        lambda _self, recipient, _url, _expires: sends.append(recipient),
    )

    anonymous = client.post(_REQUEST_CURRENT)
    headers = _login_headers(client, member)
    provider_response = client.post(_REQUEST_CURRENT, headers=headers)

    assert anonymous.status_code == 401
    assert provider_response.status_code == 403
    assert provider_response.json()["detail"]["code"] == "member_recovery_unavailable"
    assert sends == []
    assert db.query(MemberPasswordRecoveryToken).count() == 0