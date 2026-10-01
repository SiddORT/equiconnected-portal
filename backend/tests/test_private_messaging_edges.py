"""Regression coverage for messaging access, encryption, limits, and races."""
import base64
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fastapi import Request

from app.main import app
from app.models.enums import PublicationStatus, ProviderStatus
from app.models.messaging import (
    MessagingSendLimit,
    ProviderConversation,
    ProviderMessage,
)
from app.models.user import User
from app.services.messaging_encryption import (
    MessagingCiphertextInvalid,
    MessagingEncryptionUnavailable,
    decrypt_text,
    encrypt_text,
)
from app.services.messaging_service import MessagingService
from tests.conftest import TestingSessionLocal
from tests.test_private_messaging import (
    BASE,
    _configure_synthetic_key,
    _headers,
    _provider_pair,
    _start,
    _user,
)


def _key_settings(keys: dict[str, bytes], active_key_id: str):
    encoded = {
        key_id: base64.b64encode(value).decode("ascii")
        for key_id, value in keys.items()
    }
    return SimpleNamespace(
        MESSAGING_ENCRYPTION_KEYRING=json.dumps(encoded),
        MESSAGING_ENCRYPTION_ACTIVE_KEY_ID=active_key_id,
    )


def test_unverified_accounts_and_anonymous_requests_cannot_use_messaging(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)
    member.email_verified_at = None
    unverified_provider = _user(
        db, email="unverified-provider@example.test", role_name="provider"
    )
    unverified_provider.email_verified_at = None
    outsider_provider = _user(
        db, email="unlinked-provider@example.test", role_name="provider"
    )
    started = _start(client, member, provider)
    assert started.status_code == 403

    # Restore verification to create a thread, then make sure a different
    # provider account cannot use inbox/unread to discover it.
    member.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    started = _start(client, member, provider)
    assert started.status_code == 201
    conversation_id = started.json()["conversation"]["id"]

    for path in (f"{BASE}/inbox", f"{BASE}/unread"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=_headers(unverified_provider)).status_code == 403
    for path in (f"{BASE}/inbox", f"{BASE}/unread"):
        # A provider account with no explicit listing ownership cannot create
        # a portal session, so it must not enumerate either participant's data.
        assert client.get(path, headers=_headers(outsider_provider)).status_code == 403
    assert client.get(
        f"{BASE}/{conversation_id}", headers=_headers(outsider_provider)
    ).status_code == 403
    assert client.get(f"{BASE}/availability", params={"provider_id": str(provider.id)}).status_code == 401
    assert provider_user.is_active


