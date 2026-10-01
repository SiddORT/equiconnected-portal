"""Consented, historical provider labels without profile or plaintext fallbacks."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy.orm.attributes import set_committed_value

from app.models.messaging import ProviderConversation, ProviderMessage
from app.models.provider import DirectProviderPortalAccess
from app.services.messaging_encryption import encrypt_text
from app.services import messaging_service
from app.services.messaging_service import MessagingService
from tests.test_private_messaging import (
    BASE, _configure_synthetic_key, _headers, _provider_pair, _start, _user,
)


def _snapshot(db, conversation_id, payload):
    conversation = db.get(ProviderConversation, conversation_id)
    conversation.contact_snapshot_ciphertext = encrypt_text(
        payload,
        conversation_id=conversation.id,
        record_id=conversation.id,
        field="contact_snapshot",
    )
    db.commit()
    return conversation


def test_existing_saved_names_survive_profile_edits_and_reopening(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, owner, provider = _provider_pair(db)
    first = _start(client, member, provider).json()["conversation"]["id"]
    second_member = _user(db, email="second@example.test", role_name="horse_owner")
    db.commit()
    second = _start(client, second_member, provider).json()["conversation"]["id"]
    encrypted = db.get(ProviderConversation, first).contact_snapshot_ciphertext
    assert "Member Example" not in encrypted
    member.first_name, member.last_name = "Changed", "Profile"
    db.commit()
    db.expire_all()

    for _ in range(2):
        inbox = client.get(f"{BASE}/inbox", headers=_headers(owner))
        assert inbox.status_code == 200
        items = {item["id"]: item for item in inbox.json()["items"]}
        assert items[first]["member_name"] == "Member Example"
        assert items[second]["member_name"] == "Second Example"
        for item in items.values():
            assert not {"contact", "email", "phone"} & item.keys()
        for conversation_id, name in ((first, "Member Example"), (second, "Second Example")):
            thread = client.get(f"{BASE}/{conversation_id}", headers=_headers(owner))
            assert thread.status_code == 200
            assert thread.json()["conversation"]["member_name"] == name
            assert thread.json()["contact"]["name"] == name
    assert db.get(ProviderConversation, first).contact_snapshot_ciphertext == encrypted
    assert db.query(ProviderMessage).count() == 2
    member_inbox = client.get(f"{BASE}/inbox", headers=_headers(member)).json()
    assert member_inbox["items"][0]["member_name"] is None
    assert client.get(f"{BASE}/{first}", headers=_headers(member)).json()["conversation"]["member_name"] is None


@pytest.mark.parametrize("name", ["absent", None, "", " \t\n ", 123, ["not a name"]])
def test_readable_snapshot_without_usable_name_keeps_generic_identity(client, db, monkeypatch, name):
    _configure_synthetic_key(monkeypatch)
    member, owner, provider = _provider_pair(db)
    conversation_id = _start(client, member, provider).json()["conversation"]["id"]
    payload = {"email": "not-a-label@example.test", "phone": "+1 555 0100"}
    if name != "absent":
        payload["name"] = name
    _snapshot(db, conversation_id, json.dumps(payload))
    inbox = client.get(f"{BASE}/inbox", headers=_headers(owner))
    thread = client.get(f"{BASE}/{conversation_id}", headers=_headers(owner))
    assert inbox.status_code == thread.status_code == 200
    assert inbox.json()["items"][0]["member_name"] is None
    assert thread.json()["conversation"]["member_name"] is None
    assert thread.json()["contact"]["name"] == ""
    assert "not-a-label@example.test" not in inbox.text


def test_saved_unicode_name_is_trimmed_consistently_without_extra_contact_fields(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, owner, provider = _provider_pair(db)
    conversation_id = _start(client, member, provider).json()["conversation"]["id"]
    _snapshot(db, conversation_id, json.dumps({
        "name": "  Élise Synthetic Member  ",
        "email": "synthetic@example.test",
        "phone": "+1 555 0100",
        "unrecognized": "must not be returned",
    }))
    inbox = client.get(f"{BASE}/inbox", headers=_headers(owner)).json()
    thread = client.get(f"{BASE}/{conversation_id}", headers=_headers(owner)).json()
    assert inbox["items"][0]["member_name"] == "Élise Synthetic Member"
    assert thread["conversation"]["member_name"] == thread["contact"]["name"] == "Élise Synthetic Member"
    assert "unrecognized" not in thread["contact"]


def test_absent_recorded_consent_never_decrypts_or_discloses_contact(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, owner, provider = _provider_pair(db)
    conversation_id = _start(client, member, provider).json()["conversation"]["id"]
    original = MessagingService._conversation_for_participant

    def without_consent(self, *args):
        result = original(self, *args)
        # Model disallows new consentless rows; emulate a legacy readable record
        # at the authorized boundary without changing schema or stored consent.
        set_committed_value(result[0], "contact_consent_at", None)
        return result

    monkeypatch.setattr(MessagingService, "_conversation_for_participant", without_consent)
    original_decrypt = messaging_service.decrypt_text

    def no_contact_decrypt(*args, **kwargs):
        assert kwargs["field"] != "contact_snapshot"
        return original_decrypt(*args, **kwargs)

    monkeypatch.setattr("app.services.messaging_service.decrypt_text", no_contact_decrypt)
    inbox = client.get(f"{BASE}/inbox", headers=_headers(owner))
    thread = client.get(f"{BASE}/{conversation_id}", headers=_headers(owner))
    assert inbox.status_code == thread.status_code == 200
    assert inbox.json()["items"][0]["member_name"] is None
    assert thread.json()["conversation"]["member_name"] is None
    assert thread.json()["contact"] is None


def test_only_requested_authorized_provider_page_decrypts_labels(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, owner, provider = _provider_pair(db)
    first = _start(client, member, provider).json()["conversation"]["id"]
    second_member = _user(db, email="latest@example.test", role_name="horse_owner")
    db.commit()
    second = _start(client, second_member, provider).json()["conversation"]["id"]
    db.get(ProviderConversation, first).contact_snapshot_ciphertext = "invalid"
    db.commit()
    response = client.get(f"{BASE}/inbox?page_size=1", headers=_headers(owner))
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["id"] == second
    assert response.json()["items"][0]["member_name"] == "Latest Example"
    assert client.get(f"{BASE}/inbox?page=2&page_size=1", headers=_headers(owner)).status_code == 503
    # Members do not decrypt contact snapshots at all.
    assert client.get(f"{BASE}/inbox", headers=_headers(member)).status_code == 200
    assert client.get(f"{BASE}/{first}", headers=_headers(member)).status_code == 200
    assert client.get(f"{BASE}/inbox?page=3&page_size=1", headers=_headers(owner)).json()["items"] == []


@pytest.mark.parametrize("failure", ["ciphertext", "json", "array", "unknown_key", "missing_keys", "swapped"])
def test_snapshot_failures_keep_safe_503_without_profile_fallback(client, db, monkeypatch, failure):
    _configure_synthetic_key(monkeypatch)
    member, owner, provider = _provider_pair(db)
    conversation_id = _start(client, member, provider).json()["conversation"]["id"]
    conversation = db.get(ProviderConversation, conversation_id)
    expected = "message_content_unavailable"
    if failure == "ciphertext":
        conversation.contact_snapshot_ciphertext = "v1.test-v1.AAAAAAAAAAAAAAAAAAAAAAAA"
    elif failure in ("json", "array"):
        _snapshot(db, conversation_id, "not json" if failure == "json" else "[]")
    elif failure == "unknown_key":
        conversation.contact_snapshot_ciphertext = conversation.contact_snapshot_ciphertext.replace(".test-v1.", ".missing.")
        expected = "messaging_encryption_unavailable"
    elif failure == "missing_keys":
        monkeypatch.setattr("app.services.messaging_encryption.get_settings", lambda: SimpleNamespace(
            MESSAGING_ENCRYPTION_KEYRING="", MESSAGING_ENCRYPTION_ACTIVE_KEY_ID="",
        ))
        expected = "messaging_encryption_unavailable"
    else:
        other = _user(db, email="other-snapshot@example.test", role_name="horse_owner")
        db.commit()
        other_id = _start(client, other, provider).json()["conversation"]["id"]
        conversation.contact_snapshot_ciphertext = db.get(ProviderConversation, other_id).contact_snapshot_ciphertext
    db.commit()
    for path in (f"{BASE}/inbox", f"{BASE}/{conversation_id}"):
        response = client.get(path, headers=_headers(owner))
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == expected
        assert "Member Example" not in response.text
        assert member.email not in response.text


def test_outsiders_admins_and_replacement_owners_cannot_discover_or_decrypt_names(client, db, monkeypatch):
    _configure_synthetic_key(monkeypatch)
    member, owner, provider = _provider_pair(db)
    conversation_id = _start(client, member, provider).json()["conversation"]["id"]
    outsider = _user(db, email="outsider@example.test", role_name="horse_owner")
    admin = _user(db, email="admin@example.test", role_name="admin", roles=["provider", "horse_owner"])
    _, unrelated_owner, _ = _provider_pair(
        db, member_email="unrelated-member@example.test", provider_email="unrelated-provider@example.test",
    )

    def forbidden_decryption(*args, **kwargs):
        pytest.fail("Unauthorized request attempted sensitive decryption")

    monkeypatch.setattr("app.services.messaging_service.decrypt_text", forbidden_decryption)
    for user in (outsider, unrelated_owner, admin):
        inbox = client.get(f"{BASE}/inbox", headers=_headers(user))
        assert inbox.status_code == 403 or inbox.json()["items"] == []
        response = client.get(f"{BASE}/{conversation_id}", headers=_headers(user))
        assert response.status_code in (403, 404)
        assert "Member Example" not in inbox.text + response.text
    replacement = _user(db, email="replacement@example.test", role_name="provider")
    access = db.get(DirectProviderPortalAccess, provider.id)
    access.user_id, access.recipient_email = replacement.id, replacement.email
    db.commit()
    for user in (owner, replacement, member):
        inbox = client.get(f"{BASE}/inbox", headers=_headers(user))
        assert inbox.status_code == 403 or inbox.json()["items"] == []
        response = client.get(f"{BASE}/{conversation_id}", headers=_headers(user))
        assert response.status_code in (403, 404)
        assert "Member Example" not in inbox.text + response.text