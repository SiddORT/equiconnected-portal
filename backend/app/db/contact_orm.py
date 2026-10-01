"""ORM identity-bound plaintext adapters for contact storage types."""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import event
from sqlalchemy.orm import Session, attributes

from app.db.contact_types import (
    ContactCiphertextInvalid,
    ContactPersistenceError,
    EncryptedContactValue,
    ProtectedContactSnapshot,
    contact_blind_index_value,
    decrypt_contact,
    encrypted_contact_value,
    is_contact_ciphertext,
    protect_contact_snapshot,
    record_identity,
    reveal_contact_snapshot,
)

_MODEL_FIELDS: dict[type, tuple[str, ...]] = {}
_MODEL_SNAPSHOTS: dict[type, tuple[str, ...]] = {}
_REFRESH_LISTENERS: set[type] = set()
_EVENTS_INSTALLED = False


def register_contact_model(
    model: type,
    *,
    fields: Iterable[str] = (),
    snapshots: Iterable[str] = (),
) -> None:
    """Attach persistence hooks for contact-bearing mapped attributes."""
    global _EVENTS_INSTALLED
    field_names = tuple(fields)
    snapshot_names = tuple(snapshots)
    if field_names:
        _MODEL_FIELDS[model] = field_names
    if snapshot_names:
        _MODEL_SNAPSHOTS[model] = snapshot_names

    if model not in _REFRESH_LISTENERS:
        event.listen(model, "refresh", _refresh_instance_contacts)
        _REFRESH_LISTENERS.add(model)
    if _EVENTS_INSTALLED:
        return

    @event.listens_for(Session, "before_flush")
    def _encrypt_pending_contacts(session, _flush_context, _instances):
        for instance in session.new.union(session.dirty):
            cls = type(instance)
            table_name = instance.__table__.name
            is_new = instance in session.new
            state = attributes.instance_state(instance)
            if cls in _MODEL_FIELDS:
                record_id = record_identity(instance)
                for name in _MODEL_FIELDS[cls]:
                    if (
                        not is_new
                        and not state.attrs[name].history.has_changes()
                    ):
                        continue
                    value = getattr(instance, name)
                    index_attr = f"_{name}_blind_index"
                    if value is None:
                        setattr(instance, index_attr, None)
                    elif isinstance(value, EncryptedContactValue):
                        if (
                            value.table != table_name
                            or value.record_id != record_id
                            or value.field != name
                        ):
                            raise ContactPersistenceError(
                                "Contact ciphertext is bound to a different record or field."
                            )
                    elif isinstance(value, str):
                        if is_contact_ciphertext(value):
                            raise ContactCiphertextInvalid(
                                "Contact value is already encrypted or was copied from storage."
                            )
                        setattr(
                            instance,
                            name,
                            encrypted_contact_value(
                                value,
                                table=table_name,
                                record_id=record_id,
                                field=name,
                            ),
                        )
                        setattr(
                            instance,
                            index_attr,
                            contact_blind_index_value(
                                value, table=table_name, field=name
                            ),
                        )
                    else:
                        raise ContactPersistenceError(
                            f"{table_name}.{name} must be a plaintext string or None."
                        )
            if cls in _MODEL_SNAPSHOTS:
                record_id = record_identity(instance)
                for name in _MODEL_SNAPSHOTS[cls]:
                    if (
                        not is_new
                        and not state.attrs[name].history.has_changes()
                    ):
                        continue
                    value = getattr(instance, name)
                    if value is None:
                        continue
                    if isinstance(value, ProtectedContactSnapshot):
                        if (
                            value.table != table_name
                            or value.record_id != record_id
                            or value.column != name
                        ):
                            raise ContactPersistenceError(
                                "Protected snapshot is bound to a different record or field."
                            )
                    elif isinstance(value, dict):
                        setattr(
                            instance,
                            name,
                            protect_contact_snapshot(
                                value,
                                table=table_name,
                                record_id=record_id,
                                column=name,
                            ),
                        )
                    else:
                        raise ContactPersistenceError(
                            f"{table_name}.{name} must be a JSON object."
                        )

    @event.listens_for(Session, "loaded_as_persistent")
    def _decrypt_loaded_contacts(_session, instance):
        _reveal_instance_contacts(instance)

    @event.listens_for(Session, "after_flush_postexec")
    def _restore_plaintext_api_values(session, _flush_context):
        for instance in tuple(session.identity_map.values()):
            _reveal_instance_contacts(instance)

    _EVENTS_INSTALLED = True


def _refresh_instance_contacts(target, _context, attrs):
    """Decrypt values after an expired attribute or explicit refresh reloads."""
    _reveal_instance_contacts(target, attrs=attrs)


def _reveal_instance_contacts(
    instance: Any,
    *,
    attrs: Iterable[str] | None = None,
) -> None:
    cls = type(instance)
    table_name = instance.__table__.name
    if cls not in _MODEL_FIELDS and cls not in _MODEL_SNAPSHOTS:
        return
    refreshed = set(attrs) if attrs is not None else None
    record_id = record_identity(instance)
    for name in _MODEL_FIELDS.get(cls, ()):
        if refreshed is not None and name not in refreshed:
            continue
        value = getattr(instance, name, None)
        if isinstance(value, EncryptedContactValue):
            if (
                value.table != table_name
                or value.record_id != record_id
                or value.field != name
            ):
                raise ContactCiphertextInvalid(
                    "Stored contact data is bound to a different record or field."
                )
            cleartext = decrypt_contact(
                value.ciphertext,
                table=table_name,
                record_id=record_id,
                field=name,
            )
            attributes.set_committed_value(instance, name, cleartext)
    for name in _MODEL_SNAPSHOTS.get(cls, ()):
        if refreshed is not None and name not in refreshed:
            continue
        value = getattr(instance, name, None)
        if isinstance(value, ProtectedContactSnapshot):
            # Result processors cannot see row identity, so bind to the loaded
            # instance before authenticating every recognized contact leaf.
            bound = ProtectedContactSnapshot(
                value.payload, table_name, record_id, name
            )
            cleartext = reveal_contact_snapshot(
                bound,
                table=table_name,
                record_id=record_id,
                column=name,
            )
            attributes.set_committed_value(instance, name, cleartext)