def test_admin_primary_or_assigned_role_is_denied_all_mailboxes(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, _provider_user, provider = _provider_pair(db)
    started = _start(client, member, provider)
    assert started.status_code == 201
    admin_member = _user(
        db, email="admin-member@example.test", role_name="admin", roles=["horse_owner"]
    )
    admin_provider = _user(
        db, email="admin-provider@example.test", role_name="admin", roles=["provider"]
    )
    db.commit()

    for admin in (admin_member, admin_provider):
        for path in (f"{BASE}/inbox", f"{BASE}/unread"):
            assert client.get(path, headers=_headers(admin)).status_code == 403
        assert client.get(
            f'{BASE}/{started.json()["conversation"]["id"]}',
            headers=_headers(admin),
        ).status_code in (403, 404)


def test_stable_manager_can_message_but_withdrawn_listing_hides_old_thread(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)
    member = _user(
        db, email="stable-manager@example.test", role_name="stable_manager"
    )
    db.commit()

    started = _start(client, member, provider)
    assert started.status_code == 201, started.text
    conversation_id = started.json()["conversation"]["id"]
    provider.status = ProviderStatus.INACTIVE
    db.commit()

    availability = client.get(
        f"{BASE}/availability",
        params={"provider_id": str(provider.id)},
        headers=_headers(member),
    )
    assert availability.status_code == 200
    assert availability.json()["available"] is False
    assert availability.json()["reason"] == "provider_unavailable"
    assert client.get(
        f"{BASE}/{conversation_id}", headers=_headers(member)
    ).status_code == 404
    assert client.get(
        f"{BASE}/inbox", headers=_headers(member)
    ).json()["items"] == []
    assert client.get(
        f"{BASE}/unread", headers=_headers(provider_user)
    ).json()["count"] == 0


def test_unpublished_listing_and_disabled_participant_invalidate_private_access(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)
    started = _start(client, member, provider)
    assert started.status_code == 201, started.text
    conversation_id = started.json()["conversation"]["id"]

    provider.publication_status = PublicationStatus.UNPUBLISHED
    db.commit()
    assert client.get(
        f"{BASE}/{conversation_id}", headers=_headers(member)
    ).status_code == 404
    assert client.get(
        f"{BASE}/availability",
        params={"provider_id": str(provider.id)},
        headers=_headers(member),
    ).json()["available"] is False

    provider.publication_status = PublicationStatus.PUBLISHED
    member.is_active = False
    db.commit()
    assert client.get(f"{BASE}/inbox", headers=_headers(member)).status_code == 403

    member.is_active = True
    provider_user.is_active = False
    db.commit()
    assert client.get(
        f"{BASE}/availability",
        params={"provider_id": str(provider.id)},
        headers=_headers(member),
    ).json()["available"] is False
    assert client.get(
        f"{BASE}/{conversation_id}", headers=_headers(member)
    ).status_code == 404
    assert client.get(f"{BASE}/inbox", headers=_headers(provider_user)).status_code == 403
    assert client.get(f"{BASE}/unread", headers=_headers(provider_user)).status_code == 403


def test_key_rotation_decrypts_old_envelopes_and_ciphertext_is_record_bound(monkeypatch):
    key_v1 = b"\x11" * 32
    key_v2 = b"\x22" * 32
    monkeypatch.setattr(
        "app.services.messaging_encryption.get_settings",
        lambda: _key_settings({"key-v1": key_v1}, "key-v1"),
    )
    conversation_id, first_record_id, second_record_id = uuid4(), uuid4(), uuid4()
    old_envelope = encrypt_text(
        "rotated message",
        conversation_id=conversation_id,
        record_id=first_record_id,
        field="message_body",
    )

    monkeypatch.setattr(
        "app.services.messaging_encryption.get_settings",
        lambda: _key_settings({"key-v1": key_v1, "key-v2": key_v2}, "key-v2"),
    )
    assert decrypt_text(
        old_envelope,
        conversation_id=conversation_id,
        record_id=first_record_id,
        field="message_body",
    ) == "rotated message"
    with pytest.raises(MessagingCiphertextInvalid):
        decrypt_text(
            old_envelope,
            conversation_id=conversation_id,
            record_id=second_record_id,
            field="message_body",
        )
    with pytest.raises(MessagingCiphertextInvalid):
        decrypt_text(
            old_envelope,
            conversation_id=uuid4(),
            record_id=first_record_id,
            field="message_body",
        )
    with pytest.raises(MessagingCiphertextInvalid):
        decrypt_text(
            old_envelope,
            conversation_id=conversation_id,
            record_id=first_record_id,
            field="contact_snapshot",
        )
    monkeypatch.setattr(
        "app.services.messaging_encryption.get_settings",
        lambda: _key_settings({"key-v2": key_v2}, "key-v2"),
    )
    with pytest.raises(MessagingEncryptionUnavailable):
        decrypt_text(
            old_envelope,
            conversation_id=conversation_id,
            record_id=first_record_id,
            field="message_body",
        )

    new_envelope = encrypt_text(
        "new key message",
        conversation_id=conversation_id,
        record_id=second_record_id,
        field="message_body",
    )
    assert new_envelope.startswith("v1.key-v2.")
    assert decrypt_text(
        new_envelope,
        conversation_id=conversation_id,
        record_id=second_record_id,
        field="message_body",
    ) == "new key message"


@pytest.mark.parametrize(
    ("keys", "active"),
    [
        ("not json", "key-v1"),
        ('{"key-v1":"bm90LWEtMzItYnl0ZS1rZXk="}', "key-v1"),
        ('{"key-v1":"AQID"}', "missing"),
    ],
)
def test_invalid_keyring_fails_closed(monkeypatch, keys, active):
    monkeypatch.setattr(
        "app.services.messaging_encryption.get_settings",
        lambda: SimpleNamespace(
            MESSAGING_ENCRYPTION_KEYRING=keys,
            MESSAGING_ENCRYPTION_ACTIVE_KEY_ID=active,
        ),
    )
    with pytest.raises(MessagingEncryptionUnavailable):
        encrypt_text(
            "not saved",
            conversation_id=uuid4(),
            record_id=uuid4(),
            field="message_body",
        )


def test_validation_does_not_echo_plaintext_and_authorized_html_stays_plain_text(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    member, _provider_user, provider = _provider_pair(db)
    secret_text = "<script>private-notification-payload</script>"
    rejected = _start(
        client,
        member,
        provider,
        message="x" * 5_001,
    )
    assert rejected.status_code == 422
    assert secret_text not in rejected.text
    assert "xxxxx" not in rejected.text
    assert db.query(ProviderConversation).count() == 0

    accepted = _start(client, member, provider, message=secret_text)
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["messages"][0]["body"] == secret_text
    stored = db.query(ProviderMessage).one()
    assert secret_text not in stored.body_ciphertext
    assert secret_text not in accepted.json()["conversation"]


def test_unhandled_message_errors_do_not_write_plaintext_to_logs(monkeypatch):
    secret = "member@example.test +1 555 0100 confidential message"
    captured = {}

    class CapturingLogger:
        def error(self, event, **fields):
            captured.update(event=event, **fields)

    monkeypatch.setattr("app.main.get_logger", lambda _name: CapturingLogger())
    handler = app.exception_handlers[Exception]
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"{BASE}/not-a-real-thread",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "http_version": "1.1",
            "server": ("testserver", 80),
            "client": ("testclient", 1234),
        }
    )
    response = asyncio.run(handler(request, RuntimeError(secret)))
    assert response.status_code == 500
    assert secret.encode() not in response.body
    assert captured["event"] == "unhandled_exception"
    assert captured["exc"] == "RuntimeError"
    assert secret not in repr(captured)


