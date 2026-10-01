"""Resumable legacy contact conversion tests using only the isolated test schema."""
from __future__ import annotations

import base64
import importlib.util
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.contact_types import _unpack_bound_value, contact_blind_index
from app.db.base import Base
from app.services import contact_encryption
from app.services.contact_encryption import decrypt_contact
from tests.test_contact_encryption import _seed_contact_inventory_records
from tests.conftest import TEST_DB_URL, _make_engine, engine


def _load_conversion_module():
    path = (
        Path(__file__).parents[1]
        / "scripts/contact_data_migration.py"
    )
    script_dir = str(path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("contact_data_migration_tests", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_storage_migration():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/6c4e8a2f1b90_contact_encryption_storage.py"
    )
    spec = importlib.util.spec_from_file_location("contact_storage_migration_tests", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def legacy_contact_conversion_schema(db):
    """Downgrade the complete encrypted contact inventory to legacy plaintext."""
    migration = _load_conversion_module()
    schema_migration = _load_storage_migration()

    direct_contacts, snapshot_rows = _seed_contact_inventory_records(db)
    user_id, legacy_email = direct_contacts[("users", "email")]
    legacy_email = f"v1.legacy-{user_id.hex}@example.invalid"
    direct_contacts[("users", "email")] = (user_id, legacy_email)
    legacy_mobile = direct_contacts[("users", "mobile_number")][1]
    update_id = next(
        record_id
        for table, record_id, _column, _contacts in snapshot_rows
        if table == "provider_profile_updates"
    )
    legacy_snapshot_email = next(
        contacts["email"]
        for table, _record_id, column, contacts in snapshot_rows
        if table == "provider_profile_updates" and column == "proposed_profile"
    )
    legacy_snapshot_phone = next(
        contacts["phone"]
        for table, _record_id, column, contacts in snapshot_rows
        if table == "provider_profile_updates" and column == "proposed_profile"
    )
    role_id = db.execute(
        text("SELECT role_id FROM users WHERE id = :id"), {"id": user_id}
    ).scalar_one()

    # Restore all known scalar legacy values through raw SQL. Indexes remain
    # correctly keyed as in the staged migration before cutover.
    for (table, column), (record_id, cleartext) in direct_contacts.items():
        key_column = "provider_id" if table == "direct_provider_portal_access" else "id"
        db.execute(
            text(
                f"UPDATE {table} SET {column} = :value, "
                f"{column}_blind_index = :index "
                f"WHERE {key_column} = :record_id"
            ),
            {
                "value": cleartext,
                "index": contact_blind_index(
                    cleartext, table=table, field=column
                ),
                "record_id": record_id,
            },
        )

    # Restore every structured JSON contact leaf, including collection emails,
    # legacy scalar contacts, action snapshots, and provider profile history.
    for table, record_id, column, contacts in snapshot_rows:
        payload = db.execute(
            text(
                f"SELECT {column} FROM {table} WHERE id = :record_id"
            ),
            {"record_id": record_id},
        ).scalar_one()
        for dotted_path, cleartext in contacts.items():
            target = payload
            parts = dotted_path.split(".")
            for part in parts[:-1]:
                target = target[int(part)] if part.isdigit() else target[part]
            final = parts[-1]
            target[int(final) if final.isdigit() else final] = cleartext
        db.execute(
            text(
                f"UPDATE {table} SET {column} = CAST(:payload AS jsonb) "
                "WHERE id = :record_id"
            ),
            {"payload": json.dumps(payload), "record_id": record_id},
        )
    db.commit()

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            operation_context = Operations(MigrationContext.configure(connection))
            user_constraints = {
                constraint["name"]
                for constraint in inspect(connection).get_unique_constraints("users")
            }
            if "uq_users_email_blind_index" not in user_constraints:
                assert "users_email_blind_index_key" in user_constraints
                connection.execute(
                    text(
                        "ALTER TABLE users RENAME CONSTRAINT "
                        "users_email_blind_index_key TO uq_users_email_blind_index"
                    )
                )
            unique_fields = {("users", "email"), ("subscribers", "email")}
            for spec in migration.TABLES:
                for field_name in spec.scalar_fields:
                    if (spec.table.name, field_name) in unique_fields:
                        continue
                    name = schema_migration.conv(
                        f"ix_{spec.table.name}_{field_name}_blind_index"
                    )
                    rendered_name = (
                        connection.dialect.identifier_preparer
                        .truncate_and_render_index_name(
                            name,
                            _alembic_quote=False,
                        )
                    )
                    existing_names = {
                        index["name"]
                        for index in inspect(connection).get_indexes(spec.table.name)
                    }
                    if rendered_name not in existing_names:
                        operation_context.create_index(
                            name,
                            spec.table.name,
                            [f"{field_name}_blind_index"],
                        )
            connection.execute(
                text(
                    """
                    CREATE TABLE contact_encryption_migration_state (
                        id SMALLINT PRIMARY KEY CHECK (id = 1),
                        state VARCHAR(20) NOT NULL DEFAULT 'pending',
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        rows_examined BIGINT NOT NULL DEFAULT 0,
                        rows_changed BIGINT NOT NULL DEFAULT 0,
                        scalar_values_encrypted BIGINT NOT NULL DEFAULT 0,
                        snapshots_protected BIGINT NOT NULL DEFAULT 0,
                            historical_copies_redacted BIGINT NOT NULL DEFAULT 0,
                            audit_metadata_redacted BIGINT NOT NULL DEFAULT 0,
                        verified_at TIMESTAMPTZ NULL,
                        cutover_completed_at TIMESTAMPTZ NULL
                    )
                    """
                )
            )
            connection.execute(
                text("INSERT INTO contact_encryption_migration_state (id) VALUES (1)")
            )
            with Operations.context(MigrationContext.configure(connection)):
                schema_migration._create_guard_functions()
                schema_migration._create_write_guards()
            transaction.commit()
        except BaseException:
            transaction.rollback()
            raise

    missing_test_indexes = []
    for spec in migration.TABLES:
        table = spec.table.name
        indexes = inspect(engine).get_indexes(table)
        constraints = inspect(engine).get_unique_constraints(table)
        for field_name in spec.scalar_fields:
            if (table, field_name) == ("users", "email"):
                present = any(
                    item.get("name") == "uq_users_email_blind_index"
                    and item.get("column_names") == ["email_blind_index"]
                    for item in constraints
                )
            elif (table, field_name) == ("subscribers", "email"):
                present = any(
                    item.get("name") == "uq_subscribers_email"
                    and item.get("column_names") == ["email_blind_index"]
                    for item in constraints
                )
            else:
                index_name = (
                    engine.dialect.identifier_preparer
                    .truncate_and_render_index_name(
                        schema_migration.conv(
                            f"ix_{table}_{field_name}_blind_index"
                        ),
                        _alembic_quote=False,
                    )
                )
                present = any(
                    index.get("name") == index_name
                    and index.get("column_names") == [f"{field_name}_blind_index"]
                    and index.get("unique") is False
                    for index in indexes
                )
            if not present:
                missing_test_indexes.append(
                    f"{table}.{field_name}: indexes={indexes!r}, "
                    f"constraints={constraints!r}"
                )
    assert not missing_test_indexes, (
        "test contact schema is missing expected blind indexes: "
        + ", ".join(missing_test_indexes)
    )

    yield {
        "migration": migration,
        "schema_migration": schema_migration,
        "user_id": user_id,
        "update_id": update_id,
        "legacy_email": legacy_email,
        "legacy_mobile": legacy_mobile,
        "snapshot_email": legacy_snapshot_email,
        "snapshot_phone": legacy_snapshot_phone,
        "role_id": role_id,
        "direct_contacts": direct_contacts,
        "snapshot_rows": snapshot_rows,
        "legacy_scalar_count": len(direct_contacts),
        "legacy_snapshot_count": sum(
            len(contacts) for _table, _record_id, _column, contacts in snapshot_rows
        ),
    }

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                schema_migration._drop_write_guards()
                schema_migration._drop_guard_functions()
            connection.execute(
                text("DROP TABLE IF EXISTS contact_encryption_migration_state")
            )
            transaction.commit()
        except BaseException:
            transaction.rollback()
            raise


def test_legacy_conversion_resumes_after_interruption_and_is_idempotent(
    legacy_contact_conversion_schema, capsys
):
    setup = legacy_contact_conversion_schema
    migration = setup["migration"]

    preview = migration.preview(engine, batch_size=1)
    assert preview.remaining_plaintext == (
        setup["legacy_scalar_count"] + setup["legacy_snapshot_count"]
    )
    assert preview.verified is False

    real_emit = migration.emit
    emitted_batch = False

    def interrupt_after_committed_batch(payload):
        nonlocal emitted_batch
        real_emit(payload)
        if payload.get("phase") == "convert" and not emitted_batch:
            emitted_batch = True
            raise KeyboardInterrupt

    migration.emit = interrupt_after_committed_batch
    with pytest.raises(KeyboardInterrupt):
        migration.convert(engine, batch_size=1)
    assert emitted_batch
    interrupted_output = capsys.readouterr().out
    assert setup["legacy_email"] not in interrupted_output
    assert setup["legacy_mobile"] not in interrupted_output
    assert setup["snapshot_email"] not in interrupted_output

    after_interrupt = migration.preview(engine, batch_size=1)
    assert 0 < after_interrupt.remaining_plaintext < preview.remaining_plaintext

    migration.emit = real_emit
    completed = migration.convert(engine, batch_size=1)
    assert completed["verification"]["verified"] is True
    assert completed["verification"]["remaining_plaintext"] == 0
    assert completed["conversion"]["scalar_values_encrypted"] > 0
    assert completed["conversion"]["snapshots_protected"] > 0

    repeated = migration.convert(engine, batch_size=1)
    assert repeated["verification"]["verified"] is True
    assert repeated["conversion"]["rows_changed"] == 0
    assert repeated["conversion"]["scalar_values_encrypted"] == 0
    assert repeated["conversion"]["snapshots_protected"] == 0

    with engine.connect() as connection:
        email, mobile, snapshot = connection.execute(
            text(
                """
                SELECT users.email, users.mobile_number,
                       provider_profile_updates.proposed_profile
                FROM users
                CROSS JOIN provider_profile_updates
                WHERE users.id = :user_id
                  AND provider_profile_updates.id = :update_id
                """
            ),
            {"user_id": setup["user_id"], "update_id": setup["update_id"]},
        ).one()
    serialized = json.dumps(snapshot, sort_keys=True)
    assert setup["legacy_email"] not in email
    assert setup["legacy_mobile"] not in mobile
    assert setup["snapshot_email"] not in serialized
    assert setup["snapshot_phone"] not in serialized

    with engine.connect() as connection:
        for (table, column), (record_id, cleartext) in setup[
            "direct_contacts"
        ].items():
            key_column = (
                "provider_id"
                if table == "direct_provider_portal_access"
                else "id"
            )
            raw = connection.execute(
                text(
                    f"SELECT {column} FROM {table} "
                    f"WHERE {key_column} = :record_id"
                ),
                {"record_id": record_id},
            ).scalar_one()
            bound = _unpack_bound_value(raw, expected_field=column)
            assert bound.table == table
            assert bound.record_id == str(record_id)
            assert decrypt_contact(
                bound.ciphertext,
                table=table,
                record_id=str(record_id),
                field=column,
            ) == cleartext
            assert cleartext not in raw
            index = connection.execute(
                text(
                    f"SELECT {column}_blind_index FROM {table} "
                    f"WHERE {key_column} = :record_id"
                ),
                {"record_id": record_id},
            ).scalar_one()
            assert index == contact_blind_index(
                cleartext, table=table, field=column
            )
        for table, record_id, column, contacts in setup["snapshot_rows"]:
            raw = connection.execute(
                text(f"SELECT {column} FROM {table} WHERE id = :record_id"),
                {"record_id": record_id},
            ).scalar_one()
            snapshot_text = json.dumps(raw, sort_keys=True)
            for dotted_path, cleartext in contacts.items():
                node = raw
                for part in dotted_path.split("."):
                    node = node[int(part)] if part.isdigit() else node[part]
                assert isinstance(node, str) and node.startswith("v1.")
                assert cleartext not in snapshot_text
                assert decrypt_contact(
                    node,
                    table=table,
                    record_id=str(record_id),
                    field=f"{column}:{dotted_path}",
                ) == cleartext


def test_conversion_inventory_matches_every_schema_contact_and_snapshot_field(
    legacy_contact_conversion_schema,
):
    setup = legacy_contact_conversion_schema
    migration = setup["migration"]
    schema_migration = setup["schema_migration"]
    expected_scalars = {}
    for table, field_name, _length, _nullable in schema_migration.CONTACT_FIELDS:
        expected_scalars.setdefault(table, set()).add(field_name)
    converted_scalars = {
        spec.table.name: set(spec.scalar_fields)
        for spec in migration.TABLES
        if spec.scalar_fields
    }
    assert converted_scalars == expected_scalars

    expected_snapshots = {}
    for table, column in schema_migration.SNAPSHOT_FIELDS:
        expected_snapshots.setdefault(table, set()).add(column)
    converted_snapshots = {
        spec.table.name: set(spec.snapshot_fields)
        for spec in migration.TABLES
        if spec.snapshot_fields
    }
    assert converted_snapshots == expected_snapshots


def test_conversion_preview_detects_duplicate_normalized_email_conflicts(
    legacy_contact_conversion_schema,
):
    setup = legacy_contact_conversion_schema
    migration = setup["migration"]
    duplicate_id = uuid4()
    duplicate_email = setup["legacy_email"].upper()
    now = datetime.now(timezone.utc)
    # Simulate a legacy process inserting after the migration's trigger was
    # installed: its stale, distinct index cannot satisfy conversion uniqueness.
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE users DISABLE TRIGGER trg_users_contact_write_guard")
        )
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, email_blind_index, password_hash, role_id,
                    is_active, created_at, updated_at
                ) VALUES (
                    :id, :email, :index, :password_hash, :role_id,
                    TRUE, :created_at, :updated_at
                )
                """
            ),
            {
                "id": duplicate_id,
                "email": duplicate_email,
                "index": "f" * 64,
                "password_hash": "legacy-conflict-fixture",
                "role_id": setup["role_id"],
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text("ALTER TABLE users ENABLE TRIGGER trg_users_contact_write_guard")
        )

    result = migration.preview(engine, batch_size=1)
    assert result.conflict_groups == 1
    assert result.duplicate_rows == 1
    assert result.validation_errors > 0
    with pytest.raises(ValueError, match="Preview checks failed"):
        migration.convert(engine, batch_size=1)
    with engine.connect() as connection:
        state = connection.execute(
            text("SELECT state FROM contact_encryption_migration_state WHERE id = 1")
        ).scalar_one()
        raw_email = connection.execute(
            text("SELECT email FROM users WHERE id = :id"),
            {"id": setup["user_id"]},
        ).scalar_one()
    assert state == "pending"
    assert raw_email == setup["legacy_email"]


def test_conversion_rejects_tampered_or_field_swapped_ciphertext(
    legacy_contact_conversion_schema,
):
    setup = legacy_contact_conversion_schema
    migration = setup["migration"]
    migration.convert(engine, batch_size=2)

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET email = mobile_number WHERE id = :id"),
            {"id": setup["user_id"]},
        )
    result = migration.preview(engine, batch_size=2)
    assert result.invalid_scalars >= 1
    assert result.verified is False
    with pytest.raises(ValueError, match="Preview checks failed"):
        migration.convert(engine, batch_size=2)


def test_database_guards_reject_plaintext_scalar_and_snapshot_writes(
    legacy_contact_conversion_schema,
):
    setup = legacy_contact_conversion_schema
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE users SET email = :value WHERE id = :id"),
                {"value": "guard-bypass@example.invalid", "id": setup["user_id"]},
            )
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE provider_profile_updates
                    SET proposed_profile = CAST(:payload AS jsonb)
                    WHERE id = :id
                    """
                ),
                {
                    "payload": json.dumps({"email": "guard-snapshot@example.invalid"}),
                    "id": setup["update_id"],
                },
            )


