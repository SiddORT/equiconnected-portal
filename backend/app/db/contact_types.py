"""SQLAlchemy storage boundaries for encrypted contact fields and snapshots.

Mapped model attributes remain plaintext-facing for normal ORM use.  The ORM
unit-of-work converts those values to record-bound envelopes before binding;
the TypeDecorator rejects ordinary strings from Core and bulk write paths.
Exact equality is translated to an independent blind-index column.
"""
from __future__ import annotations

import base64
import binascii
import json
import uuid
from typing import Any, Iterable, Mapping

from sqlalchemy import JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DontWrapMixin
from sqlalchemy.sql import operators
from sqlalchemy.types import TypeDecorator

from app.services.contact_encryption import (
    ContactCiphertextInvalid,
    contact_blind_index,
    decrypt_contact,
    encrypt_contact,
    is_contact_ciphertext,
)

_PACKED_VALUE_PREFIX = "ecv1:"
_SNAPSHOT_CONTACT_KEYS = {
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


class ContactPersistenceError(ValueError, DontWrapMixin):
    """An unsafe contact value was supplied to a persistence boundary."""


class EncryptedContactValue:
    """Ciphertext explicitly bound to one table, primary key, and field."""

    __slots__ = ("ciphertext", "table", "record_id", "field")

    def __init__(self, ciphertext: str, table: str, record_id: str, field: str):
        self.ciphertext = ciphertext
        self.table = table
        self.record_id = record_id
        self.field = field


class ProtectedContactSnapshot:
    """JSON snapshot whose recognized contact leaves are encrypted in place."""

    __slots__ = ("payload", "table", "record_id", "column")

    def __init__(
        self, payload: dict[str, Any], table: str, record_id: str, column: str
    ):
        self.payload = payload
        self.table = table
        self.record_id = record_id
        self.column = column

    def __repr__(self) -> str:
        return "<ProtectedContactSnapshot (redacted)>"


class ContactBlindIndex:
    """Opaque validated value accepted by blind-index columns only."""

    __slots__ = ("digest",)

    def __init__(self, digest: str):
        self.digest = digest


class ContactBlindIndexType(TypeDecorator):
    """Block plaintext ORM/Core writes to companion lookup columns."""

    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, ContactBlindIndex):
            raise ContactPersistenceError(
                "Blind-index columns accept keyed index values only."
            )
        digest = value.digest
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ContactPersistenceError("Contact blind index is invalid.")
        return digest

    def process_result_value(self, value, dialect):
        return ContactBlindIndex(value) if value is not None else None


def contact_blind_index_value(
    value: str,
    *,
    table: str,
    field: str,
) -> ContactBlindIndex:
    """Return an opaque HMAC wrapper suitable for a database blind-index column."""
    return ContactBlindIndex(
        contact_blind_index(value, table=table, field=field)
    )


def record_identity(instance: Any) -> str:
    """Return a stable binding identity from all mapped primary-key columns."""
    mapper = instance.__mapper__
    values: list[tuple[str, str]] = []
    for column in mapper.primary_key:
        key = mapper.get_property_by_column(column).key
        value = getattr(instance, key, None)
        if value is None:
            default = column.default
            if default is not None and callable(default.arg):
                try:
                    value = default.arg()
                except TypeError:
                    value = default.arg(None)
                setattr(instance, key, value)
        if value is None:
            raise ContactPersistenceError(
                "Contact persistence requires a primary key before flush."
            )
        values.append((column.name, str(value)))
    if len(values) == 1:
        return values[0][1]
    return json.dumps(values, separators=(",", ":"), ensure_ascii=True)


def encrypted_contact_value(
    value: str,
    *,
    table: str,
    record_id: str,
    field: str,
) -> EncryptedContactValue:
    """Prepare ciphertext for an explicit Core/bulk write.

    The helper is intentionally explicit about table, record ID, and field.
    Use :func:`prepare_contact_values` to include the matching blind index too.
    """
    if not isinstance(value, str):
        raise TypeError("Contact values must be strings.")
    ciphertext = encrypt_contact(
        value, table=table, record_id=str(record_id), field=field
    )
    return EncryptedContactValue(ciphertext, table, str(record_id), field)