def test_send_limit_is_persisted_per_account_and_resets_after_window(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    monkeypatch.setattr("app.services.messaging_service.SEND_LIMIT", 2)
    member, provider_user, provider = _provider_pair(db)
    started = _start(client, member, provider)
    assert started.status_code == 201, started.text
    conversation_id = started.json()["conversation"]["id"]

    first_reply = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(member),
        json={"request_id": str(uuid4()), "message": "Second member message."},
    )
    assert first_reply.status_code == 201
    limited = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(member),
        json={"request_id": str(uuid4()), "message": "Over the member limit."},
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3600"
    budget = db.get(MessagingSendLimit, member.id)
    assert budget.send_count == 2

    budget.window_started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()
    allowed_after_window = client.post(
        f"{BASE}/{conversation_id}/messages",
        headers=_headers(member),
        json={"request_id": str(uuid4()), "message": "After the window."},
    )
    assert allowed_after_window.status_code == 201
    assert db.get(MessagingSendLimit, member.id).send_count == 1
    assert client.get(f"{BASE}/unread", headers=_headers(provider_user)).json()["count"] == 3


def test_paginated_history_and_concurrent_read_receipts_do_not_skip_unseen(
    client, db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    member, provider_user, provider = _provider_pair(db)
    started = _start(client, member, provider)
    assert started.status_code == 201
    conversation_id = started.json()["conversation"]["id"]
    conversation = db.get(ProviderConversation, conversation_id)
    # Seed an extended history through the same serialization/encryption path,
    # avoiding a large HTTP loop unrelated to pagination assertions.
    for sequence in range(2, 106):
        sender, side = (
            (provider_user, "provider") if sequence % 2 == 0 else (member, "member")
        )
        MessagingService(db)._append_message(
            conversation,
            sender,
            side,
            f"History message {sequence}",
            uuid4(),
        )
    db.commit()

    headers = _headers(member)
    page_one = client.get(
        f"{BASE}/{conversation_id}?limit=50", headers=headers
    ).json()
    assert [message["sequence"] for message in page_one["messages"]] == list(range(56, 106))
    assert page_one["next_before_sequence"] == 56
    page_two = client.get(
        f"{BASE}/{conversation_id}?limit=50&before_sequence=56", headers=headers
    ).json()
    assert [message["sequence"] for message in page_two["messages"]] == list(range(6, 56))
    assert page_two["next_before_sequence"] == 6
    page_three = client.get(
        f"{BASE}/{conversation_id}?limit=50&before_sequence=6", headers=headers
    ).json()
    assert [message["sequence"] for message in page_three["messages"]] == list(range(1, 6))
    sequences = [
        message["sequence"]
        for page in (page_one, page_two, page_three)
        for message in page["messages"]
    ]
    assert sorted(sequences) == list(range(1, 106))
    # Merely fetching any of the history pages did not acknowledge incoming
    # messages. There are 52 provider messages at even sequences 2..104.
    assert client.get(
        f"{BASE}/unread", headers=headers
    ).json()["count"] == 52

    # Member-owned odd messages are already read; mark out-of-order rendered
    # incoming messages concurrently. The cursor must wait for a missing gap,
    # then advance through all now-read messages once that gap is filled.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _mark_read_in_session, member.id, conversation_id, [104]
            ),
            pool.submit(
                _mark_read_in_session, member.id, conversation_id, [2]
            ),
        ]
        receipts = [future.result() for future in futures]
    assert sorted(cursor for _received, cursor in receipts)[-1] == 3
    assert sorted(received for received, _cursor in receipts)[-1] == [104]
    final = client.get(
        f"{BASE}/{conversation_id}?limit=50", headers=headers
    ).json()
    assert final["conversation"]["unread_count"] > 0
    assert client.get(f"{BASE}/unread", headers=headers).json()["count"] > 0


