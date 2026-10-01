"""Versioned AES-GCM envelopes for private message and contact content."""
from __future__ import annotations

import base64
import binascii
import json
import re
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_FORMAT_VERSION = "v1"
_AAD_PREFIX = b"equiconnected/private-messaging"


class MessagingEncryptionUnavailable(Exception):
    """Messaging must remain unavailable without a valid dedicated keyring."""


class MessagingCiphertextInvalid(Exception):
    """Stored encrypted content cannot be authenticated or decoded."""


def _keyring() -> tuple[str, dict[str, bytes]]:
    settings = get_settings()
    raw = settings.MESSAGING_ENCRYPTION_KEYRING
    active_id = settings.MESSAGING_ENCRYPTION_ACTIVE_KEY_ID
    if not raw or not active_id or not _KEY_ID.fullmatch(active_id):
        raise MessagingEncryptionUnavailable("Private messaging encryption is not configured.")
    try:
        encoded_keys = json.loads(raw)
        if not isinstance(encoded_keys, dict) or not encoded_keys:
            raise ValueError
        keys = {}
        for key_id, encoded_key in encoded_keys.items():
            if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
                raise ValueError
            if not isinstance(encoded_key, str):
                raise ValueError
            decoded = base64.b64decode(encoded_key, validate=True)
            if len(decoded) != 32:
                raise ValueError
            keys[key_id] = decoded
        if active_id not in keys:
            raise ValueError
        return active_id, keys
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise MessagingEncryptionUnavailable(
            "Private messaging encryption is not configured."
        ) from exc


def _aad(conversation_id: UUID, record_id: UUID, field: str) -> bytes:
    return b":".join(
        (
            _AAD_PREFIX,
            _FORMAT_VERSION.encode("ascii"),
            str(conversation_id).encode("ascii"),
            str(record_id).encode("ascii"),
            field.encode("ascii"),
        )
    )


def ensure_encryption_available() -> None:
    """Validate dedicated key configuration without persisting any content."""
    _keyring()


def encrypt_text(plaintext: str, *, conversation_id: UUID, record_id: UUID, field: str) -> str:
    """Encrypt text with a fresh nonce and authenticated record/field binding."""
    from os import urandom

    active_id, keys = _keyring()
    nonce = urandom(12)
    ciphertext = AESGCM(keys[active_id]).encrypt(
        nonce,
        plaintext.encode("utf-8"),
        _aad(conversation_id, record_id, field),
    )
    payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{_FORMAT_VERSION}.{active_id}.{payload}"


def decrypt_text(
    envelope: str, *, conversation_id: UUID, record_id: UUID, field: str
) -> str:
    """Authenticate and decrypt a v1 envelope, retaining explicit safe failures."""
    active_id, keys = _keyring()
    del active_id
    try:
        version, key_id, encoded = envelope.split(".", maxsplit=2)
        if version != _FORMAT_VERSION or not _KEY_ID.fullmatch(key_id):
            raise ValueError
        key = keys.get(key_id)
        if key is None:
            raise MessagingEncryptionUnavailable(
                "Private messaging encryption is not configured."
            )
        data = base64.b64decode(encoded, altchars=b"-_", validate=True)
        if len(data) < 12 + 16:
            raise ValueError
        plaintext = AESGCM(key).decrypt(
            data[:12],
            data[12:],
            _aad(conversation_id, record_id, field),
        )
        return plaintext.decode("utf-8")
    except MessagingEncryptionUnavailable:
        raise
    except (ValueError, UnicodeDecodeError, binascii.Error, InvalidTag) as exc:
        raise MessagingCiphertextInvalid(
            "Private message content could not be authenticated."
        ) from exc