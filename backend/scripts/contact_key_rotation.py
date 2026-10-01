#!/usr/bin/env python3
"""Preview-first contact encryption and blind-index key rotation utility."""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import sys
from typing import Any
from uuid import UUID

from sqlalchemy import and_, create_engine, text
from sqlalchemy.engine import Connection, Engine

import contact_data_migration as migration
from app.db.contact_types import (
    ContactBlindIndex,
    EncryptedContactValue,
    ProtectedContactSnapshot,
    _unpack_bound_value,
    prepare_contact_values,
)
from app.services.contact_encryption import (
    ContactCiphertextInvalid,
    ContactEncryptionUnavailable,
    _key_material,
    decrypt_contact,
    encrypt_contact,
    ensure_contact_encryption_available,
    is_contact_ciphertext,
    normalize_contact,
)

logging.disable(logging.CRITICAL)
logging.getLogger("sqlalchemy.engine").disabled = True

INDEX_DOMAIN = b"equiconnected/contact-blind-index/v1"
ROTATION_APPROVAL = "CONTACT_KEY_ROTATION"
MAINTENANCE_ENV = "CONTACT_ENCRYPTION_MAINTENANCE_WINDOW"
NEXT_INDEX_SECRET = "CONTACT_BLIND_INDEX_NEXT_KEY"


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


def _decode_index_key(encoded: str) -> bytes:
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ContactEncryptionUnavailable(
            "Contact blind-index rotation key is unavailable."
        ) from exc
    if len(key) != 32 or base64.b64encode(key).decode("ascii") != encoded:
        raise ContactEncryptionUnavailable(
            "Contact blind-index rotation key is unavailable."
        )
    return key


def _next_index_key() -> tuple[bytes, bytes]:
    _active_id, encryption_keys, current = _key_material()
    encoded = os.environ.get(NEXT_INDEX_SECRET, "")
    if not encoded:
        raise ContactEncryptionUnavailable(
            "Contact blind-index rotation key is unavailable."
        )
    target = _decode_index_key(encoded)
    if hmac.compare_digest(target, current) or any(
        hmac.compare_digest(target, key) for key in encryption_keys.values()
    ):
        raise ContactEncryptionUnavailable(
            "Contact blind-index rotation key is not independent."
        )
    return current, target


def _index_with_key(value: str, *, table: str, field_name: str, key: bytes) -> str:
    normalized = normalize_contact(value, field=field_name).encode("utf-8")
    domain = b"\x00".join(
        (INDEX_DOMAIN, table.encode("utf-8"), field_name.encode("utf-8"))
    )
    return hmac.new(key, domain + b"\x00" + normalized, hashlib.sha256).hexdigest()


def _active_encryption_key_id() -> str:
    from app.core.config import get_settings

    return get_settings().CONTACT_ENCRYPTION_ACTIVE_KEY_ID


def _snapshot_rotation(
    value: Any,
    *,
    table: str,
    record_id: str,
    column: str,
    active_key_id: str,
    path: tuple[str, ...] = (),
    parents: tuple[str, ...] = (),
    reencrypt: bool = True,
) -> tuple[Any, int, int, int]:
    """Return protected snapshot, old-key count, plaintext count, and total leaves."""
    if isinstance(value, dict):
        result = {}
        old_keys = plaintext = total = 0
        for key, child in value.items():
            transformed, old, plain, count = _snapshot_rotation(
                child,
                table=table,
                record_id=record_id,
                column=column,
                active_key_id=active_key_id,
                path=path + (str(key),),
                parents=parents + (str(key),),
                reencrypt=reencrypt,
            )
            result[key] = transformed
            old_keys += old
            plaintext += plain
            total += count
        return result, old_keys, plaintext, total
    if isinstance(value, list):
        result = []
        old_keys = plaintext = total = 0
        for index, child in enumerate(value):
            transformed, old, plain, count = _snapshot_rotation(
                child,
                table=table,
                record_id=record_id,
                column=column,
                active_key_id=active_key_id,
                path=path + (str(index),),
                parents=parents,
                reencrypt=reencrypt,
            )
            result.append(transformed)
            old_keys += old
            plaintext += plain
            total += count
        return result, old_keys, plaintext, total
    if not path or not migration._snapshot_contact_key(path[-1], parents[:-1]):
        return value, 0, 0, 0
    if value is None:
        return None, 0, 0, 1
    if not isinstance(value, str):
        raise ContactCiphertextInvalid(
            "Contact snapshot values must be strings or null."
        )
    if not is_contact_ciphertext(value):
        return value, 0, 1, 1
    if not value.startswith("v1."):
        raise ContactCiphertextInvalid(
            "Stored contact data has an invalid encrypted representation."
        )
    parts = value.split(".", maxsplit=2)
    if len(parts) != 3:
        raise ContactCiphertextInvalid("Stored contact data could not be authenticated.")
    cleartext = decrypt_contact(
        value,
        table=table,
        record_id=record_id,
        field=f"{column}:{'.'.join(path)}",
    )
    if parts[1] == active_key_id:
        return value, 0, 0, 1
    if not reencrypt:
        return value, 1, 0, 1
    return (
        encrypt_contact(
            cleartext,
            table=table,
            record_id=record_id,
            field=f"{column}:{'.'.join(path)}",
        ),
        1,
        0,
        1,
    )