def _start_in_session(member_id, provider_id, request_id, body):
    session = TestingSessionLocal()
    try:
        member = session.get(User, member_id)
        result = MessagingService(session).start(
            member,
            provider_id=provider_id,
            request_id=request_id,
            raw_body=body,
            consent=True,
        )
        return result[0].id, result[1].id
    finally:
        session.rollback()
        session.close()


def _reply_in_session(user_id, conversation_id, request_id, body):
    session = TestingSessionLocal()
    try:
        user = session.get(User, user_id)
        result = MessagingService(session).reply(
            user,
            conversation_id=conversation_id,
            request_id=request_id,
            raw_body=body,
        )
        return result[1].id, result[1].sequence
    finally:
        session.rollback()
        session.close()


def _mark_read_in_session(user_id, conversation_id, sequences):
    session = TestingSessionLocal()
    try:
        user = session.get(User, user_id)
        return MessagingService(session).mark_read(
            user,
            conversation_id=conversation_id,
            message_sequences=sequences,
        )
    finally:
        session.rollback()
        session.close()


def test_concurrent_first_messages_deduplicate_and_distinct_requests_share_thread(
    db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    monkeypatch.setattr("app.services.messaging_service.SEND_LIMIT", 100)
    member, _provider_user, provider = _provider_pair(db)
    member_id, provider_id = member.id, provider.id
    db.commit()
    shared_request_id = uuid4()
    with ThreadPoolExecutor(max_workers=6) as pool:
        duplicate_results = list(
            pool.map(
                lambda _index: _start_in_session(
                    member_id, provider_id, shared_request_id, "Same first message."
                ),
                range(6),
            )
        )
    assert len({conversation_id for conversation_id, _ in duplicate_results}) == 1
    assert len({message_id for _, message_id in duplicate_results}) == 1
    assert db.query(ProviderConversation).count() == 1
    assert db.query(ProviderMessage).count() == 1

    with ThreadPoolExecutor(max_workers=6) as pool:
        distinct_results = list(
            pool.map(
                lambda index: _start_in_session(
                    member_id, provider_id, uuid4(), f"Concurrent message {index}."
                ),
                range(6),
            )
        )
    assert {conversation_id for conversation_id, _ in distinct_results} == {
        duplicate_results[0][0]
    }
    sequences = [message.sequence for message in db.query(ProviderMessage).all()]
    assert sorted(sequences) == list(range(1, 8))


def test_concurrent_replies_deduplicate_idempotent_request_and_serialize_sequences(
    db, monkeypatch
):
    _configure_synthetic_key(monkeypatch)
    monkeypatch.setattr("app.services.messaging_service.SEND_LIMIT", 100)
    member, provider_user, provider = _provider_pair(db)
    provider_user_id = provider_user.id
    provider_id = provider.id
    service = MessagingService(db)
    conversation, _, _, _ = service.start(
        member,
        provider_id=provider_id,
        request_id=uuid4(),
        raw_body="Start conversation.",
        consent=True,
    )
    conversation_id = conversation.id
    db.commit()

    shared_request_id = uuid4()
    with ThreadPoolExecutor(max_workers=6) as pool:
        duplicates = list(
            pool.map(
                lambda _index: _reply_in_session(
                    provider_user_id,
                    conversation_id,
                    shared_request_id,
                    "Same provider reply.",
                ),
                range(6),
            )
        )
    assert len({message_id for message_id, _ in duplicates}) == 1
    assert len({sequence for _, sequence in duplicates}) == 1

    with ThreadPoolExecutor(max_workers=6) as pool:
        replies = list(
            pool.map(
                lambda index: _reply_in_session(
                    provider_user_id,
                    conversation_id,
                    uuid4(),
                    f"Concurrent reply {index}.",
                ),
                range(6),
            )
        )
    sequences = sorted(message.sequence for message in db.query(ProviderMessage).all())
    assert sequences == list(range(1, 9))
    assert sorted(sequence for _, sequence in replies) == list(range(3, 9))
