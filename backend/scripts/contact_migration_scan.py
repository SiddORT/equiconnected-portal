"""Bounded preflight scanning and conflict helpers for contact conversion."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from app.db.contact_types import (
    EncryptedContactValue,
    _unpack_bound_value,
    contact_blind_index,
)
from app.services.contact_encryption import (
    ContactCiphertextInvalid,
    ContactEncryptionUnavailable,
    decrypt_contact,
    is_contact_ciphertext,
)
from contact_migration_helpers import (
    _generated_name_replacements,
    _redact_audit_value,
    _redact_snapshot_email_name_copy,
    _walk_snapshot,
)

ACTIVE_INVITATION_STATUSES = {"PENDING", "ACCEPTED"}


@dataclass
class ScanResult:
    rows_examined: int = 0
    scalar_values: int = 0
    scalar_plaintext: int = 0
    scalar_authenticated: int = 0
    missing_indexes: int = 0
    index_mismatches: int = 0
    invalid_scalars: int = 0
    snapshot_values: int = 0
    snapshot_plaintext: int = 0
    snapshot_authenticated: int = 0
    invalid_snapshots: int = 0
    generated_contact_copies: int = 0
    audit_metadata_contacts: int = 0
    conflict_groups: int = 0
    duplicate_rows: int = 0
    tables: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def remaining_plaintext(self) -> int:
        return (
            self.scalar_plaintext
            + self.snapshot_plaintext
            + self.generated_contact_copies
            + self.audit_metadata_contacts
        )

    @property
    def validation_errors(self) -> int:
        return (
            self.index_mismatches
            + self.invalid_scalars
            + self.invalid_snapshots
            + self.conflict_groups
        )

    @property
    def verified(self) -> bool:
        return (
            self.remaining_plaintext == 0
            and self.missing_indexes == 0
            and self.validation_errors == 0
        )

    def progress_payload(self) -> dict[str, Any]:
        return {
            "rows_examined": self.rows_examined,
            "scalar_values": self.scalar_values,
            "scalar_plaintext": self.scalar_plaintext,
            "scalar_authenticated": self.scalar_authenticated,
            "missing_indexes": self.missing_indexes,
            "index_mismatches": self.index_mismatches,
            "invalid_scalars": self.invalid_scalars,
            "snapshot_values": self.snapshot_values,
            "snapshot_plaintext": self.snapshot_plaintext,
            "snapshot_authenticated": self.snapshot_authenticated,
            "invalid_snapshots": self.invalid_snapshots,
            "generated_contact_copies": self.generated_contact_copies,
            "audit_metadata_contacts": self.audit_metadata_contacts,
            "conflict_groups": self.conflict_groups,
            "duplicate_rows": self.duplicate_rows,
            "remaining_plaintext": self.remaining_plaintext,
            "validation_errors": self.validation_errors,
            "verified": self.verified,
        }


class SchemaNotReady(RuntimeError):
    """The schema revision required by the conversion tool is not installed."""


def record_id(spec: Any, row: dict[str, Any]) -> str:
    values = [
        (column.name, str(row[column.name]))
        for column in spec.primary_key_columns
    ]
    if len(values) == 1:
        return values[0][1]
    return json.dumps(values, separators=(",", ":"), ensure_ascii=True)


def raw_rows(
    connection: Connection,
    spec: Any,
    *,
    after: str | None,
    batch_size: int,
    lock_rows: bool = False,
) -> list[dict[str, Any]]:
    table = spec.table
    primary_key = spec.identity_column
    selections = [f"{primary_key.name}::text AS {primary_key.name}"]
    primary_key_names = {column.name for column in spec.primary_key_columns}
    selections.extend(spec.scalar_fields)
    selections.extend(
        f"{name}_blind_index" for name in spec.scalar_fields
    )
    selections.extend(spec.snapshot_fields)
    for name_field, _email_field, _fallback in spec.name_email_fallbacks:
        if name_field not in selections:
            selections.append(name_field)
    selections.extend(spec.redaction_fields)
    selections.extend(
        name
        for name in ("status", "provider_id", "provider_type", "actor_type")
        if name in table.c
        and name not in selections
        and name not in primary_key_names
    )
    where = ""
    parameters: dict[str, Any] = {"limit": batch_size}
    if after is not None:
        where = (
            f"WHERE {table.name}.{primary_key.name} > CAST(:after AS uuid)"
        )
        parameters["after"] = after
    sql = (
        f"SELECT {', '.join(selections)} FROM {table.name} {where} "
        f"ORDER BY {table.name}.{primary_key.name} LIMIT :limit"
    )
    if lock_rows:
        sql += " FOR UPDATE"
    result = connection.execute(text(sql), parameters)
    rows = [dict(row._mapping) for row in result]
    result.close()
    return rows


def schema_is_ready(engine: Engine, table_specs: Iterable[Any]) -> None:
    table_specs = tuple(table_specs)
    inspector = inspect(engine)
    required_tables = {spec.table.name for spec in table_specs}
    required_tables.add("contact_encryption_migration_state")
    missing_tables = required_tables - set(inspector.get_table_names())
    if missing_tables:
        raise SchemaNotReady("Contact encryption schema is incomplete.")
    for spec in table_specs:
        columns = {
            column["name"]
            for column in inspector.get_columns(spec.table.name, schema=None)
        }
        required_columns = {
            *(column.name for column in spec.primary_key_columns),
            *spec.scalar_fields,
            *(f"{name}_blind_index" for name in spec.scalar_fields),
            *spec.snapshot_fields,
            *(name for name, _email, _fallback in spec.name_email_fallbacks),
            *spec.redaction_fields,
        }
        if not required_columns.issubset(columns):
            raise SchemaNotReady("Contact encryption schema is incomplete.")
    expected_guard_tables = {
        spec.table.name
        for spec in table_specs
        if spec.scalar_fields
        or spec.snapshot_fields
        or spec.redaction_fields
        or spec.name_email_fallbacks
    }
    with engine.connect() as connection:
        guards = connection.execute(
            text(
                """
                SELECT c.relname AS table_name, t.tgname AS trigger_name
                FROM pg_trigger AS t
                JOIN pg_class AS c ON c.oid = t.tgrelid
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                JOIN pg_proc AS p ON p.oid = t.tgfoid
                WHERE NOT t.tgisinternal
                  AND n.nspname = current_schema()
                  AND p.proname = 'reject_plaintext_contact_write'
                  AND t.tgenabled IN ('O', 'A')
                """
            )
        ).all()
    actual_guards = {(row.table_name, row.trigger_name) for row in guards}
    expected_guards = {
        (table_name, f"trg_{table_name}_contact_write_guard")
        for table_name in expected_guard_tables
    }
    if not expected_guards.issubset(actual_guards):
        raise SchemaNotReady("Contact plaintext-write guards are not installed.")


def create_conflict_table(connection: Connection) -> None:
    connection.execute(
        text("DROP TABLE IF EXISTS pg_temp.contact_migration_unique_values")
    )
    connection.execute(
        text(
            """
            CREATE TEMP TABLE contact_migration_unique_values (
                rule text NOT NULL,
                identity text NOT NULL
            ) ON COMMIT DROP
            """
        )
    )


def flush_conflict_rows(
    connection: Connection, values: list[dict[str, str]]
) -> None:
    if not values:
        return
    connection.execute(
        text(
            """
            INSERT INTO contact_migration_unique_values (rule, identity)
            VALUES (:rule, :identity)
            """
        ),
        values,
    )
    values.clear()


def scan_scalar_value(
    value: Any,
    index_value: Any,
    *,
    table: str,
    record_id: str,
    field_name: str,
) -> tuple[str | None, str | None, str]:
    """Return cleartext, expected index, and state without exposing values."""
    if value is None:
        if index_value is not None:
            return None, None, "index_mismatch"
        return None, None, "null"
    if not isinstance(value, str):
        return None, None, "invalid"
    if value.startswith("ecv1:"):
        try:
            bound: EncryptedContactValue = _unpack_bound_value(
                value, expected_field=field_name
            )
            if bound.table != table or bound.record_id != record_id:
                return None, None, "invalid"
            cleartext = decrypt_contact(
                bound.ciphertext,
                table=table,
                record_id=record_id,
                field=field_name,
            )
            expected_index = contact_blind_index(
                cleartext, table=table, field=field_name
            )
            if index_value is None:
                return cleartext, expected_index, "missing_index"
            if index_value != expected_index:
                return cleartext, expected_index, "index_mismatch"
            return cleartext, expected_index, "authenticated"
        except (
            ContactCiphertextInvalid,
            ContactEncryptionUnavailable,
            ValueError,
        ):
            return None, None, "invalid"
    if is_contact_ciphertext(value):
        return None, None, "invalid"
    expected_index = contact_blind_index(
        value, table=table, field=field_name
    )
    if index_value is not None and index_value != expected_index:
        return value, expected_index, "index_mismatch"
    return value, expected_index, "plaintext"


def track_uniqueness(
    entries: list[dict[str, str]],
    *,
    table: str,
    field_name: str,
    expected_index: str | None,
    row: dict[str, Any],
) -> None:
    if expected_index is None:
        return
    if table == "users" and field_name == "email":
        entries.append({"rule": "users.email", "identity": expected_index})
    elif table == "subscribers" and field_name == "email":
        entries.append({"rule": "subscribers.email", "identity": expected_index})
    elif table == "provider_invitations" and field_name == "recipient_email":
        status = str(row.get("status", "")).upper()
        if status not in ACTIVE_INVITATION_STATUSES:
            return
        provider_id = row.get("provider_id")
        provider_type = row.get("provider_type")
        if provider_id is not None:
            identity = f"{provider_id}:{expected_index}"
            rule = "provider_invitations.provider_id_email"
        else:
            identity = f"{provider_type}:{expected_index}"
            rule = "provider_invitations.new_provider_type_email"
        entries.append({"rule": rule, "identity": identity})


def scan_contact_data(
    connection: Connection,
    *,
    table_specs: Iterable[Any],
    batch_size: int,
    progress: bool = False,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> ScanResult:
    result = ScanResult()
    create_conflict_table(connection)
    conflict_entries: list[dict[str, str]] = []
    for spec in table_specs:
        table_name = spec.table.name
        table_counts = result.tables.setdefault(
            table_name,
            {"rows_examined": 0, "scalar_values": 0, "snapshots": 0},
        )
        cursor = None
        while True:
            rows = raw_rows(
                connection, spec, after=cursor, batch_size=batch_size
            )
            if not rows:
                break
            for row in rows:
                current_record_id = record_id(spec, row)
                result.rows_examined += 1
                table_counts["rows_examined"] += 1
                decrypted_fields: dict[str, str | None] = {}
                for field_name in spec.scalar_fields:
                    result.scalar_values += 1
                    table_counts["scalar_values"] += 1
                    cleartext, expected, state = scan_scalar_value(
                        row.get(field_name),
                        row.get(f"{field_name}_blind_index"),
                        table=table_name,
                        record_id=current_record_id,
                        field_name=field_name,
                    )
                    decrypted_fields[field_name] = cleartext
                    if state == "plaintext":
                        result.scalar_plaintext += 1
                    elif state == "authenticated":
                        result.scalar_authenticated += 1
                    elif state == "missing_index":
                        result.scalar_authenticated += 1
                        result.missing_indexes += 1
                    elif state == "index_mismatch":
                        result.index_mismatches += 1
                    elif state == "invalid":
                        result.invalid_scalars += 1
                    track_uniqueness(
                        conflict_entries,
                        table=table_name,
                        field_name=field_name,
                        expected_index=expected,
                        row=row,
                    )
                result.generated_contact_copies += len(
                    _generated_name_replacements(spec, row, decrypted_fields)
                )
                for column in spec.snapshot_fields:
                    table_counts["snapshots"] += 1
                    payload = row.get(column)
                    if payload is None:
                        continue
                    try:
                        if spec.snapshot_name_email_fallback:
                            payload, copies = _redact_snapshot_email_name_copy(
                                payload,
                                table=table_name,
                                record_id=current_record_id,
                                column=column,
                            )
                            result.generated_contact_copies += copies
                        _protected, plain_count, encrypted_count = _walk_snapshot(
                            payload,
                            table=table_name,
                            record_id=current_record_id,
                            column=column,
                            encrypt_plaintext=False,
                        )
                        result.snapshot_values += plain_count + encrypted_count
                        result.snapshot_plaintext += plain_count
                        result.snapshot_authenticated += encrypted_count
                    except (
                        ContactCiphertextInvalid,
                        ContactEncryptionUnavailable,
                        TypeError,
                        ValueError,
                    ):
                        result.invalid_snapshots += 1
                for column in spec.redaction_fields:
                    payload = row.get(column)
                    _safe_payload, redactions = _redact_audit_value(payload)
                    result.audit_metadata_contacts += redactions
            flush_conflict_rows(connection, conflict_entries)
            cursor = rows[-1][spec.identity_column.name]
            if progress and emit is not None:
                emit(
                    {
                        "phase": "preview",
                        "table": table_name,
                        "rows_examined": table_counts["rows_examined"],
                    }
                )
        flush_conflict_rows(connection, conflict_entries)
    conflict_summary = connection.execute(
        text(
            """
            SELECT count(*) AS conflict_groups,
                   coalesce(sum(row_count - 1), 0) AS duplicate_rows
            FROM (
                SELECT count(*) AS row_count
                FROM contact_migration_unique_values
                GROUP BY rule, identity
                HAVING count(*) > 1
            ) conflicts
            """
        )
    ).mappings().one()
    result.conflict_groups = int(conflict_summary["conflict_groups"])
    result.duplicate_rows = int(conflict_summary["duplicate_rows"])
    return result