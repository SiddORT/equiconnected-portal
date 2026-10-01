"""Check effective encryption configuration without DB access or secret output.

Run from the repository root: python backend/scripts/check_contact_encryption.py
This uses the same cached Settings and validators as the application. It never
generates keys, encrypts data, changes configuration, or opens a DB session.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.contact_encryption import (  # noqa: E402
    ContactEncryptionUnavailable,
    ensure_contact_encryption_available,
)
from app.services.messaging_encryption import (  # noqa: E402
    MessagingEncryptionUnavailable,
    ensure_encryption_available,
)


def main() -> int:
    try:
        ensure_contact_encryption_available()
    except ContactEncryptionUnavailable as exc:
        print(f"Contact encryption: unavailable ({exc.reason}).")
        return 1
    except Exception:
        # Settings validation can contain input values; never print its payload.
        print("Contact encryption: unavailable (application_settings_invalid).")
        return 1

    print("Contact encryption: ready.")
    try:
        ensure_encryption_available()
    except MessagingEncryptionUnavailable:
        print(
            "Private messaging: unavailable (configuration missing or invalid). "
            "Messaging remains fail-closed; contact readiness is independent."
        )
    except Exception:
        print("Private messaging: unavailable (application_settings_invalid).")
        return 1
    else:
        print("Private messaging: ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())