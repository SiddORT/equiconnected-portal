"""Security boundaries and persistence behavior for private provider messaging."""
import base64
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.core.security import create_access_token
from app.models.enums import (
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.messaging import (
    MessagingNotificationOutbox,
    ProviderConversation,
    ProviderMessage,
)
from app.models.provider import DirectProviderPortalAccess, Provider
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.role import Role
from app.models.user import User, UserRole


BASE = "/api/v1/messages"


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _user(db, *, email: str, role_name: str, roles: list[str] | None = None) -> User:
    names = list(dict.fromkeys([role_name, *(roles or [])]))
    role_rows = {}
    for name in names:
        role = db.query(Role).filter(Role.name == name).one_or_none()
        if role is None:
            role = Role(name=name, description=name)
            db.add(role)
            db.flush()
        role_rows[name] = role
    user = User(
        email=email,
        password_hash="not-used",
        role=role_rows[role_name],
        first_name=email.split("@")[0].title(),
        last_name="Example",
        mobile_number="+1 555 0100",
        email_verified_at=datetime.now(timezone.utc),
        is_active=True,
    )
    db.add(user)
    db.flush()
    for role in role_rows.values():
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()
    return user


def _provider_pair(
    db,
    *,
    name: str = "Messaging Clinic",
    member_email: str = "member@example.test",
    provider_email: str = "provider@example.test",
):
    member = _user(db, email=member_email, role_name="horse_owner")
    provider_account = _user(db, email=provider_email, role_name="provider")
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=PublicationStatus.PUBLISHED,
    )
    db.add(provider)
    db.flush()
    db.add(
        DirectProviderPortalAccess(
            provider_id=provider.id,
            user_id=provider_account.id,
            recipient_email=provider_account.email,
            sent_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return member, provider_account, provider


def _configure_synthetic_key(monkeypatch):
    key = base64.b64encode(b"test-only-synthetic-messaging-key!"[:32].ljust(32, b"!")).decode()
    monkeypatch.setattr(
        "app.services.messaging_encryption.get_settings",
        lambda: SimpleNamespace(
            MESSAGING_ENCRYPTION_KEYRING=json.dumps({"test-v1": key}),
            MESSAGING_ENCRYPTION_ACTIVE_KEY_ID="test-v1",
        ),
    )
    # These backend security tests inspect the durable outbox separately and
    # never run its SMTP worker or connect it to the non-test schema.
    monkeypatch.setattr(
        "app.api.v1.messages._dispatch_notifications", lambda _outbox_ids: None
    )


def _start(client, member, provider, *, request_id=None, message="Please call me."):
    return client.post(
        f"{BASE}/start",
        headers=_headers(member),
        json={
            "provider_id": str(provider.id),
            "request_id": str(request_id or uuid4()),
            "message": message,
            "consent": True,
        },
    )


def test_member_provider_round_trip_encrypts_storage_and_keeps_contact_private(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)

    unavailable = client.get(
        f"{BASE}/availability",
        params={"provider_id": str(provider.id)},
        headers=_headers(member),
    )
    assert unavailable.status_code == 200
    assert unavailable.json() == {
        "available": True,
        "reason": None,
        "provider_name": provider.name,
    }

    first = _start(client, member, provider)
    assert first.status_code == 201, first.text
    member_thread = first.json()
    assert member_thread["messages"][0]["body"] == "Please call me."
    assert member_thread["contact"] is None
    conversation_id = member_thread["conversation"]["id"]

    stored_conversation = db.get(ProviderConversation, conversation_id)
    stored_message = db.query(ProviderMessage).filter_by(conversation_id=conversation_id).one()
    assert "member@example.test" not in stored_conversation.contact_snapshot_ciphertext
    assert "555 0100" not in stored_conversation.contact_snapshot_ciphertext
    assert "Please call me." not in stored_message.body_ciphertext
    assert stored_message.body_ciphertext.startswith("v1.test-v1.")
    assert db.query(MessagingNotificationOutbox).filter_by(message_id=stored_message.id).count() == 2
    member_outbox = (
        db.query(MessagingNotificationOutbox)
        .filter_by(message_id=stored_message.id, recipient_user_id=member.id)
        .one()
    )
    member_outbox.status = "failed"
    db.commit()

    member_thread = client.get(
        f"{BASE}/{conversation_id}", headers=_headers(member)
    )
    provider_thread = client.get(
        f"{BASE}/{conversation_id}", headers=_headers(provider_user)
    )
    assert member_thread.status_code == provider_thread.status_code == 200
    assert member_thread.json()["conversation"]["notifications_failed"] is True
    assert provider_thread.json()["conversation"]["notifications_failed"] is False

    provider_data = provider_thread.json()
    assert provider_data["contact"] == {
        "name": "Member Example",
        "email": "member@example.test",
        "phone": "+1 555 0100",
    }
    assert provider_data["messages"][0]["body"] == "Please call me."

    reply = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(provider_user),
        json={"request_id": str(uuid4()), "message": "I can help."},
    )
    assert reply.status_code == 201, reply.text
    refreshed = client.get(f"{BASE}/{conversation_id}", headers=_headers(member))
    assert refreshed.status_code == 200
    assert [row["body"] for row in refreshed.json()["messages"]] == [
        "Please call me.",
        "I can help.",
    ]


def test_member_and_admin_assignment_cannot_read_another_conversation(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)
    other_member = _user(db, email="other@example.test", role_name="horse_owner")
    admin = _user(db, email="admin-plus-member@example.test", role_name="admin", roles=["horse_owner"])
    admin_provider = _user(db, email="admin-plus-provider@example.test", role_name="admin", roles=["provider"])
    db.commit()

    started = _start(client, member, provider)
    assert started.status_code == 201, started.text
    conversation_id = started.json()["conversation"]["id"]

    for outsider in (other_member, admin, admin_provider):
        response = client.get(f"{BASE}/{conversation_id}", headers=_headers(outsider))
        assert response.status_code in (403, 404)
        assert "Please call me." not in response.text
    assert client.get(f"{BASE}/unread", headers=_headers(admin)).status_code == 403
    assert client.get(f"{BASE}/unread", headers=_headers(admin_provider)).status_code == 403
    assert client.get(f"{BASE}/inbox", headers=_headers(provider_user)).status_code == 200


def test_idempotent_start_reuses_saved_message_and_outbox(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, _provider_user, provider = _provider_pair(db)
    request_id = uuid4()

    first = _start(client, member, provider, request_id=request_id)
    retry = _start(client, member, provider, request_id=request_id)
    assert first.status_code == 201, first.text
    assert retry.status_code == 201, retry.text
    assert first.json()["messages"][0]["id"] == retry.json()["messages"][0]["id"]
    assert db.query(ProviderConversation).count() == 1
    assert db.query(ProviderMessage).count() == 1
    assert db.query(MessagingNotificationOutbox).count() == 2

    conflicting = _start(
        client, member, provider, request_id=request_id, message="A different request."
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["detail"]["code"] == "message_request_conflict"
    assert db.query(ProviderMessage).count() == 1


def test_database_send_limit_is_per_account_and_allows_exact_idempotent_retry(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    monkeypatch.setattr("app.services.messaging_service.SEND_LIMIT", 1)
    member, provider_user, provider = _provider_pair(db)
    request_id = uuid4()
    first = _start(client, member, provider, request_id=request_id)
    retry = _start(client, member, provider, request_id=request_id)
    assert first.status_code == retry.status_code == 201

    conversation_id = first.json()["conversation"]["id"]
    provider_reply = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(provider_user),
        json={"request_id": str(uuid4()), "message": "Provider reply."},
    )
    assert provider_reply.status_code == 201
    over_limit = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(member),
        json={"request_id": str(uuid4()), "message": "One message too many."},
    )
    assert over_limit.status_code == 429
    assert over_limit.json()["detail"]["code"] == "message_send_limit"
    assert db.query(ProviderMessage).count() == 2


def test_missing_encryption_secret_disables_messaging_without_fallback(client, db, monkeypatch):
    member, _provider_user, provider = _provider_pair(db)
    monkeypatch.setattr(
        "app.services.messaging_encryption.get_settings",
        lambda: SimpleNamespace(
            MESSAGING_ENCRYPTION_KEYRING="",
            MESSAGING_ENCRYPTION_ACTIVE_KEY_ID="",
        ),
    )
    availability = client.get(
        f"{BASE}/availability",
        params={"provider_id": str(provider.id)},
        headers=_headers(member),
    )
    assert availability.status_code == 200
    assert availability.json()["reason"] == "messaging_encryption_unavailable"
    failed = _start(client, member, provider)
    assert failed.status_code == 503
    assert failed.json()["detail"]["code"] == "messaging_encryption_unavailable"
    assert db.query(ProviderConversation).count() == 0


def test_tampered_ciphertext_fails_closed_without_disclosing_plaintext(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)
    started = _start(client, member, provider)
    conversation_id = started.json()["conversation"]["id"]
    message = db.query(ProviderMessage).filter_by(conversation_id=conversation_id).one()
    message.body_ciphertext = "v1.test-v1.AAAAAAAAAAAAAAAAAAAAAAAA"
    db.commit()

    response = client.get(f"{BASE}/{conversation_id}", headers=_headers(provider_user))
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "message_content_unavailable"
    assert "Please call me." not in response.text


def test_explicit_owner_change_does_not_transfer_private_history(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, old_owner, provider = _provider_pair(db)
    started = _start(client, member, provider)
    conversation_id = started.json()["conversation"]["id"]
    new_owner = _user(db, email="replacement@example.test", role_name="provider")
    access = db.get(DirectProviderPortalAccess, provider.id)
    access.user_id = new_owner.id
    access.recipient_email = new_owner.email
    db.commit()

    assert client.get(f"{BASE}/{conversation_id}", headers=_headers(old_owner)).status_code in (
        403,
        404,
    )
    new_inbox = client.get(f"{BASE}/inbox", headers=_headers(new_owner))
    assert new_inbox.status_code == 200
    assert new_inbox.json()["items"] == []


def test_member_consent_and_profile_requirements_are_server_enforced(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, _provider_user, provider = _provider_pair(db)
    no_consent = client.post(
        f"{BASE}/start",
        headers=_headers(member),
        json={
            "provider_id": str(provider.id),
            "request_id": str(uuid4()),
            "message": "Can we talk?",
            "consent": False,
        },
    )
    assert no_consent.status_code == 422
    assert no_consent.json()["detail"]["code"] == "contact_sharing_consent_required"
    member.mobile_number = None
    db.commit()
    incomplete = _start(client, member, provider)
    assert incomplete.status_code == 409
    assert incomplete.json()["detail"]["code"] == "profile_incomplete"
    assert db.query(ProviderConversation).count() == 0


def test_read_cursor_cannot_advance_past_thread_and_is_monotonic(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)
    started = _start(client, member, provider)
    conversation_id = started.json()["conversation"]["id"]
    reply = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(provider_user),
        json={"request_id": str(uuid4()), "message": "A provider reply."},
    )
    assert reply.status_code == 201

    future = client.post(
        f"{BASE}/{conversation_id}/read",
        headers=_headers(member),
        json={"through_sequence": 3},
    )
    assert future.status_code == 422
    advance = client.post(
        f"{BASE}/{conversation_id}/read",
        headers=_headers(member),
        json={"through_sequence": 2},
    )
    assert advance.status_code == 200
    backwards = client.post(
        f"{BASE}/{conversation_id}/read",
        headers=_headers(member),
        json={"through_sequence": 1},
    )
    assert backwards.status_code == 200
    assert backwards.json()["read_sequence"] == 2


def test_get_does_not_mark_unseen_messages_and_receipts_do_not_skip_gaps(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)
    started = _start(client, member, provider)
    conversation_id = started.json()["conversation"]["id"]

    assert client.get("/api/v1/messages/unread", headers=_headers(provider_user)).json()["count"] == 1
    # Fetching plaintext is not evidence that the participant saw it.
    thread = client.get(
        f"{BASE}/{conversation_id}", headers=_headers(provider_user)
    )
    assert thread.status_code == 200, thread.text
    assert client.get("/api/v1/messages/unread", headers=_headers(provider_user)).json()["count"] == 1

    provider_reply = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(provider_user),
        json={"request_id": str(uuid4()), "message": "A provider reply."},
    )
    assert provider_reply.status_code == 201
    member_reply = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(member),
        json={"request_id": str(uuid4()), "message": "Another question."},
    )
    assert member_reply.status_code == 201

    # The member wrote sequence 3 without seeing incoming sequence 2. Reading
    # only 3 cannot move their cursor past that unseen earlier reply.
    own_message = client.post(
        f"{BASE}/{conversation_id}/read",
        headers=_headers(member),
        json={"message_sequences": [3]},
    )
    assert own_message.status_code == 200
    assert own_message.json()["read_sequence"] == 1
    assert client.get("/api/v1/messages/unread", headers=_headers(member)).json()["count"] == 1

    incoming = client.post(
        f"{BASE}/{conversation_id}/read",
        headers=_headers(member),
        json={"message_sequences": [2]},
    )
    assert incoming.status_code == 200
    assert incoming.json()["read_sequence"] == 3
    assert client.get("/api/v1/messages/unread", headers=_headers(member)).json()["count"] == 0


def test_each_supported_explicit_provider_ownership_path_can_message(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    for ownership_path in ("direct", "invitation", "registration"):
        member, provider_user, provider = _provider_pair(
            db,
            name=f"{ownership_path.title()} Clinic",
            member_email=f"{ownership_path}-member@example.test",
            provider_email=f"{ownership_path}-provider@example.test",
        )
        if ownership_path != "direct":
            db.delete(db.get(DirectProviderPortalAccess, provider.id))
            if ownership_path == "invitation":
                admin = _user(
                    db, email=f"{ownership_path}-admin@example.test", role_name="admin"
                )
                db.add(
                    ProviderInvitation(
                        provider_id=provider.id,
                        provider_type=provider.provider_type,
                        recipient_email=provider_user.email,
                        token_hash=f"{ownership_path}-completed-token",
                        status=InvitationStatus.COMPLETED,
                        expires_at=datetime.now(timezone.utc),
                        sent_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        portal_user_id=provider_user.id,
                        created_by=admin.id,
                    )
                )
            else:
                db.add(
                    ProviderRegistrationApplication(
                        user_id=provider_user.id,
                        provider_id=provider.id,
                        provider_type=provider.provider_type,
                        provider_name=provider.name,
                        visit_stability=provider.visit_stability,
                        postal_code="12345",
                        review_status=ProviderApplicationStatus.APPROVED,
                    )
                )
            db.commit()
        response = _start(client, member, provider)
        assert response.status_code == 201, f"{ownership_path}: {response.text}"


def test_ambiguous_or_disabled_provider_account_is_not_available(client, db):
    member, provider_user, provider = _provider_pair(db)
    second_owner = _user(db, email="second-owner@example.test", role_name="provider")
    admin = _user(db, email="inviter@example.test", role_name="admin")
    db.add(
        ProviderInvitation(
            provider_id=provider.id,
            provider_type=provider.provider_type,
            recipient_email=second_owner.email,
            token_hash="ambiguous-completed-invitation",
            status=InvitationStatus.COMPLETED,
            expires_at=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            portal_user_id=second_owner.id,
            created_by=admin.id,
        )
    )
    db.commit()
    ambiguous = client.get(
        f"{BASE}/availability",
        params={"provider_id": str(provider.id)},
        headers=_headers(member),
    )
    assert ambiguous.status_code == 200
    assert ambiguous.json()["available"] is False
    assert ambiguous.json()["reason"] == "provider_account_ambiguous"

    db.delete(db.query(ProviderInvitation).filter_by(provider_id=provider.id).one())
    provider_user.is_active = False
    db.commit()
    disabled = client.get(
        f"{BASE}/availability",
        params={"provider_id": str(provider.id)},
        headers=_headers(member),
    )
    assert disabled.json()["available"] is False
    assert disabled.json()["reason"] == "provider_account_unavailable"