def _scalar_cleartext(
    value: Any,
    *,
    table: str,
    record_id: str,
    field_name: str,
) -> tuple[str | None, str | None]:
    if value is None or not isinstance(value, str) or not value.startswith("ecv1:"):
        raise ContactCiphertextInvalid(
            "Contact data is not in authenticated encrypted storage."
        )
    bound: EncryptedContactValue = _unpack_bound_value(
        value, expected_field=field_name
    )
    if bound.table != table or bound.record_id != record_id:
        raise ContactCiphertextInvalid(
            "Stored contact data is bound to a different record or field."
        )
    cleartext = decrypt_contact(
        bound.ciphertext,
        table=table,
        record_id=record_id,
        field=field_name,
    )
    parts = bound.ciphertext.split(".", maxsplit=2)
    if len(parts) != 3 or parts[0] != "v1":
        raise ContactCiphertextInvalid(
            "Stored contact data could not be authenticated."
        )
    return cleartext, parts[1]


def _state_is_complete(engine: Engine) -> bool:
    with engine.connect() as connection:
        result = connection.execute(
            text(
                """
                SELECT state = 'complete' AND cutover_completed_at IS NOT NULL
                FROM contact_encryption_migration_state
                WHERE id = 1
                """
            )
        ).scalar_one_or_none()
    return bool(result)


def _scan_rotation(
    connection: Connection,
    *,
    mode: str,
    batch_size: int,
) -> dict[str, int | bool]:
    active_key_id = _active_encryption_key_id()
    if mode == "index":
        current_index_key, target_index_key = _next_index_key()
    else:
        _active, _keys, current_index_key = _key_material()
        target_index_key = current_index_key
    migration._create_conflict_table(connection)
    conflict_entries: list[dict[str, str]] = []
    summary: dict[str, int | bool] = {
        "rows_examined": 0,
        "scalar_values": 0,
        "snapshot_values": 0,
        "encryption_values_pending": 0,
        "index_values_pending": 0,
        "index_values_already_rotated": 0,
        "index_mismatches": 0,
        "invalid_values": 0,
        "plaintext_values": 0,
        "conflict_groups": 0,
        "duplicate_rows": 0,
    }
    for spec in migration.TABLES:
        cursor = None
        while True:
            rows = migration._raw_rows(
                connection, spec, after=cursor, batch_size=batch_size
            )
            if not rows:
                break
            for row in rows:
                record_id = migration._record_id(spec, row)
                summary["rows_examined"] = int(summary["rows_examined"]) + 1
                for field_name in spec.scalar_fields:
                    value = row.get(field_name)
                    index_value = row.get(f"{field_name}_blind_index")
                    if value is None:
                        if index_value is not None:
                            summary["index_mismatches"] = int(summary["index_mismatches"]) + 1
                        continue
                    summary["scalar_values"] = int(summary["scalar_values"]) + 1
                    try:
                        cleartext, key_id = _scalar_cleartext(
                            value,
                            table=spec.table.name,
                            record_id=record_id,
                            field_name=field_name,
                        )
                    except (ContactCiphertextInvalid, ContactEncryptionUnavailable, ValueError):
                        summary["invalid_values"] = int(summary["invalid_values"]) + 1
                        continue
                    if mode == "encryption":
                        expected_index = _index_with_key(
                            cleartext,
                            table=spec.table.name,
                            field_name=field_name,
                            key=current_index_key,
                        )
                        if index_value != expected_index:
                            summary["index_mismatches"] = int(summary["index_mismatches"]) + 1
                        if key_id != active_key_id:
                            summary["encryption_values_pending"] = (
                                int(summary["encryption_values_pending"]) + 1
                            )
                        target_index = expected_index
                    else:
                        old_index = _index_with_key(
                            cleartext,
                            table=spec.table.name,
                            field_name=field_name,
                            key=current_index_key,
                        )
                        target_index = _index_with_key(
                            cleartext,
                            table=spec.table.name,
                            field_name=field_name,
                            key=target_index_key,
                        )
                        if index_value == old_index:
                            summary["index_values_pending"] = (
                                int(summary["index_values_pending"]) + 1
                            )
                        elif index_value == target_index:
                            summary["index_values_already_rotated"] = (
                                int(summary["index_values_already_rotated"]) + 1
                            )
                        else:
                            summary["index_mismatches"] = int(summary["index_mismatches"]) + 1
                    migration._track_uniqueness(
                        conflict_entries,
                        table=spec.table.name,
                        field_name=field_name,
                        expected_index=target_index,
                        row=row,
                    )
                for column in spec.snapshot_fields:
                    payload = row.get(column)
                    if payload is None:
                        continue
                    try:
                        _transformed, old, plaintext, count = _snapshot_rotation(
                            payload,
                            table=spec.table.name,
                            record_id=record_id,
                            column=column,
                            active_key_id=active_key_id,
                            reencrypt=False,
                        )
                        summary["snapshot_values"] = int(summary["snapshot_values"]) + count
                        summary["encryption_values_pending"] = (
                            int(summary["encryption_values_pending"]) + old
                        )
                        summary["plaintext_values"] = (
                            int(summary["plaintext_values"]) + plaintext
                        )
                    except (ContactCiphertextInvalid, ContactEncryptionUnavailable, TypeError, ValueError):
                        summary["invalid_values"] = int(summary["invalid_values"]) + 1
                if mode == "index":
                    migration._flush_conflict_rows(connection, conflict_entries)
            migration._flush_conflict_rows(connection, conflict_entries)
            cursor = rows[-1][spec.identity_column.name]
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
    summary["conflict_groups"] = int(conflict_summary["conflict_groups"])
    summary["duplicate_rows"] = int(conflict_summary["duplicate_rows"])
    summary["verified"] = (
        summary["index_mismatches"] == 0
        and summary["invalid_values"] == 0
        and summary["plaintext_values"] == 0
        and summary["conflict_groups"] == 0
        and (
            mode != "index"
            or summary["index_values_pending"] == 0
        )
        and (
            mode != "encryption"
            or summary["encryption_values_pending"] == 0
        )
    )
    return summary


