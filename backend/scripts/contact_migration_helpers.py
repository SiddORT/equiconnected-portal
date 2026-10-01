"""Contact snapshot protection and bounded historical-copy cleanup helpers."""
from __future__ import annotations

import re
from typing import Any

from app.services.contact_encryption import (
    ContactCiphertextInvalid,
    decrypt_contact,
    encrypt_contact,
    is_contact_ciphertext,
)


SNAPSHOT_CONTACT_KEYS = {
    "email",
    "contact_email",
    "recipient_email",
    "submitter_email",
    "actor_email",
    "phone",
    "contact_phone",
    "mobile_number",
    "telephone",
    "emergency_contact_number",
}
EMAIL_TEXT_RE = re.compile(
    r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
    r"[A-Z]{2,63}(?![\w.-])",
    re.IGNORECASE,
)
PHONE_TEXT_RE = re.compile(
    r"(?<!\w)(?=[+()\d][+()\d\s.-]*\d)"
    r"\+?(?:\d[\d\s().-]{5,}\d)(?!\w)"
)
SENSITIVE_AUDIT_KEY_PARTS = (
    "email",
    "phone",
    "telephone",
    "mobile",
    "contact",
    "recipient",
)
AUDIT_NAME_KEYS = {"name", "provider_name", "actor_name", "submitter_name"}


def _snapshot_contact_key(key: str, parents: tuple[str, ...]) -> bool:
    lowered = key.lower()
    if lowered in SNAPSHOT_CONTACT_KEYS or lowered.endswith(("_email", "_phone")):
        return True
    return lowered == "number" and bool(parents) and parents[-1].lower() == "phones"


def _walk_snapshot(
    value: Any,
    *,
    table: str,
    record_id: str,
    column: str,
    path: tuple[str, ...] = (),
    parents: tuple[str, ...] = (),
    encrypt_plaintext: bool = True,
) -> tuple[Any, int, int]:
    """Authenticate existing JSON envelopes and encrypt plaintext contact leaves."""
    if isinstance(value, dict):
        result = {}
        plain_count = 0
        encrypted_count = 0
        for key, child in value.items():
            transformed, plain, encrypted = _walk_snapshot(
                child,
                table=table,
                record_id=record_id,
                column=column,
                path=path + (str(key),),
                parents=parents + (str(key),),
                encrypt_plaintext=encrypt_plaintext,
            )
            result[key] = transformed
            plain_count += plain
            encrypted_count += encrypted
        return result, plain_count, encrypted_count
    if isinstance(value, list):
        result = []
        plain_count = 0
        encrypted_count = 0
        for index, child in enumerate(value):
            transformed, plain, encrypted = _walk_snapshot(
                child,
                table=table,
                record_id=record_id,
                column=column,
                path=path + (str(index),),
                parents=parents,
                encrypt_plaintext=encrypt_plaintext,
            )
            result.append(transformed)
            plain_count += plain
            encrypted_count += encrypted
        return result, plain_count, encrypted_count
    if not path or not _snapshot_contact_key(path[-1], parents[:-1]):
        return value, 0, 0
    if value is None:
        return None, 0, 0
    if not isinstance(value, str):
        raise ContactCiphertextInvalid(
            "Contact snapshot values must be strings or null."
        )
    bound_field = f"{column}:{'.'.join(path)}"
    if is_contact_ciphertext(value):
        decrypt_contact(
            value,
            table=table,
            record_id=record_id,
            field=bound_field,
        )
        return value, 0, 1
    if not encrypt_plaintext:
        return value, 1, 0
    return (
        encrypt_contact(
            value,
            table=table,
            record_id=record_id,
            field=bound_field,
        ),
        1,
        0,
    )


