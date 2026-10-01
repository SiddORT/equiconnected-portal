"""Authenticated encryption and keyed blind indexes for persisted contact values.

Contact encryption deliberately has its own keyring and blind-index secret.  It
is separate from both application signing secrets and private-messaging keys.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from os import urandom
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_CONTACT_ENVELOPE = re.compile(
    r"^v1\.[A-Za-z0-9_-]{1,32}\.[A-Za-z0-9_-]+={0,2}$"
)
_FORMAT_VERSION = "v1"
_AAD_PREFIX = b"equiconnected/contact-encryption"
_BLIND_INDEX_DOMAIN = b"equiconnected/contact-blind-index/v1"


class ContactEncryptionUnavailable(Exception):
    """Contact persistence cannot proceed because its dedicated keys are invalid."""

    def __init__(
        self,
        message: str = "Contact encryption is not configured.",
        *,
        reason: str = "contact_configuration_invalid",
    ) -> None:
        super().__init__(message)
        # Static categories only: never include key bytes, JSON, IDs or contacts.
        self.reason = reason


class ContactCiphertextInvalid(Exception):
    """Stored contact data is malformed, tampered with, or bound to another record."""


def _key_material() -> tuple[str, dict[str, bytes], bytes]:
    settings = get_settings()
    raw_keyring = settings.CONTACT_ENCRYPTION_KEYRING
    active_id = settings.CONTACT_ENCRYPTION_ACTIVE_KEY_ID
    raw_index_key = settings.CONTACT_BLIND_INDEX_KEY
    if not raw_keyring:
        raise ContactEncryptionUnavailable(reason="contact_keyring_missing")
    if not isinstance(active_id, str) or not _KEY_ID.fullmatch(active_id):
        raise ContactEncryptionUnavailable(reason="contact_active_key_id_invalid")
    reason = "contact_keyring_invalid"
    try:
        decoded_ring = json.loads(raw_keyring)
        if not isinstance(decoded_ring, dict) or not decoded_ring:
            raise ValueError
        keys: dict[str, bytes] = {}
        for key_id, encoded_key in decoded_ring.items():
            reason = "contact_key_id_invalid"
            if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
                raise ValueError
            reason = "contact_key_encoding_invalid"
            if not isinstance(encoded_key, str):
                raise ValueError
            key = base64.b64decode(encoded_key, validate=True)
            reason = "contact_key_length_invalid"
            if len(key) != 32:
                raise ValueError
            keys[key_id] = key
        reason = "contact_active_key_missing"
        if active_id not in keys:
            raise ValueError
        reason = "contact_keys_duplicated"
        if len(set(keys.values())) != len(keys):
            raise ValueError
        reason = "contact_blind_index_missing"
        if not raw_index_key:
            raise ValueError
        reason = "contact_blind_index_encoding_invalid"
        index_key = base64.b64decode(raw_index_key, validate=True)
        reason = "contact_blind_index_length_invalid"
        if len(index_key) != 32:
            raise ValueError
        reason = "contact_blind_index_reuses_contact_key"
        if any(
            hmac.compare_digest(index_key, encryption_key)
            for encryption_key in keys.values()
        ):
            raise ValueError
        peer_keys = _other_application_keys(settings)
        contact_material = (*keys.values(), index_key)
        for source, peer_key in peer_keys:
            if any(
                hmac.compare_digest(contact_key, peer_key)
                for contact_key in contact_material
            ):
                raise ContactEncryptionUnavailable(
                    reason=f"contact_key_reuses_{source}_key"
                )
        return active_id, keys, index_key
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ContactEncryptionUnavailable(reason=reason) from exc


def _other_application_keys(settings: Any) -> tuple[tuple[str, bytes], ...]:
    """Collect comparable peer bytes, not validate another feature's readiness.

    Messaging validates its own configuration before every encrypt/decrypt.
    An unusable optional messaging keyring must not disable contact storage.
    Keep every decodable AES key for reuse checks, including retained keys and
    keys in a partially invalid ring; never substitute these for contact keys.
    """
    peers: list[tuple[str, bytes]] = []
    configured_jwt_key = getattr(settings, "SECRET_KEY", "")
    if configured_jwt_key:
        jwt_key = configured_jwt_key.encode("utf-8")
        peers.append(("jwt", jwt_key))
        try:
            decoded_jwt_key = base64.b64decode(jwt_key, validate=True)
        except (ValueError, binascii.Error):
            decoded_jwt_key = b""
        if decoded_jwt_key:
            peers.append(("jwt", decoded_jwt_key))

    raw_messaging_ring = getattr(settings, "MESSAGING_ENCRYPTION_KEYRING", "")
    if raw_messaging_ring:
        try:
            messaging_ring = json.loads(raw_messaging_ring)
        except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
            messaging_ring = None
        if isinstance(messaging_ring, dict):
            for encoded_key in messaging_ring.values():
                if not isinstance(encoded_key, str):
                    continue
                try:
                    peer_key = base64.b64decode(encoded_key, validate=True)
                except (ValueError, binascii.Error):
                    continue
                if len(peer_key) == 32:
                    peers.append(("messaging", peer_key))
    return tuple(peers)


def ensure_contact_encryption_available() -> None:
    """Validate encryption and blind-index keys without persisting any contacts."""
    _key_material()


def _aad(table: str, record_id: str, field: str) -> bytes:
    return b"\x00".join(
        (
            _AAD_PREFIX,
            _FORMAT_VERSION.encode("ascii"),
            table.encode("utf-8"),
            record_id.encode("utf-8"),
            field.encode("utf-8"),
        )
    )


def encrypt_contact(
    value: str,
    *,
    table: str,
    record_id: str,
    field: str,
) -> str:
    """Return randomized AES-GCM ciphertext authenticated to its row and field."""
    if not isinstance(value, str):
        raise TypeError("Contact values must be strings.")
    if is_contact_ciphertext(value):
        raise ContactCiphertextInvalid("Contact value is already encrypted.")
    active_id, keys, _ = _key_material()
    nonce = urandom(12)
    ciphertext = AESGCM(keys[active_id]).encrypt(
        nonce,
        value.encode("utf-8"),
        _aad(table, str(record_id), field),
    )
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{_FORMAT_VERSION}.{active_id}.{encoded}"


def decrypt_contact(
    envelope: str,
    *,
    table: str,
    record_id: str,
    field: str,
) -> str:
    """Authenticate and decrypt a value; there is intentionally no plaintext fallback."""
    active_id, keys, _ = _key_material()
    del active_id
    try:
        version, key_id, encoded = envelope.split(".", maxsplit=2)
        if version != _FORMAT_VERSION or not _KEY_ID.fullmatch(key_id):
            raise ValueError
        key = keys.get(key_id)
        if key is None:
            raise ContactEncryptionUnavailable(
                reason="contact_ciphertext_key_missing"
            )
        packed = base64.b64decode(encoded, altchars=b"-_", validate=True)
        if len(packed) < 12 + 16:
            raise ValueError
        cleartext = AESGCM(key).decrypt(
            packed[:12],
            packed[12:],
            _aad(table, str(record_id), field),
        )
        return cleartext.decode("utf-8")
    except ContactEncryptionUnavailable:
        raise
    except (ValueError, UnicodeDecodeError, binascii.Error, InvalidTag) as exc:
        raise ContactCiphertextInvalid(
            "Stored contact data could not be authenticated."
        ) from exc


def normalize_contact(value: str, *, field: str) -> str:
    """Normalize only for equality lookup; the original contact remains encrypted."""
    normalized = value.strip()
    if "email" in field.lower():
        normalized = normalized.lower()
    return normalized


def contact_blind_index(value: str, *, table: str, field: str) -> str:
    """Create a domain-separated HMAC blind index for exact matching."""
    if not isinstance(value, str):
        raise TypeError("Contact values must be strings.")
    _, _, index_key = _key_material()
    normalized = normalize_contact(value, field=field).encode("utf-8")
    domain = b"\x00".join(
        (_BLIND_INDEX_DOMAIN, table.encode("utf-8"), field.encode("utf-8"))
    )
    return hmac.new(index_key, domain + b"\x00" + normalized, hashlib.sha256).hexdigest()


def is_contact_ciphertext(value: Any) -> bool:
    """Recognize a well-formed encrypted envelope or reserved packed value."""
    if not isinstance(value, str):
        return False
    if value.startswith("ecv1:"):
        return True
    if not _CONTACT_ENVELOPE.fullmatch(value):
        return False
    try:
        _version, _key_id, encoded = value.split(".", maxsplit=2)
        packed = base64.b64decode(encoded, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        return False
    return len(packed) >= 12 + 16