def prepare_contact_values(
    model_or_table: Any,
    record_id: str,
    values: Mapping[str, str | None],
) -> dict[Any, Any]:
    """Build safe SQLAlchemy Core values for one record's contact fields.

    The result is intended for ``insert(table).values(mapping)`` or
    ``update(table).values(mapping)``.  It contains only bound ciphertext and
    blind-index column values; ordinary plaintext Core binds are rejected.
    """
    table = getattr(model_or_table, "__table__", model_or_table)
    result: dict[Any, Any] = {}
    for name, value in values.items():
        column = table.c.get(name)
        index_column = table.c.get(f"{name}_blind_index")
        if column is None or index_column is None:
            raise ContactPersistenceError(
                f"{table.name}.{name} is not a protected contact field."
            )
        if value is None:
            result[column] = None
            result[index_column] = None
            continue
        if not isinstance(value, str):
            raise TypeError("Contact values must be strings or None.")
        result[column] = encrypted_contact_value(
            value, table=table.name, record_id=str(record_id), field=name
        )
        result[index_column] = contact_blind_index_value(
            value, table=table.name, field=name
        )
    return result


def _pack_bound_value(value: EncryptedContactValue) -> str:
    payload = json.dumps(
        {
            "table": value.table,
            "record": value.record_id,
            "field": value.field,
            "ciphertext": value.ciphertext,
        },
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return _PACKED_VALUE_PREFIX + base64.urlsafe_b64encode(payload).decode("ascii")


def _unpack_bound_value(value: str, *, expected_field: str) -> EncryptedContactValue:
    if not value.startswith(_PACKED_VALUE_PREFIX):
        raise ContactCiphertextInvalid(
            "Stored contact data is not encrypted; plaintext fallback is disabled."
        )
    try:
        encoded = value[len(_PACKED_VALUE_PREFIX) :]
        payload = json.loads(
            base64.b64decode(encoded, altchars=b"-_", validate=True).decode("utf-8")
        )
        result = EncryptedContactValue(
            ciphertext=payload["ciphertext"],
            table=payload["table"],
            record_id=payload["record"],
            field=payload["field"],
        )
        if (
            not isinstance(result.ciphertext, str)
            or not is_contact_ciphertext(result.ciphertext)
            or not isinstance(result.table, str)
            or not isinstance(result.record_id, str)
            or result.field != expected_field
        ):
            raise ValueError
        return result
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error) as exc:
        raise ContactCiphertextInvalid(
            "Stored contact data could not be authenticated."
        ) from exc