def _load_rotation_module(conversion_module):
    script_dir = str(Path(__file__).parents[1] / "scripts")
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    sys.modules["contact_data_migration"] = conversion_module
    path = Path(script_dir) / "contact_key_rotation.py"
    spec = importlib.util.spec_from_file_location("contact_key_rotation_tests", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_contact_key_rotation_reencrypts_contacts_and_blind_indexes(
    legacy_contact_conversion_schema, monkeypatch
):
    setup = legacy_contact_conversion_schema
    migration = setup["migration"]
    rotation = _load_rotation_module(migration)
    migration.convert(engine, batch_size=5)
    cutover = migration.complete_cutover(engine, batch_size=5)
    assert cutover.verified

    _active_id, old_keys, current_index_key = contact_encryption._key_material()
    old_keyring = {
        key_id: base64.b64encode(key).decode("ascii")
        for key_id, key in old_keys.items()
    }
    rotated_key_id = "contact-test-rotated"
    new_encryption_key = secrets.token_bytes(32)
    new_index_key = secrets.token_bytes(32)
    rotated_settings = SimpleNamespace(
        CONTACT_ENCRYPTION_KEYRING=json.dumps(
            {
                **old_keyring,
                rotated_key_id: base64.b64encode(new_encryption_key).decode("ascii"),
            }
        ),
        CONTACT_ENCRYPTION_ACTIVE_KEY_ID=rotated_key_id,
        CONTACT_BLIND_INDEX_KEY=base64.b64encode(current_index_key).decode("ascii"),
    )
    monkeypatch.setattr(
        contact_encryption, "get_settings", lambda: rotated_settings
    )
    monkeypatch.setattr(
        rotation, "_active_encryption_key_id", lambda: rotated_key_id
    )

    encryption_result = rotation.rotate(engine, "encryption", batch_size=5)
    assert encryption_result["verified"] is True
    with engine.connect() as connection:
        packed_email = connection.execute(
            text("SELECT email FROM users WHERE id = :id"),
            {"id": setup["user_id"]},
        ).scalar_one()
    bound_email = _unpack_bound_value(packed_email, expected_field="email")
    assert bound_email.ciphertext.split(".", maxsplit=2)[1] == rotated_key_id
    assert decrypt_contact(
        bound_email.ciphertext,
        table="users",
        record_id=str(setup["user_id"]),
        field="email",
    ) == setup["legacy_email"]

    monkeypatch.setenv(
        rotation.NEXT_INDEX_SECRET,
        base64.b64encode(new_index_key).decode("ascii"),
    )
    index_result = rotation.rotate(engine, "index", batch_size=5)
    assert index_result["verified"] is True

    rotated_settings.CONTACT_BLIND_INDEX_KEY = base64.b64encode(
        new_index_key
    ).decode("ascii")
    with engine.connect() as connection:
        email_index = connection.execute(
            text("SELECT email_blind_index FROM users WHERE id = :id"),
            {"id": setup["user_id"]},
        ).scalar_one()
    assert email_index == contact_blind_index(
        setup["legacy_email"], table="users", field="email"
    )


def test_storage_migration_upgrades_existing_tables_in_isolated_schema():
    """Exercise the real storage revision without touching the shared test schema."""
    storage_migration = _load_storage_migration()
    schema_name = f"contact_upgrade_{uuid4().hex}"
    admin_engine = create_engine(
        TEST_DB_URL,
        pool_pre_ping=True,
        hide_parameters=True,
    )
    scratch_engine = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema_name}"))
        scratch_engine = _make_engine(schema_name)
        Base.metadata.create_all(bind=scratch_engine)

        # Reconstruct the preceding revision's storage layout: bounded scalar
        # columns, plaintext exact-match indexes, and no blind-index columns.
        with scratch_engine.begin() as connection:
            for table, field_name, old_length, _nullable in (
                storage_migration.CONTACT_FIELDS
            ):
                connection.execute(
                    text(
                        f"ALTER TABLE {table} ALTER COLUMN {field_name} "
                        f"TYPE VARCHAR({old_length})"
                    )
                )
                connection.execute(
                    text(
                        f"ALTER TABLE {table} DROP COLUMN "
                        f"{field_name}_blind_index CASCADE"
                    )
                )
            connection.execute(
                text("CREATE UNIQUE INDEX ix_users_email ON users (email)")
            )
            connection.execute(
                text(
                    "ALTER TABLE subscribers ADD CONSTRAINT uq_subscribers_email "
                    "UNIQUE (email)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_provider_invitations_provider_email "
                    "ON provider_invitations (provider_id, recipient_email)"
                )
            )
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX uq_provider_invitations_active_provider_email
                    ON provider_invitations (provider_id, recipient_email)
                    WHERE status IN ('PENDING', 'ACCEPTED')
                    """
                )
            )

        with scratch_engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Operations.context(MigrationContext.configure(connection)):
                    storage_migration.upgrade()
                transaction.commit()
            except BaseException:
                transaction.rollback()
                raise

        inspector = inspect(scratch_engine)
        for table, field_name, _old_length, _nullable in (
            storage_migration.CONTACT_FIELDS
        ):
            names = {
                column["name"]
                for column in inspector.get_columns(table)
            }
            assert field_name in names
            assert f"{field_name}_blind_index" in names
            contact_type = next(
                column["type"]
                for column in inspector.get_columns(table)
                if column["name"] == field_name
            )
            assert contact_type.__class__.__name__.lower() == "text"
        users_unique = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("users")
        }
        assert ("email_blind_index",) in users_unique
        subscriber_unique = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("subscribers")
        }
        assert ("email_blind_index",) in subscriber_unique
        invitation_indexes = {
            index["name"] for index in inspector.get_indexes("provider_invitations")
        }
        assert "ix_provider_invitations_provider_email_blind_index" in invitation_indexes
        assert "uq_provider_invitations_active_provider_email" in invitation_indexes

        with scratch_engine.connect() as connection:
            state = connection.execute(
                text(
                    "SELECT state FROM contact_encryption_migration_state WHERE id = 1"
                )
            ).scalar_one()
            guard_count = connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM pg_trigger AS trigger
                    JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
                    JOIN pg_namespace AS namespace
                      ON namespace.oid = relation.relnamespace
                    WHERE NOT trigger.tgisinternal
                      AND trigger.tgname LIKE 'trg_%_contact_write_guard'
                      AND namespace.nspname = :schema
                    """
                ),
                {"schema": schema_name},
            ).scalar_one()
        assert state == "pending"
        expected_guards = len(
            {
                table for table, _field, _length, _nullable
                in storage_migration.CONTACT_FIELDS
            }
            | {table for table, _column in storage_migration.SNAPSHOT_FIELDS}
            | {
                table
                for table, _column
                in storage_migration.AUDIT_REDACTION_FIELDS
            }
            | {
                table
                for table, _column
                in storage_migration.CONTACT_FREE_TEXT_FIELDS
            }
        )
        assert guard_count == expected_guards

        with pytest.raises(IntegrityError):
            with scratch_engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users (id, email) VALUES (:id, :email)"
                    ),
                    {
                        "id": uuid4(),
                        "email": "migration-guard@example.invalid",
                    },
                )
    finally:
        if scratch_engine is not None:
            scratch_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        admin_engine.dispose()