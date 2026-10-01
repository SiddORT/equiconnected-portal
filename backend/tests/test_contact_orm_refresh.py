"""Regressions for the ORM plaintext view across refresh/expiration boundaries."""
from __future__ import annotations

import base64
import json
import secrets
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select

from app.db.contact_types import ContactPersistenceError, EncryptedContactValue
from app.models.role import Role
from app.models.user import User
from app.services import contact_encryption
from app.services.contact_encryption import (
    ContactCiphertextInvalid,
    ContactEncryptionUnavailable,
    decrypt_contact,
    encrypt_contact,
    is_contact_ciphertext,
    normalize_contact,
)


def test_v1_prefixed_email_is_plaintext_and_malformed_envelopes_fail_closed():
    email = "v1.user@example.com"
    envelope = encrypt_contact(
        email, table="users", record_id="v1-prefix-test", field="email"
    )
    assert not is_contact_ciphertext(email)
    assert is_contact_ciphertext(envelope)
    assert decrypt_contact(
        envelope, table="users", record_id="v1-prefix-test", field="email"
    ) == email
    assert normalize_contact("Straße@example.com", field="email") == (
        "straße@example.com"
    )
    with pytest.raises(ContactCiphertextInvalid):
        decrypt_contact(
            "v1.test-ephemeral.not-an-envelope",
            table="users",
            record_id="v1-prefix-test",
            field="email",
        )


def test_plaintext_contacts_survive_commit_expire_and_explicit_refresh(db):
    role = Role(name=f"contact-refresh-{uuid4().hex}", description="Test only")
    email = f"refresh-{uuid4().hex}@example.invalid"
    mobile = "+971501234567"
    user = User(
        id=uuid4(),
        email=email,
        mobile_number=mobile,
        password_hash="not-a-real-password-hash",
        role=role,
    )
    db.add(user)
    db.commit()

    # expire_on_commit reloads these attributes; the ORM refresh boundary must
    # restore the existing Python/API plaintext contract.
    assert user.email == email
    assert user.mobile_number == mobile

    db.expire(user, ["email", "mobile_number"])
    assert user.email == email
    assert user.mobile_number == mobile

    db.refresh(user, attribute_names=["email", "mobile_number"])
    assert user.email == email
    assert user.mobile_number == mobile


def test_scalar_contact_select_returns_opaque_nonserializable_value_not_ciphertext(db):
    role = Role(name=f"contact-scalar-{uuid4().hex}", description="Test only")
    email = f"scalar-{uuid4().hex}@example.invalid"
    user = User(
        id=uuid4(),
        email=email,
        password_hash="not-a-real-password-hash",
        role=role,
    )
    db.add(user)
    db.commit()

    selected = db.scalar(select(User.email).where(User.id == user.id))
    assert isinstance(selected, EncryptedContactValue)
    assert not isinstance(selected, str)
    assert "ciphertext" not in repr(selected)
    with pytest.raises((TypeError, ValueError)):
        jsonable_encoder(selected)


def test_core_cannot_write_plaintext_into_blind_index_column(db):
    with pytest.raises(ContactPersistenceError):
        db.execute(
            insert(User.__table__).values(
                email_blind_index="plaintext@example.invalid"
            )
        )


@pytest.mark.parametrize(
    "reused_secret",
    ("jwt-aes", "jwt-blind-index", "messaging-aes", "messaging-blind-index"),
)
def test_contact_key_material_cannot_reuse_jwt_or_messaging_keys(
    monkeypatch, reused_secret
):
    aes_key, blind_key = secrets.token_bytes(32), secrets.token_bytes(32)
    jwt_key = "unrelated-jwt-secret"
    messaging_ring = {}
    if reused_secret == "jwt-aes":
        jwt_key = base64.b64encode(aes_key).decode("ascii")
    elif reused_secret == "jwt-blind-index":
        jwt_key = base64.b64encode(blind_key).decode("ascii")
    elif reused_secret == "messaging-aes":
        messaging_ring = {"messaging": base64.b64encode(aes_key).decode("ascii")}
    else:
        messaging_ring = {"messaging": base64.b64encode(blind_key).decode("ascii")}

    monkeypatch.setattr(
        contact_encryption,
        "get_settings",
        lambda: SimpleNamespace(
            CONTACT_ENCRYPTION_KEYRING=json.dumps(
                {"contact": base64.b64encode(aes_key).decode("ascii")}
            ),
            CONTACT_ENCRYPTION_ACTIVE_KEY_ID="contact",
            CONTACT_BLIND_INDEX_KEY=base64.b64encode(blind_key).decode("ascii"),
            SECRET_KEY=jwt_key,
            MESSAGING_ENCRYPTION_KEYRING=json.dumps(messaging_ring)
            if messaging_ring
            else "",
        ),
    )
    with pytest.raises(ContactEncryptionUnavailable):
        contact_encryption.ensure_contact_encryption_available()