class _ContactComparator(TypeDecorator.Comparator):
    """Permit exact matching only, transparently using the blind index."""

    def operate(self, op, *other, **kwargs):
        if op is operators.eq:
            return self.__eq__(*other, **kwargs)
        if op is operators.ne:
            return self.__ne__(*other, **kwargs)
        if op is operators.in_op:
            return self.in_(*other, **kwargs)
        if op is operators.not_in_op:
            return self.not_in(*other, **kwargs)
        if op is operators.is_:
            return super().operate(op, *other, **kwargs)
        if op is operators.is_not:
            return super().operate(op, *other, **kwargs)
        raise ContactPersistenceError(
            "Encrypted contact fields support exact matching only."
        )

    def _index_expression(self):
        index = self.expr.table.c.get(f"{self.expr.name}_blind_index")
        if index is None:
            raise ContactPersistenceError(
                f"{self.expr.table.name}.{self.expr.name} has no blind-index column."
            )
        return index

    def __eq__(self, other):
        if other is None:
            return self.expr.is_(None)
        if not isinstance(other, str):
            raise ContactPersistenceError(
                "Encrypted contact fields support exact matching against strings only."
            )
        return self._index_expression() == contact_blind_index_value(
            other, table=self.expr.table.name, field=self.expr.name
        )

    def __ne__(self, other):
        if other is None:
            return self.expr.is_not(None)
        if not isinstance(other, str):
            raise ContactPersistenceError(
                "Encrypted contact fields support exact matching against strings only."
            )
        return self._index_expression() != contact_blind_index_value(
            other, table=self.expr.table.name, field=self.expr.name
        )

    def in_(self, values):
        if not isinstance(values, (list, tuple, set, frozenset)):
            raise ContactPersistenceError(
                "Encrypted contact IN queries require a finite collection."
            )
        if any(value is None for value in values):
            raise ContactPersistenceError(
                "Use an explicit NULL predicate with encrypted contact IN queries."
            )
        indexes = [
            contact_blind_index_value(
                value, table=self.expr.table.name, field=self.expr.name
            )
            for value in values
        ]
        return self._index_expression().in_(indexes)

    def not_in(self, values):
        if not isinstance(values, (list, tuple, set, frozenset)):
            raise ContactPersistenceError(
                "Encrypted contact NOT IN queries require a finite collection."
            )
        if any(value is None for value in values):
            raise ContactPersistenceError(
                "Use an explicit NULL predicate with encrypted contact NOT IN queries."
            )
        indexes = [
            contact_blind_index_value(
                value, table=self.expr.table.name, field=self.expr.name
            )
            for value in values
        ]
        return self._index_expression().not_in(indexes)

    def like(self, other, **kwargs):
        raise ContactPersistenceError(
            "Substring search is not supported on encrypted contact fields."
        )

    def ilike(self, other, **kwargs):
        raise ContactPersistenceError(
            "Substring search is not supported on encrypted contact fields."
        )

    def asc(self, **kwargs):
        raise ContactPersistenceError(
            "Sorting encrypted contact fields is not supported."
        )

    def desc(self, **kwargs):
        raise ContactPersistenceError(
            "Sorting encrypted contact fields is not supported."
        )