def preview(engine: Engine, mode: str, batch_size: int) -> dict[str, int | bool]:
    migration._check_database_schema(engine)
    ensure_contact_encryption_available()
    if not _state_is_complete(engine):
        raise PermissionError("Contact-data cutover has not been completed.")
    with engine.connect() as connection:
        with connection.begin():
            return _scan_rotation(
                connection, mode=mode, batch_size=batch_size
            )


def _rotate_scalar_row(
    spec: migration.TableSpec,
    row: dict[str, Any],
    *,
    mode: str,
    active_key_id: str,
    current_index_key: bytes,
    target_index_key: bytes,
) -> dict[Any, Any]:
    record_id = migration._record_id(spec, row)
    updates: dict[Any, Any] = {}
    for field_name in spec.scalar_fields:
        value = row.get(field_name)
        if value is None:
            continue
        cleartext, key_id = _scalar_cleartext(
            value,
            table=spec.table.name,
            record_id=record_id,
            field_name=field_name,
        )
        index_column = spec.table.c[f"{field_name}_blind_index"]
        if mode == "encryption" and key_id != active_key_id:
            updates.update(
                prepare_contact_values(
                    spec.model, record_id, {field_name: cleartext}
                )
            )
        elif mode == "index":
            current_value = _index_with_key(
                cleartext,
                table=spec.table.name,
                field_name=field_name,
                key=current_index_key,
            )
            target_value = _index_with_key(
                cleartext,
                table=spec.table.name,
                field_name=field_name,
                key=target_index_key,
            )
            if row.get(f"{field_name}_blind_index") == current_value:
                updates[index_column] = ContactBlindIndex(target_value)
            elif row.get(f"{field_name}_blind_index") != target_value:
                raise ValueError("Blind-index rotation preflight failed.")
    return updates


