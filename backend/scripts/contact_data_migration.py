#!/usr/bin/env python3
"""Operator-only, preview-first conversion of structured contact storage.

The script reports aggregate counts only. It never prints contact values,
ciphertext, blind indexes, connection strings, or encryption material.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import MetaData, and_, create_engine, inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql.elements import conv

from app.db.contact_types import (
    ProtectedContactSnapshot,
    prepare_contact_values,
)
from app.models.contact_enquiry import ContactEnquiry
from app.models.audit_log import AuditLog
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.invitation import ProviderInvitation
from app.models.member_feedback import MemberFeedback, MemberFeedbackAction
from app.models.organization_request import OrganizationRequest
from app.models.profile import StableProfile
from app.models.provider import (
    DirectProviderPortalAccess,
    Provider,
    ProviderEmail,
    ProviderPhone,
    ProviderProfileUpdate,
)
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.provider_review_action import ProviderReviewAction
from app.models.subscriber import Subscriber
from app.models.user import User
from app.services.contact_encryption import (
    ContactCiphertextInvalid,
    ContactEncryptionUnavailable,
    ensure_contact_encryption_available,
)
from contact_migration_scan import (
    ACTIVE_INVITATION_STATUSES,
    ScanResult,
    SchemaNotReady,
    create_conflict_table as _create_conflict_table,
    flush_conflict_rows as _flush_conflict_rows,
    raw_rows as _raw_rows,
    record_id as _record_id,
    scan_contact_data,
    scan_scalar_value as _scan_scalar_value,
    schema_is_ready as _schema_is_ready_impl,
    track_uniqueness as _track_uniqueness,
)
from contact_migration_helpers import (
    _generated_name_replacements,
    _redact_audit_value,
    _redact_snapshot_email_name_copy,
    _snapshot_contact_key,
    _walk_snapshot,
)

logging.disable(logging.CRITICAL)
logging.getLogger("sqlalchemy.engine").disabled = True


@dataclass(frozen=True)
class TableSpec:
    model: type
    scalar_fields: tuple[str, ...] = ()
    snapshot_fields: tuple[str, ...] = ()
    name_email_fallbacks: tuple[tuple[str, str, str], ...] = ()
    redaction_fields: tuple[str, ...] = ()
    snapshot_name_email_fallback: bool = False

    @property
    def table(self):
        return self.model.__table__

    @property
    def primary_key_columns(self):
        return tuple(self.table.primary_key.columns)

    @property
    def identity_column(self):
        if len(self.primary_key_columns) != 1:
            raise ValueError("Contact migration expects one primary-key column per table.")
        return self.primary_key_columns[0]


TABLES = (
    TableSpec(User, ("email", "mobile_number")),
    TableSpec(
        Provider,
        ("email", "phone", "emergency_contact_number"),
        name_email_fallbacks=(("name", "email", "Invited provider"),),
    ),
    TableSpec(ProviderEmail, ("email",)),
    TableSpec(ProviderPhone, ("number",)),
    TableSpec(
        ProviderRegistrationApplication, ("emergency_contact_number",)
    ),
    TableSpec(StableProfile, ("contact_email", "contact_phone")),
    TableSpec(OrganizationRequest, ("contact_email",)),
    TableSpec(ProviderInvitation, ("recipient_email",)),
    TableSpec(DirectProviderPortalAccess, ("recipient_email",)),
    TableSpec(EmailDeliveryLog, ("recipient_email",)),
    TableSpec(ContactEnquiry, ("email", "phone")),
    TableSpec(Subscriber, ("email",)),
    TableSpec(
        MemberFeedback,
        ("submitter_email",),
        name_email_fallbacks=(("submitter_name", "submitter_email", "Member"),),
    ),
    TableSpec(
        MemberFeedbackAction,
        ("actor_email",),
        ("content_snapshot",),
        name_email_fallbacks=(("actor_name", "actor_email", "actor_type"),),
    ),
    TableSpec(
        ProviderProfileUpdate,
        (),
        ("base_profile", "proposed_profile"),
        snapshot_name_email_fallback=True,
    ),
    TableSpec(
        ProviderReviewAction,
        ("actor_email",),
        ("content_snapshot",),
        name_email_fallbacks=(("actor_name", "actor_email", "actor_type"),),
    ),
    TableSpec(AuditLog, redaction_fields=("metadata",)),
)

APPROVAL_TEXT = "CONTACT_DATA_CONVERSION"
MAINTENANCE_ENV = "CONTACT_ENCRYPTION_MAINTENANCE_WINDOW"


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


def _schema_is_ready(engine: Engine) -> None:
    _schema_is_ready_impl(engine, TABLES)


def _scan(
    connection: Connection,
    *,
    batch_size: int,
    progress: bool = False,
) -> ScanResult:
    return scan_contact_data(
        connection,
        table_specs=TABLES,
        batch_size=batch_size,
        progress=progress,
        emit=emit,
    )


def _record_pk_values(spec: TableSpec, row: dict[str, Any]) -> dict[Any, Any]:
    values = {}
    for column in spec.primary_key_columns:
        raw = row[column.name]
        values[column] = UUID(str(raw))
    return values


def _convert_batch(
    connection: Connection,
    spec: TableSpec,
    rows: list[dict[str, Any]],
) -> tuple[int, int, int, int, int]:
    changed_rows = 0
    scalar_changed = 0
    snapshots_changed = 0
    generated_copies_redacted = 0
    audit_metadata_redacted = 0
    for row in rows:
        record_id = _record_id(spec, row)
        scalar_values: dict[str, str | None] = {}
        decrypted_fields: dict[str, str | None] = {}
        for field_name in spec.scalar_fields:
            cleartext, expected, state = _scan_scalar_value(
                row.get(field_name),
                row.get(f"{field_name}_blind_index"),
                table=spec.table.name,
                record_id=record_id,
                field_name=field_name,
            )
            decrypted_fields[field_name] = cleartext
            if state == "invalid" or state == "index_mismatch":
                raise ValueError("The contact preflight identified an invalid row.")
            if state in {"plaintext", "missing_index"}:
                scalar_values[field_name] = cleartext
        updates: dict[Any, Any] = {}
        if scalar_values:
            updates.update(
                prepare_contact_values(
                    spec.model, record_id, scalar_values
                )
            )
            scalar_changed += len(scalar_values)
        for column in spec.snapshot_fields:
            payload = row.get(column)
            if payload is None:
                continue
            snapshot_copies_redacted = 0
            if spec.snapshot_name_email_fallback:
                payload, snapshot_copies_redacted = (
                    _redact_snapshot_email_name_copy(
                        payload,
                        table=spec.table.name,
                        record_id=record_id,
                        column=column,
                    )
                )
                generated_copies_redacted += snapshot_copies_redacted
            protected_payload, plaintext_count, _encrypted_count = _walk_snapshot(
                payload,
                table=spec.table.name,
                record_id=record_id,
                column=column,
            )
            if plaintext_count or snapshot_copies_redacted:
                updates[spec.table.c[column]] = ProtectedContactSnapshot(
                    protected_payload,
                    spec.table.name,
                    record_id,
                    column,
                )
                snapshots_changed += 1
        generated_replacements = _generated_name_replacements(
            spec, row, decrypted_fields
        )
        for field_name, replacement in generated_replacements.items():
            updates[spec.table.c[field_name]] = replacement
            generated_copies_redacted += 1
        for column in spec.redaction_fields:
            payload = row.get(column)
            redacted_payload, redaction_count = _redact_audit_value(payload)
            if redaction_count:
                updates[spec.table.c[column]] = redacted_payload
                audit_metadata_redacted += redaction_count
        if updates:
            result = connection.execute(
                spec.table.update()
                .where(
                    and_(
                        *(
                            column == value
                            for column, value in _record_pk_values(spec, row).items()
                        )
                    )
                )
                .values(updates)
            )
            if result.rowcount != 1:
                raise RuntimeError("A contact row changed during conversion.")
            changed_rows += 1
    return (
        changed_rows,
        scalar_changed,
        snapshots_changed,
        generated_copies_redacted,
        audit_metadata_redacted,
    )


def _update_state(
    connection: Connection,
    *,
    state: str,
    rows_examined: int = 0,
    rows_changed: int = 0,
    scalar_values_encrypted: int = 0,
    snapshots_protected: int = 0,
    historical_copies_redacted: int = 0,
    audit_metadata_redacted: int = 0,
) -> None:
    connection.execute(
        text(
            """
            UPDATE contact_encryption_migration_state
            SET state = :state,
                updated_at = now(),
                rows_examined = rows_examined + :rows_examined,
                rows_changed = rows_changed + :rows_changed,
                scalar_values_encrypted =
                    scalar_values_encrypted + :scalar_values_encrypted,
                snapshots_protected = snapshots_protected + :snapshots_protected,
                historical_copies_redacted =
                    historical_copies_redacted + :historical_copies_redacted,
                audit_metadata_redacted =
                    audit_metadata_redacted + :audit_metadata_redacted
            WHERE id = 1
            """
        ),
        {
            "state": state,
            "rows_examined": rows_examined,
            "rows_changed": rows_changed,
            "scalar_values_encrypted": scalar_values_encrypted,
            "snapshots_protected": snapshots_protected,
            "historical_copies_redacted": historical_copies_redacted,
            "audit_metadata_redacted": audit_metadata_redacted,
        },
    )


def _check_operator_approval(args: argparse.Namespace, environment: str) -> None:
    if args.confirm != APPROVAL_TEXT:
        raise PermissionError("Explicit contact-data mutation approval is required.")
    if os.environ.get(MAINTENANCE_ENV) != "1":
        raise PermissionError("The contact-encryption maintenance window is not enabled.")
    is_production = (
        environment == "production"
        or os.getenv("REPLIT_DEPLOYMENT") == "1"
    )
    if is_production and not args.production_approval:
        raise PermissionError("Production operator approval record is required.")
    if args.production_approval and len(args.production_approval) > 120:
        raise PermissionError("Production operator approval record is invalid.")


def _check_database_schema(engine: Engine) -> None:
    _schema_is_ready(engine)
    inspector = inspect(engine)

    def has_unique(table: str, name: str, columns: list[str]) -> bool:
        constraints = inspector.get_unique_constraints(table)
        indexes = inspector.get_indexes(table)
        return any(
            constraint.get("name") == name
            and constraint.get("column_names") == columns
            for constraint in constraints
        ) or any(
            index.get("name") == name
            and index.get("unique") is True
            and index.get("column_names") == columns
            for index in indexes
        )

    def has_index(
        table: str, name: str, columns: list[str], *, unique: bool
    ) -> bool:
        rendered_name = (
            engine.dialect.identifier_preparer.truncate_and_render_index_name(
                conv(name),
                _alembic_quote=False,
            )
        )
        return any(
            index.get("name") == rendered_name
            and index.get("unique") is unique
            and index.get("column_names") == columns
            for index in inspector.get_indexes(table)
        )

    for spec in TABLES:
        table = spec.table.name
        for field_name in spec.scalar_fields:
            index_column = f"{field_name}_blind_index"
            if table == "users" and field_name == "email":
                exists = has_unique(
                    table, "uq_users_email_blind_index", [index_column]
                )
            elif table == "subscribers" and field_name == "email":
                exists = has_unique(
                    table, "uq_subscribers_email", [index_column]
                )
            else:
                exists = has_index(
                    table,
                    f"ix_{table}_{field_name}_blind_index",
                    [index_column],
                    unique=False,
                )
            if not exists:
                raise SchemaNotReady("Contact indexes are incomplete.")

    if not has_index(
        "provider_invitations",
        "ix_provider_invitations_provider_email_blind_index",
        ["provider_id", "recipient_email_blind_index"],
        unique=False,
    ):
        raise SchemaNotReady("Contact indexes are incomplete.")

    invitation_index = next(
        (
            index
            for index in inspector.get_indexes("provider_invitations")
            if index.get("name")
            == "uq_provider_invitations_active_provider_email"
            and index.get("unique") is True
            and index.get("column_names")
            == ["provider_id", "recipient_email_blind_index"]
        ),
        None,
    )
    predicate = ""
    if invitation_index:
        predicate = str(
            invitation_index.get("dialect_options", {}).get(
                "postgresql_where", ""
            )
        ).upper()
    if (
        invitation_index is None
        or "STATUS" not in predicate
        or "PENDING" not in predicate
        or "ACCEPTED" not in predicate
    ):
        raise SchemaNotReady("Contact uniqueness indexes are incomplete.")


def preview(engine: Engine, batch_size: int) -> ScanResult:
    _check_database_schema(engine)
    ensure_contact_encryption_available()
    with engine.connect() as connection:
        with connection.begin():
            return _scan(connection, batch_size=batch_size, progress=True)


def convert(engine: Engine, batch_size: int) -> dict[str, Any]:
    _check_database_schema(engine)
    ensure_contact_encryption_available()
    with engine.connect() as connection:
        migration_state = connection.execute(
            text(
                "SELECT state FROM contact_encryption_migration_state WHERE id = 1"
            )
        ).scalar_one_or_none()
    if migration_state == "complete":
        raise PermissionError("Contact-data cutover is already complete.")
    preflight = preview(engine, batch_size)
    if preflight.validation_errors:
        raise ValueError("Preview checks failed; conversion was not started.")
    totals = {
        "rows_examined": 0,
        "rows_changed": 0,
        "scalar_values_encrypted": 0,
        "snapshots_protected": 0,
        "historical_copies_redacted": 0,
        "audit_metadata_redacted": 0,
    }
    with engine.begin() as connection:
        _update_state(connection, state="converting")
    for spec in TABLES:
        cursor = None
        table_rows_examined = 0
        while True:
            with engine.begin() as connection:
                rows = _raw_rows(
                    connection,
                    spec,
                    after=cursor,
                    batch_size=batch_size,
                    lock_rows=True,
                )
                if not rows:
                    break
                (
                    changed,
                    scalars,
                    snapshots,
                    historical,
                    audit_redactions,
                ) = _convert_batch(
                    connection, spec, rows
                )
                examined = len(rows)
                _update_state(
                    connection,
                    state="converting",
                    rows_examined=examined,
                    rows_changed=changed,
                    scalar_values_encrypted=scalars,
                    snapshots_protected=snapshots,
                    historical_copies_redacted=historical,
                    audit_metadata_redacted=audit_redactions,
                )
                totals["rows_examined"] += examined
                totals["rows_changed"] += changed
                totals["scalar_values_encrypted"] += scalars
                totals["snapshots_protected"] += snapshots
                totals["historical_copies_redacted"] += historical
                totals["audit_metadata_redacted"] += audit_redactions
                table_rows_examined += examined
                cursor = rows[-1][spec.identity_column.name]
            emit(
                {
                    "phase": "convert",
                    "table": spec.table.name,
                    "rows_examined": table_rows_examined,
                    "rows_changed": totals["rows_changed"],
                }
            )
    final = preview(engine, batch_size)
    return {
        "phase": "convert_complete",
        "conversion": totals,
        "verification": final.progress_payload(),
    }


def verify(engine: Engine, batch_size: int) -> ScanResult:
    _check_database_schema(engine)
    ensure_contact_encryption_available()
    with engine.connect() as connection:
        with connection.begin():
            return _scan(connection, batch_size=batch_size, progress=True)


def complete_cutover(engine: Engine, batch_size: int) -> ScanResult:
    _check_database_schema(engine)
    ensure_contact_encryption_available()
    with engine.begin() as connection:
        connection.execute(
            text(
                "LOCK TABLE "
                + ", ".join(
                    f"{spec.table.name}" for spec in TABLES
                )
                + " IN ACCESS EXCLUSIVE MODE"
            )
        )
        result = _scan(connection, batch_size=batch_size, progress=True)
        if not result.verified:
            raise ValueError("Cutover verification failed; completion was refused.")
        connection.execute(
            text(
                """
                UPDATE contact_encryption_migration_state
                SET state = 'complete',
                    updated_at = now(),
                    verified_at = now(),
                    cutover_completed_at = now()
                WHERE id = 1
                """
            )
        )
    return result


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview, convert, and verify encrypted contact storage."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--batch-size", type=int, default=500)
    for name in ("convert", "complete-cutover"):
        command = subparsers.add_parser(name)
        command.add_argument("--batch-size", type=int, default=500)
        command.add_argument("--confirm", default="")
        command.add_argument(
            "--production-approval",
            default="",
            help="Non-secret approval/ticket reference; required in production.",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _make_parser().parse_args(argv)
    if not 1 <= args.batch_size <= 5000:
        emit({"status": "error", "code": "invalid_batch_size"})
        return 2
    try:
        from app.core.config import get_settings

        settings = get_settings()
        if args.command in {"convert", "complete-cutover"}:
            _check_operator_approval(args, settings.ENVIRONMENT)
        _schema_url = settings.DATABASE_URL
        engine = create_engine(
            _schema_url,
            echo=False,
            hide_parameters=True,
            pool_pre_ping=True,
        )
        if args.command == "preview":
            result = preview(engine, args.batch_size)
            emit({"phase": "preview_complete", **result.progress_payload()})
        elif args.command == "verify":
            result = verify(engine, args.batch_size)
            emit({"phase": "verification_complete", **result.progress_payload()})
            engine.dispose()
            return 0 if result.verified else 3
        elif args.command == "convert":
            result = convert(engine, args.batch_size)
            emit(result)
            engine.dispose()
            return 0 if result["verification"]["verified"] else 3
        else:
            result = complete_cutover(engine, args.batch_size)
            emit(
                {
                    "phase": "cutover_complete",
                    **result.progress_payload(),
                }
            )
        engine.dispose()
        return 0
    except KeyboardInterrupt:
        emit({"status": "interrupted", "resume": "rerun preview then convert"})
        return 130
    except PermissionError as exc:
        emit(
            {
                "status": "refused",
                "code": "operator_approval_required"
                if "approval" in str(exc).lower()
                else "maintenance_window_required",
            }
        )
        return 4
    except ContactEncryptionUnavailable:
        emit({"status": "error", "code": "contact_encryption_unavailable"})
        return 5
    except SchemaNotReady:
        emit({"status": "error", "code": "contact_schema_not_ready"})
        return 6
    except Exception as exc:
        # Exception strings and SQL diagnostics can contain parameter values.
        emit(
            {
                "status": "error",
                "code": "contact_operation_failed",
                "error_class": type(exc).__name__,
            }
        )
        return 7


if __name__ == "__main__":
    sys.exit(main())