def _redact_audit_value(value: Any, key: str | None = None) -> tuple[Any, int]:
    """Remove known contact-bearing audit metadata without logging its values."""
    if key and any(part in key.lower() for part in SENSITIVE_AUDIT_KEY_PARTS):
        if value is None or value == "[redacted]":
            return value, 0
        return "[redacted]", 1
    if isinstance(value, dict):
        result = {}
        count = 0
        changed_contact = str(value.get("field", "")).lower()
        is_contact_change = any(
            part in changed_contact
            for part in SENSITIVE_AUDIT_KEY_PARTS
        )
        for child_key, child in value.items():
            if (
                is_contact_change
                and str(child_key).lower() in {"before", "after"}
                and child is not None
                and child != "[redacted]"
            ):
                result[child_key] = "[redacted]"
                count += 1
                continue
            result[child_key], changed = _redact_audit_value(
                child, str(child_key)
            )
            count += changed
        return result, count
    if isinstance(value, list):
        result = []
        count = 0
        for child in value:
            transformed, changed = _redact_audit_value(child, key)
            result.append(transformed)
            count += changed
        return result, count
    if isinstance(value, str):
        if key and key.lower() == "summary":
            redacted = EMAIL_TEXT_RE.sub("[redacted]", value)
            redacted = PHONE_TEXT_RE.sub("[redacted]", redacted)
            return redacted, int(redacted != value)
        if (
            key
            and key.lower() in AUDIT_NAME_KEYS
            and EMAIL_TEXT_RE.fullmatch(value.strip())
        ):
            return "[redacted]", 1
        return value, 0
    return value, 0


def _generated_name_replacements(
    spec: Any,
    row: dict[str, Any],
    decrypted_fields: dict[str, str | None],
) -> dict[str, str]:
    """Replace only inventoried email-generated display-name fallbacks."""
    replacements: dict[str, str] = {}
    for name_field, email_field, fallback in spec.name_email_fallbacks:
        candidate = row.get(name_field)
        email = decrypted_fields.get(email_field)
        if not isinstance(candidate, str) or not isinstance(email, str):
            continue
        if not EMAIL_TEXT_RE.fullmatch(email.strip()):
            continue
        is_exact_copy = candidate == email
        is_truncated_copy = len(candidate) == 200 and email.startswith(candidate)
        if is_exact_copy or is_truncated_copy:
            if fallback == "actor_type":
                actor_type = str(row.get("actor_type", "")).lower()
                replacement = {
                    "member": "Member",
                    "admin": "Administrator",
                }.get(actor_type, "Account holder")
            else:
                replacement = fallback
            replacements[name_field] = replacement
    return replacements


def _redact_snapshot_email_name_copy(
    value: Any,
    *,
    table: str,
    record_id: str,
    column: str,
) -> tuple[Any, int]:
    """Replace a snapshot's name only when it exactly duplicates its own email."""
    if not isinstance(value, dict) or not isinstance(value.get("name"), str):
        return value, 0
    email_values: set[str] = set()

    def collect(
        current: Any,
        path: tuple[str, ...] = (),
        parents: tuple[str, ...] = (),
    ) -> None:
        if isinstance(current, dict):
            for key, child in current.items():
                next_path = path + (str(key),)
                next_parents = parents + (str(key),)
                if (
                    _snapshot_contact_key(str(key), parents)
                    and "email" in str(key).lower()
                ):
                    if isinstance(child, str):
                        if is_contact_ciphertext(child):
                            cleartext = decrypt_contact(
                                child,
                                table=table,
                                record_id=record_id,
                                field=f"{column}:{'.'.join(next_path)}",
                            )
                        else:
                            cleartext = child
                        if EMAIL_TEXT_RE.fullmatch(cleartext.strip()):
                            email_values.add(cleartext)
                    continue
                collect(child, next_path, next_parents)
        elif isinstance(current, list):
            for index, child in enumerate(current):
                collect(child, path + (str(index),), parents)

    collect(value)
    if value["name"] not in email_values:
        return value, 0
    updated = dict(value)
    updated["name"] = "Invited provider"
    return updated, 1