def rotate(engine: Engine, mode: str, batch_size: int) -> dict[str, int | bool]:
    migration._check_database_schema(engine)
    ensure_contact_encryption_available()
    if not _state_is_complete(engine):
        raise PermissionError("Contact-data cutover has not been completed.")
    if mode == "index":
        current_index_key, target_index_key = _next_index_key()
    else:
        _active, _keys, current_index_key = _key_material()
        target_index_key = current_index_key
    preflight = preview(engine, mode, batch_size)
    if preflight["index_mismatches"] or preflight["invalid_values"] or preflight["conflict_groups"] or preflight["plaintext_values"]:
        raise ValueError("Rotation preview found validation failures.")
    with engine.begin() as connection:
        connection.execute(
            text(
                "LOCK TABLE "
                + ", ".join(spec.table.name for spec in migration.TABLES)
                + " IN ACCESS EXCLUSIVE MODE"
            )
        )
        locked_preflight = _scan_rotation(
            connection, mode=mode, batch_size=batch_size
        )
        if (
            locked_preflight["index_mismatches"]
            or locked_preflight["invalid_values"]
            or locked_preflight["conflict_groups"]
            or locked_preflight["plaintext_values"]
        ):
            raise ValueError("Rotation preflight changed; no rotation was applied.")
    active_key_id = _active_encryption_key_id()
    for spec in migration.TABLES:
        cursor = None
        table_rows_examined = 0
        while True:
            with engine.begin() as connection:
                rows = migration._raw_rows(
                    connection,
                    spec,
                    after=cursor,
                    batch_size=batch_size,
                    lock_rows=True,
                )
                if not rows:
                    break
                for row in rows:
                    record_id = migration._record_id(spec, row)
                    updates = _rotate_scalar_row(
                        spec,
                        row,
                        mode=mode,
                        active_key_id=active_key_id,
                        current_index_key=current_index_key,
                        target_index_key=target_index_key,
                    )
                    for column in spec.snapshot_fields:
                        payload = row.get(column)
                        if payload is None:
                            continue
                        transformed, _old, _plain, _total = _snapshot_rotation(
                            payload,
                            table=spec.table.name,
                            record_id=record_id,
                            column=column,
                            active_key_id=active_key_id,
                        )
                        if mode == "encryption" and transformed != payload:
                            updates[spec.table.c[column]] = ProtectedContactSnapshot(
                                transformed,
                                spec.table.name,
                                record_id,
                                column,
                            )
                    if updates:
                        connection.execute(
                            spec.table.update()
                            .where(
                                and_(
                                    *(
                                        primary_key == UUID(str(row[primary_key.name]))
                                        for primary_key in spec.primary_key_columns
                                    )
                                )
                            )
                            .values(updates)
                        )
                cursor = rows[-1][spec.identity_column.name]
                table_rows_examined += len(rows)
            emit(
                {
                    "phase": "rotation",
                    "mode": mode,
                    "table": spec.table.name,
                    "rows_examined": table_rows_examined,
                }
            )
    result = preview(engine, mode, batch_size)
    if not result["verified"]:
        raise ValueError("Rotation verification failed.")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview and rotate contact encryption or blind-index keys."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_name in ("preview", "verify", "rotate"):
        command = subparsers.add_parser(command_name)
        command.add_argument(
            "--mode",
            choices=("encryption", "index"),
            required=True,
        )
        command.add_argument("--batch-size", type=int, default=500)
        if command_name == "rotate":
            command.add_argument("--confirm", default="")
            command.add_argument("--production-approval", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.batch_size <= 5000:
        emit({"status": "error", "code": "invalid_batch_size"})
        return 2
    try:
        from app.core.config import get_settings

        settings = get_settings()
        if args.command == "rotate":
            if args.confirm != ROTATION_APPROVAL:
                raise PermissionError("Explicit key-rotation approval is required.")
            if os.environ.get(MAINTENANCE_ENV) != "1":
                raise PermissionError("The contact-encryption maintenance window is not enabled.")
            is_production = (
                settings.ENVIRONMENT == "production"
                or os.environ.get("REPLIT_DEPLOYMENT") == "1"
            )
            if is_production and not args.production_approval:
                raise PermissionError("Production operator approval record is required.")
            if args.production_approval and len(args.production_approval) > 120:
                raise PermissionError("Production operator approval record is invalid.")
        engine = create_engine(
            settings.DATABASE_URL,
            echo=False,
            hide_parameters=True,
            pool_pre_ping=True,
        )
        if args.command == "preview":
            result = preview(engine, args.mode, args.batch_size)
            emit({"phase": "rotation_preview", "mode": args.mode, **result})
            engine.dispose()
            return 0 if result["index_mismatches"] == 0 and result["invalid_values"] == 0 else 3
        if args.command == "verify":
            result = preview(engine, args.mode, args.batch_size)
            emit({"phase": "rotation_verification", "mode": args.mode, **result})
            engine.dispose()
            return 0 if result["verified"] else 3
        result = rotate(engine, args.mode, args.batch_size)
        emit({"phase": "rotation_complete", "mode": args.mode, **result})
        engine.dispose()
        return 0 if result["verified"] else 3
    except KeyboardInterrupt:
        emit(
            {
                "status": "interrupted",
                "resume": "retain all key versions; preview before resuming",
            }
        )
        return 130
    except PermissionError as exc:
        emit(
            {
                "status": "refused",
                "code": "operator_approval_required"
                if "approval" in str(exc).lower()
                else "maintenance_or_cutover_required",
            }
        )
        return 4
    except ContactEncryptionUnavailable:
        emit({"status": "error", "code": "contact_encryption_unavailable"})
        return 5
    except migration.SchemaNotReady:
        emit({"status": "error", "code": "contact_schema_not_ready"})
        return 6
    except Exception as exc:
        emit(
            {
                "status": "error",
                "code": "contact_key_rotation_failed",
                "error_class": type(exc).__name__,
            }
        )
        return 7


if __name__ == "__main__":
    sys.exit(main())