class ContactEncryptedText(TypeDecorator):
    """TEXT column that accepts only authenticated, record-bound ciphertext."""

    impl = Text
    cache_ok = True
    comparator_factory = _ContactComparator

    def __init__(self, field_name: str):
        self.field_name = field_name
        super().__init__()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, EncryptedContactValue):
            raise ContactPersistenceError(
                "Plaintext contact writes through Core/bulk paths are blocked; "
                "use the ORM unit-of-work or prepare_contact_values()."
            )
        if value.field != self.field_name:
            raise ContactPersistenceError(
                "Contact ciphertext is bound to a different field."
            )
        # Do not allow forged wrappers to write an unauthenticated value.
        decrypt_contact(
            value.ciphertext,
            table=value.table,
            record_id=value.record_id,
            field=value.field,
        )
        return _pack_bound_value(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _unpack_bound_value(value, expected_field=self.field_name)


def contact_text_column(field_name: str, *, nullable: bool = True):
    """Create a TEXT-backed encrypted column while keeping its API attribute name."""
    from sqlalchemy.orm import mapped_column

    return mapped_column(ContactEncryptedText(field_name), nullable=nullable)


def contact_index_column(
    field_name: str,
    *,
    nullable: bool = True,
    unique: bool = False,
    index: bool | None = None,
):
    """Create a generated blind-index column; map it to a private Python attribute."""
    from sqlalchemy.orm import mapped_column

    if index is None:
        index = not unique
    return mapped_column(
        f"{field_name}_blind_index",
        ContactBlindIndexType(),
        nullable=nullable,
        unique=unique,
        index=index,
    )


def _contact_key(key: str, parents: tuple[str, ...]) -> bool:
    lowered = key.lower()
    if lowered in _SNAPSHOT_CONTACT_KEYS or lowered.endswith(("_email", "_phone")):
        return True
    return lowered == "number" and bool(parents) and parents[-1].lower() == "phones"


def _transform_snapshot(
    value: Any,
    *,
    table: str,
    record_id: str,
    column: str,
    decrypt: bool,
    path: tuple[str, ...] = (),
    parents: tuple[str, ...] = (),
) -> Any:
    if isinstance(value, dict):
        return {
            key: _transform_snapshot(
                child,
                table=table,
                record_id=record_id,
                column=column,
                decrypt=decrypt,
                path=path + (str(key),),
                parents=parents + (str(key),),
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [
            _transform_snapshot(
                child,
                table=table,
                record_id=record_id,
                column=column,
                decrypt=decrypt,
                path=path + (str(index),),
                parents=parents,
            )
            for index, child in enumerate(value)
        ]
    if not path or not _contact_key(path[-1], parents[:-1]):
        return value
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContactPersistenceError(
            "Contact values inside protected snapshots must be strings or null."
        )
    field_name = f"{column}:{'.'.join(path)}"
    if decrypt:
        return decrypt_contact(
            value,
            table=table,
            record_id=record_id,
            field=field_name,
        )
    if is_contact_ciphertext(value):
        raise ContactCiphertextInvalid(
            "Contact snapshot value is already encrypted or was copied from storage."
        )
    return encrypt_contact(
        value,
        table=table,
        record_id=record_id,
        field=field_name,
    )


def protect_contact_snapshot(
    payload: dict[str, Any],
    *,
    table: str,
    record_id: str,
    column: str,
) -> ProtectedContactSnapshot:
    """Encrypt recognized structured contact leaves before a Core write."""
    if not isinstance(payload, dict):
        raise ContactPersistenceError("Protected contact snapshots must be JSON objects.")
    protected = _transform_snapshot(
        payload,
        table=table,
        record_id=str(record_id),
        column=column,
        decrypt=False,
    )
    return ProtectedContactSnapshot(protected, table, str(record_id), column)


def reveal_contact_snapshot(
    snapshot: ProtectedContactSnapshot,
    *,
    table: str,
    record_id: str,
    column: str,
) -> dict[str, Any]:
    """Decrypt recognized snapshot leaves after checking their row binding."""
    if (
        snapshot.table != table
        or snapshot.record_id != str(record_id)
        or snapshot.column != column
    ):
        raise ContactCiphertextInvalid(
            "Contact snapshot is bound to a different record or field."
        )
    return _transform_snapshot(
        snapshot.payload,
        table=table,
        record_id=str(record_id),
        column=column,
        decrypt=True,
    )


class ContactSnapshotJSON(TypeDecorator):
    """JSON/JSONB boundary that refuses unprotected direct contact snapshots."""

    impl = JSON
    cache_ok = True

    def __init__(self, column_name: str):
        self.column_name = column_name
        super().__init__()

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, ProtectedContactSnapshot):
            raise ContactPersistenceError(
                "Contact-bearing JSON snapshots must be written through the ORM "
                "unit-of-work or protect_contact_snapshot()."
            )
        if value.column != self.column_name:
            raise ContactPersistenceError(
                "Protected contact snapshot is bound to a different JSON column."
            )
        # Validate every protected leaf so callers cannot construct a wrapper
        # around raw JSON and bypass the ORM adapter through Core/bulk writes.
        reveal_contact_snapshot(
            value,
            table=value.table,
            record_id=value.record_id,
            column=value.column,
        )
        return value.payload

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ContactCiphertextInvalid("Stored contact snapshot is invalid.")
        return ProtectedContactSnapshot(value, "", "", self.column_name)


def protect_model_contacts(
    model: type,
    *,
    fields: Iterable[str] = (),
    snapshots: Iterable[str] = (),
) -> None:
    """Register ORM plaintext adapters after a mapped class is declared."""
    from app.db.contact_orm import register_contact_model

    register_contact_model(model, fields=fields, snapshots=snapshots)


def contact_equals(attribute: Any, value: str):
    """Explicit equivalent of ``Model.email == value`` for exact matching."""
    return attribute == value


def protect_snapshot_values(
    model_or_table: Any,
    record_id: str,
    column: str,
    payload: dict[str, Any],
) -> ProtectedContactSnapshot:
    """Prepare a record-bound protected snapshot for a direct Core write."""
    table = getattr(model_or_table, "__table__", model_or_table)
    return protect_contact_snapshot(
        payload,
        table=table.name,
        record_id=str(record_id),
        column=column,
    )