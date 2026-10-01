"""add encrypted contact storage columns, indexes, and plaintext-write guard

Revision ID: 6c4e8a2f1b90
Revises: e352d353a901
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.elements import conv


revision: str = "6c4e8a2f1b90"
down_revision: Union[str, None] = "e352d353a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, contact field, old bounded storage length, nullable)
CONTACT_FIELDS = (
    ("users", "email", 255, False),
    ("users", "mobile_number", 32, True),
    ("providers", "email", 254, True),
    ("providers", "phone", 50, True),
    ("providers", "emergency_contact_number", 50, True),
    ("provider_emails", "email", 254, False),
    ("provider_phones", "number", 50, False),
    ("provider_registration_applications", "emergency_contact_number", 50, True),
    ("stable_profiles", "contact_phone", 50, True),
    ("stable_profiles", "contact_email", 254, True),
    ("organization_requests", "contact_email", 254, True),
    ("provider_invitations", "recipient_email", 254, False),
    ("direct_provider_portal_access", "recipient_email", 254, False),
    ("email_delivery_logs", "recipient_email", 255, False),
    ("contact_enquiries", "email", 255, False),
    ("contact_enquiries", "phone", 40, True),
    ("subscribers", "email", 255, False),
    ("member_feedback", "submitter_email", 254, False),
    ("member_feedback_actions", "actor_email", 254, False),
    ("provider_review_actions", "actor_email", 254, False),
)

SNAPSHOT_FIELDS = (
    ("provider_profile_updates", "base_profile"),
    ("provider_profile_updates", "proposed_profile"),
    ("member_feedback_actions", "content_snapshot"),
    ("provider_review_actions", "content_snapshot"),
)

AUDIT_REDACTION_FIELDS = (("audit_logs", "metadata"),)
CONTACT_FREE_TEXT_FIELDS = (
    ("providers", "name"),
    ("member_feedback", "submitter_name"),
    ("member_feedback_actions", "actor_name"),
    ("provider_review_actions", "actor_name"),
)


def _create_guard_functions() -> None:
    op.execute(
        """
        CREATE FUNCTION contact_snapshot_is_protected(
            payload jsonb, phone_collection boolean DEFAULT false
        ) RETURNS boolean
        LANGUAGE plpgsql IMMUTABLE
        AS $$
        DECLARE
            member record;
            child jsonb;
            is_contact boolean;
        BEGIN
            IF payload IS NULL OR jsonb_typeof(payload) = 'null' THEN
                RETURN TRUE;
            ELSIF jsonb_typeof(payload) = 'object' THEN
                FOR member IN SELECT key, value FROM jsonb_each(payload)
                LOOP
                    is_contact :=
                        lower(member.key) IN (
                            'email', 'contact_email', 'recipient_email',
                            'submitter_email', 'actor_email', 'phone',
                            'contact_phone', 'mobile_number', 'telephone',
                            'emergency_contact_number'
                        )
                        OR lower(member.key) ~ '(_email|_phone)$'
                        OR (lower(member.key) = 'number' AND phone_collection);
                    IF is_contact AND member.value <> 'null'::jsonb THEN
                        IF jsonb_typeof(member.value) <> 'string'
                           OR (member.value #>> '{}') NOT LIKE 'v1.%' THEN
                            RETURN FALSE;
                        END IF;
                    ELSIF NOT contact_snapshot_is_protected(
                        member.value, lower(member.key) = 'phones'
                    ) THEN
                        RETURN FALSE;
                    END IF;
                END LOOP;
            ELSIF jsonb_typeof(payload) = 'array' THEN
                FOR child IN SELECT value FROM jsonb_array_elements(payload)
                LOOP
                    IF NOT contact_snapshot_is_protected(child, phone_collection) THEN
                        RETURN FALSE;
                    END IF;
                END LOOP;
            END IF;
            RETURN TRUE;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION contact_text_has_contact(candidate text)
        RETURNS boolean
        LANGUAGE sql IMMUTABLE
        AS $$
            SELECT coalesce(
                candidate ~*
                '[[:alnum:].!#$%&''*+/=?^_`{|}~-]+@[[:alnum:].-]+\\.[[:alpha:]]{2,}'
                OR candidate ~
                '(^|[^[:alnum:]_])\\+?([0-9][0-9 ().-]{5,}[0-9])($|[^[:alnum:]_])',
                FALSE
            )
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION contact_text_is_email(candidate text)
        RETURNS boolean
        LANGUAGE sql IMMUTABLE
        AS $$
            SELECT coalesce(
                btrim(candidate) ~*
                '^[[:alnum:].!#$%&''*+/=?^_`{|}~-]+@[[:alnum:].-]+\\.[[:alpha:]]{2,}$',
                FALSE
            )
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION contact_audit_metadata_is_safe(
            payload jsonb, parent_key text DEFAULT NULL
        )
        RETURNS boolean
        LANGUAGE plpgsql IMMUTABLE
        AS $$
        DECLARE
            member record;
            child jsonb;
            key_name text;
            string_value text;
            is_contact_change boolean;
        BEGIN
            IF payload IS NULL OR jsonb_typeof(payload) = 'null' THEN
                RETURN TRUE;
            ELSIF jsonb_typeof(payload) = 'object' THEN
                key_name := lower(coalesce(payload ->> 'field', ''));
                is_contact_change :=
                    key_name LIKE '%email%'
                    OR key_name LIKE '%phone%'
                    OR key_name LIKE '%telephone%'
                    OR key_name LIKE '%mobile%'
                    OR key_name LIKE '%contact%'
                    OR key_name LIKE '%recipient%';
                FOR member IN SELECT key, value FROM jsonb_each(payload)
                LOOP
                    key_name := lower(member.key);
                    IF is_contact_change
                       AND key_name IN ('before', 'after')
                       AND member.value <> 'null'::jsonb
                       AND member.value <> '"[redacted]"'::jsonb THEN
                        RETURN FALSE;
                    ELSIF key_name LIKE '%email%'
                       OR key_name LIKE '%phone%'
                       OR key_name LIKE '%telephone%'
                       OR key_name LIKE '%mobile%'
                       OR key_name LIKE '%contact%'
                       OR key_name LIKE '%recipient%' THEN
                        IF member.value <> 'null'::jsonb
                           AND member.value <> '"[redacted]"'::jsonb THEN
                            RETURN FALSE;
                        END IF;
                    ELSIF NOT contact_audit_metadata_is_safe(
                        member.value, member.key
                    ) THEN
                        RETURN FALSE;
                    END IF;
                END LOOP;
            ELSIF jsonb_typeof(payload) = 'array' THEN
                FOR child IN SELECT value FROM jsonb_array_elements(payload)
                LOOP
                    IF NOT contact_audit_metadata_is_safe(child, parent_key) THEN
                        RETURN FALSE;
                    END IF;
                END LOOP;
            ELSIF jsonb_typeof(payload) = 'string' THEN
                string_value := payload #>> '{}';
                IF (
                    lower(coalesce(parent_key, '')) = 'summary'
                    AND contact_text_has_contact(string_value)
                ) OR (
                    lower(coalesce(parent_key, '')) IN (
                        'name', 'provider_name', 'actor_name', 'submitter_name'
                    )
                    AND contact_text_is_email(string_value)
                ) THEN
                    RETURN FALSE;
                END IF;
            END IF;
            RETURN TRUE;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_plaintext_contact_write() RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            field_spec text;
            field_name text;
            field_kind text;
            blind_index_name text;
            new_row jsonb := to_jsonb(NEW);
            old_row jsonb;
            field_value jsonb;
            blind_index_value jsonb;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                old_row := to_jsonb(OLD);
            END IF;
            FOREACH field_spec IN ARRAY TG_ARGV
            LOOP
                field_kind := split_part(field_spec, ':', 1);
                field_name := substr(field_spec, length(field_kind) + 2);
                IF TG_OP = 'INSERT'
                   OR (new_row -> field_name) IS DISTINCT FROM (old_row -> field_name)
                   OR (
                       field_kind = 'scalar'
                       AND (new_row -> (field_name || '_blind_index'))
                           IS DISTINCT FROM (old_row -> (field_name || '_blind_index'))
                   ) THEN
                    field_value := new_row -> field_name;
                    IF field_kind = 'scalar' THEN
                        blind_index_name := field_name || '_blind_index';
                        blind_index_value := new_row -> blind_index_name;
                        IF field_value IS NULL
                           OR field_value = 'null'::jsonb THEN
                            IF blind_index_value IS NOT NULL
                               AND blind_index_value <> 'null'::jsonb THEN
                                RAISE EXCEPTION 'contact blind indexes require a contact value'
                                    USING ERRCODE = '23514';
                            END IF;
                        ELSIF jsonb_typeof(field_value) <> 'string'
                           OR (field_value #>> '{}') NOT LIKE 'ecv1:%' THEN
                            RAISE EXCEPTION 'plaintext contact writes are disabled'
                                USING ERRCODE = '23514';
                        ELSIF blind_index_value IS NULL
                           OR jsonb_typeof(blind_index_value) <> 'string'
                           OR (blind_index_value #>> '{}') !~ '^[0-9a-f]{64}$' THEN
                            RAISE EXCEPTION 'encrypted contacts require a blind index'
                                USING ERRCODE = '23514';
                        END IF;
                    ELSIF field_kind = 'json'
                       AND NOT contact_snapshot_is_protected(field_value) THEN
                        RAISE EXCEPTION 'plaintext contact snapshot writes are disabled'
                            USING ERRCODE = '23514';
                    ELSIF field_kind = 'audit'
                       AND NOT contact_audit_metadata_is_safe(field_value) THEN
                        RAISE EXCEPTION 'audit contact metadata must be redacted'
                            USING ERRCODE = '23514';
                    ELSIF field_kind = 'contact_free_text'
                       AND field_value IS NOT NULL
                       AND field_value <> 'null'::jsonb
                       AND (
                           jsonb_typeof(field_value) <> 'string'
                           OR contact_text_has_contact(field_value #>> '{}')
                       ) THEN
                        RAISE EXCEPTION 'contact values are not allowed in display names'
                            USING ERRCODE = '23514';
                    END IF;
                END IF;
            END LOOP;
            RETURN NEW;
        END;
        $$;
        """
    )


def _drop_guard_functions() -> None:
    op.execute("DROP FUNCTION IF EXISTS reject_plaintext_contact_write()")
    op.execute(
        "DROP FUNCTION IF EXISTS contact_snapshot_is_protected(jsonb, boolean)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS contact_audit_metadata_is_safe(jsonb, text)"
    )
    op.execute("DROP FUNCTION IF EXISTS contact_text_is_email(text)")
    op.execute("DROP FUNCTION IF EXISTS contact_text_has_contact(text)")


def _create_write_guards() -> None:
    by_table: dict[str, list[str]] = {}
    for table, field, _length, _nullable in CONTACT_FIELDS:
        by_table.setdefault(table, []).append(f"scalar:{field}")
    for table, column in SNAPSHOT_FIELDS:
        by_table.setdefault(table, []).append(f"json:{column}")
    for table, column in AUDIT_REDACTION_FIELDS:
        by_table.setdefault(table, []).append(f"audit:{column}")
    for table, column in CONTACT_FREE_TEXT_FIELDS:
        by_table.setdefault(table, []).append(f"contact_free_text:{column}")
    for table, arguments in by_table.items():
        args = ", ".join("'" + argument + "'" for argument in arguments)
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_contact_write_guard
            BEFORE INSERT OR UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_plaintext_contact_write({args})
            """
        )


def _drop_write_guards() -> None:
    for table in sorted(
        {table for table, _field, _length, _nullable in CONTACT_FIELDS}
        | {table for table, _column in SNAPSHOT_FIELDS}
        | {table for table, _column in AUDIT_REDACTION_FIELDS}
        | {table for table, _column in CONTACT_FREE_TEXT_FIELDS}
    ):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_contact_write_guard ON {table}"
        )


def upgrade() -> None:
    # This revision is deliberately schema-only. Conversion requires a separate
    # reviewed operator command after all legacy writers have been stopped.
    for table, field, _old_length, _nullable in CONTACT_FIELDS:
        op.alter_column(
            table,
            field,
            existing_type=sa.String(length=_old_length),
            type_=sa.Text(),
            existing_nullable=_nullable,
        )
        op.add_column(
            table,
            sa.Column(f"{field}_blind_index", sa.String(length=64), nullable=True),
        )

    # The new account identity and invitation/subscriber constraints are over
    # keyed indexes, never randomized ciphertext.
    op.drop_index("ix_users_email", table_name="users")
    op.create_unique_constraint(
        "uq_users_email_blind_index", "users", ["email_blind_index"]
    )

    op.drop_constraint("uq_subscribers_email", "subscribers", type_="unique")
    op.create_unique_constraint(
        "uq_subscribers_email", "subscribers", ["email_blind_index"]
    )

    op.drop_index(
        "ix_provider_invitations_provider_email",
        table_name="provider_invitations",
    )
    op.drop_index(
        "uq_provider_invitations_active_provider_email",
        table_name="provider_invitations",
    )
    op.create_index(
        "ix_provider_invitations_provider_email_blind_index",
        "provider_invitations",
        ["provider_id", "recipient_email_blind_index"],
    )
    op.create_index(
        "uq_provider_invitations_active_provider_email",
        "provider_invitations",
        ["provider_id", "recipient_email_blind_index"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'ACCEPTED')"),
    )

    unique_index_fields = {
        ("users", "email"),
        ("subscribers", "email"),
    }
    for table, field, _old_length, _nullable in CONTACT_FIELDS:
        if (table, field) in unique_index_fields:
            continue
        if table == "provider_invitations" and field == "recipient_email":
            # The additional composite and partial indexes above preserve the
            # former exact-match access path.
            pass
        op.create_index(
            conv(f"ix_{table}_{field}_blind_index"),
            table,
            [f"{field}_blind_index"],
        )

    op.create_table(
        "contact_encryption_migration_state",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("rows_examined", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_changed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("scalar_values_encrypted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("snapshots_protected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("historical_copies_redacted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("audit_metadata_redacted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cutover_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_contact_encryption_state_singleton"),
        sa.CheckConstraint(
            "state IN ('pending', 'converting', 'verified', 'complete')",
            name="ck_contact_encryption_state_value",
        ),
    )
    op.execute(
        "INSERT INTO contact_encryption_migration_state (id) VALUES (1)"
    )
    _create_guard_functions()
    _create_write_guards()


def downgrade() -> None:
    bind = op.get_bind()
    state = bind.execute(
        sa.text(
            """
            SELECT state, cutover_completed_at
            FROM contact_encryption_migration_state
            WHERE id = 1
            """
        )
    ).mappings().first()
    if state and (
        state["state"] != "pending" or state["cutover_completed_at"] is not None
    ):
        raise RuntimeError(
            "Contact encryption migration has started; downgrade is refused."
        )

    encrypted_values = 0
    for table, field, _old_length, _nullable in CONTACT_FIELDS:
        encrypted_values += bind.execute(
            sa.text(
                f"""
                SELECT count(*)
                FROM {table}
                WHERE {field} LIKE 'ecv1:%'
                   OR {field}_blind_index IS NOT NULL
                """
            )
        ).scalar_one()
    for table, column in SNAPSHOT_FIELDS:
        encrypted_values += bind.execute(
            sa.text(
                f"""
                SELECT count(*)
                FROM {table}
                WHERE {column}::text LIKE '%"v1.%'
                """
            )
        ).scalar_one()
    if encrypted_values:
        raise RuntimeError(
            "Encrypted contacts or blind indexes exist; downgrade would be unsafe."
        )

    _drop_write_guards()
    _drop_guard_functions()
    op.drop_table("contact_encryption_migration_state")

    # Invitation composite and partial indexes depend on the blind-index
    # column, so remove them before dropping that column below.
    op.drop_index(
        "uq_provider_invitations_active_provider_email",
        table_name="provider_invitations",
    )
    op.drop_index(
        "ix_provider_invitations_provider_email_blind_index",
        table_name="provider_invitations",
    )

    for table, field, _old_length, _nullable in CONTACT_FIELDS:
        if (table, field) in {("users", "email"), ("subscribers", "email")}:
            continue
        op.drop_index(
            conv(f"ix_{table}_{field}_blind_index"),
            table_name=table,
        )
        op.drop_column(table, f"{field}_blind_index")

    # Unique indexes are dropped separately from non-unique blind indexes.
    op.drop_constraint("uq_users_email_blind_index", "users", type_="unique")
    op.drop_column("users", "email_blind_index")
    op.drop_constraint("uq_subscribers_email", "subscribers", type_="unique")
    op.drop_column("subscribers", "email_blind_index")

    op.create_index(
        "ix_provider_invitations_provider_email",
        "provider_invitations",
        ["provider_id", "recipient_email"],
    )
    op.create_index(
        "uq_provider_invitations_active_provider_email",
        "provider_invitations",
        ["provider_id", "recipient_email"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'ACCEPTED')"),
    )

    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_unique_constraint("uq_subscribers_email", "subscribers", ["email"])
    for table, field, old_length, _nullable in CONTACT_FIELDS:
        op.alter_column(
            table,
            field,
            existing_type=sa.Text(),
            type_=sa.String(length=old_length),
        )