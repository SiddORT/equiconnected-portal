"""Isolated backend worker for check-private-messaging-isolated-browser.py.

This is not an application entry point. The parent smoke harness starts it as
a disposable process with PGOPTIONS pinned to a uniquely-owned schema. SMTP
message methods are replaced before importing the FastAPI application.
"""
from __future__ import annotations

import argparse
import os
import re


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--key-mode", choices=("valid", "missing", "invalid"), default="valid")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not re.fullmatch(r"pm_smoke_[a-z0-9_]{1,48}", args.schema):
        print("Refusing to start without a smoke-owned schema.", flush=True)
        return 2

    from app.core.config import get_settings

    get_settings()
    # Fail closed if the required parent-process schema pin was lost.
    if os.environ.get("PGOPTIONS") != f"-csearch_path={args.schema}":
        print("Refusing to start because the isolated schema pin is missing.", flush=True)
        return 2

    from sqlalchemy import event, text

    from app.db.session import engine

    @event.listens_for(engine, "connect")
    def _pin_isolated_schema(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute(f'SET search_path TO "{args.schema}"')
        cursor.close()
        dbapi_connection.commit()

    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT current_schema()")).scalar_one() != args.schema:
                print("Refusing to start because database connections are not isolated.", flush=True)
                return 2
    except Exception:
        print("Unable to validate the isolated backend database.", flush=True)
        return 2

    # SMTP methods are patched before app.main or messaging_notifications can
    # be imported. The only retained state is an aggregate method-call count.
    from app.services.email_service import EmailService

    smtp_events = {"count": 0}

    def _record_only(self, *args, **kwargs):
        del self, args, kwargs
        smtp_events["count"] += 1
        return None

    for method_name in (
        "_deliver",
        "send_member_message_acknowledgement",
        "send_provider_message_notification",
        "send_member_reply_notification",
    ):
        setattr(EmailService, method_name, _record_only)

    if args.key_mode != "valid":
        from app.services import messaging_encryption

        protected_settings = messaging_encryption.get_settings()
        if args.key_mode == "missing":
            test_settings = protected_settings.model_copy(
                update={
                    "MESSAGING_ENCRYPTION_KEYRING": "",
                    "MESSAGING_ENCRYPTION_ACTIVE_KEY_ID": "",
                }
            )
        else:
            # Deliberately invalid configuration, not key material. The real
            # protected settings remain untouched in the environment.
            test_settings = protected_settings.model_copy(
                update={
                    "MESSAGING_ENCRYPTION_KEYRING": "not-json",
                    "MESSAGING_ENCRYPTION_ACTIVE_KEY_ID": "smoke-invalid",
                }
            )
        messaging_encryption.get_settings = lambda: test_settings
    else:
        try:
            from app.services.messaging_encryption import ensure_encryption_available

            ensure_encryption_available()
        except Exception:
            print("Protected messaging encryption configuration is unavailable.", flush=True)
            return 2

    from app.main import app
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    if not isinstance(app, FastAPI):
        print("Unable to initialize isolated FastAPI application.", flush=True)
        return 2

    @app.get("/_smoke/smtp-event-count", include_in_schema=False)
    def smtp_event_count():
        return JSONResponse({"count": smtp_events["count"]})

    print(f"READY port={args.port} schema={args.schema} key_mode={args.key_mode}", flush=True)
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="critical",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())