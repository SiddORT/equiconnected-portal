"""Operator-only, preview-first reset of development application rows.

Never call this from application startup or deployment. The operator must name
the actual database/schema and supply a verified pg_dump archive.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal
from scripts.reset_non_admin_users import _load_users


PRESERVED = frozenset({"roles", "languages", "specializations", "system_settings", "alembic_version"})
EXPECTED = frozenset(Base.metadata.tables) | {"alembic_version"}


class ResetError(Exception):
    pass


@dataclass(frozen=True)
class Plan:
    database: str
    schema: str
    counts: dict[str, int]
    retained: tuple[tuple[str, bool, tuple[str, ...]], ...]
    keep_assignments: int
    preserved_digest: str
    full_digest: str
    fingerprint: str

    @property
    def confirmation(self):
        return f"RESET_DEVELOPMENT_DATA:{self.database}:{self.schema}"


def _identity(db: Session, database: str, schema: str) -> None:
    if get_settings().ENVIRONMENT != "development" or db.bind.dialect.name != "postgresql":
        raise ResetError("Only a PostgreSQL development connection may be reset.")
    actual = db.execute(text("select current_database(), current_schema()")).one()
    if actual != (database, schema):
        raise ResetError("Database/schema identity does not match the explicitly named target.")
    if schema.startswith("pg_") or schema == "information_schema":
        raise ResetError("System schemas cannot be reset.")


def _schema(db: Session, schema: str) -> tuple[list[str], dict[str, set[str]]]:
    inspector = inspect(db.connection())
    tables = set(inspector.get_table_names(schema=schema))
    if tables != EXPECTED:
        raise ResetError(f"Unknown or missing tables: {', '.join(sorted(tables ^ EXPECTED))}")
    if inspector.get_view_names(schema=schema) or inspector.get_materialized_view_names(schema=schema):
        raise ResetError("Unexpected views in reset schema; review before resetting.")
    graph = {name: set() for name in tables}
    for name in tables:
        actual = {
            (tuple(fk["constrained_columns"]), fk["referred_schema"] or schema,
             fk["referred_table"], tuple(fk["referred_columns"]), fk["options"].get("ondelete"))
            for fk in inspector.get_foreign_keys(name, schema=schema)
        }
        expected = {
            (tuple(col.name for col in constraint.columns), schema,
             constraint.referred_table.name,
             tuple(element.column.name for element in constraint.elements), constraint.ondelete)
            for constraint in Base.metadata.tables[name].foreign_key_constraints
        } if name != "alembic_version" else set()
        if actual != expected:
            raise ResetError(f"Unknown or changed foreign keys on {name}.")
        graph[name] = {fk[2] for fk in actual if fk[1] == schema}
    # External references can be restrictive even when every local FK is known.
    external = db.execute(text("""
        SELECT DISTINCT source_ns.nspname, source.relname
        FROM pg_constraint c
        JOIN pg_class target ON target.oid = c.confrelid
        JOIN pg_namespace target_ns ON target_ns.oid = target.relnamespace
        JOIN pg_class source ON source.oid = c.conrelid
        JOIN pg_namespace source_ns ON source_ns.oid = source.relnamespace
        WHERE c.contype = 'f' AND target_ns.nspname = :schema
          AND source_ns.nspname <> :schema
    """), {"schema": schema}).all()
    if external:
        raise ResetError("Other schemas reference reset tables; refusing reset.")
    return sorted(tables), graph


def _digest(db: Session, schema: str, retained_ids: list) -> str:
    """Digest preserved rows without recording credential hashes or other values."""
    digest = hashlib.sha256()
    for table in sorted(PRESERVED - {"alembic_version"} | {"users", "user_roles", "alembic_version"}):
        rows = db.execute(text(f'SELECT * FROM "{schema}"."{table}"')).mappings().all()
        if table == "users":
            rows = [row for row in rows if row["id"] in retained_ids]
        if table == "user_roles":
            admin_role = db.scalar(text(f'SELECT id FROM "{schema}".roles WHERE name = \'admin\''))
            rows = [row for row in rows if row["user_id"] in retained_ids and row["role_id"] == admin_role]
        payload = sorted(json.dumps(dict(row), sort_keys=True, default=str) for row in rows)
        digest.update(json.dumps([table, payload]).encode())
    return digest.hexdigest()


def _complete_digest(db: Session, schema: str, tables: list[str]) -> str:
    """Hash every value, not just row counts, without exposing stored data."""
    digest = hashlib.sha256()
    for table in tables:
        rows = db.execute(text(f'SELECT * FROM "{schema}"."{table}"')).mappings()
        payload = sorted(json.dumps(dict(row), sort_keys=True, default=str) for row in rows)
        digest.update(json.dumps([table, payload]).encode())
    # A restored serial/identity sequence must also resume at the same state.
    sequences = db.scalars(text(
        "SELECT sequencename FROM pg_sequences WHERE schemaname = :schema ORDER BY sequencename"
    ), {"schema": schema}).all()
    for sequence in sequences:
        state = db.execute(text(f'SELECT last_value, is_called FROM "{schema}"."{sequence}"')).one()
        digest.update(json.dumps([sequence, *state], default=str).encode())
    return digest.hexdigest()


def build_plan(db: Session, *, database: str, schema: str) -> Plan:
    _identity(db, database, schema)
    tables, _ = _schema(db, schema)
    accounts = _load_users(db, lock=False)
    retained_users = [
        user for user in accounts
        if user.role.name == "admin" or any(a.role.name == "admin" for a in user.role_assignments)
    ]
    if not any(user.is_active for user in retained_users):
        raise ResetError("No active administrator would remain.")
    retained_ids = [user.id for user in retained_users]
    retained = tuple(
        (user.email, user.is_active,
         tuple(sorted({user.role.name} | {a.role.name for a in user.role_assignments})))
        for user in retained_users
    )
    admin_role = db.scalar(text(f'SELECT id FROM "{schema}".roles WHERE name = \'admin\''))
    keep_assignments = sum(
        a.role_id == admin_role for user in retained_users for a in user.role_assignments
    )
    counts = {
        table: int(db.scalar(text(f'SELECT count(*) FROM "{schema}"."{table}"')))
        for table in tables
    }
    preserved_digest = _digest(db, schema, retained_ids)
    full_digest = _complete_digest(db, schema, tables)
    payload = (database, schema, counts, retained, keep_assignments,
               preserved_digest, full_digest)
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return Plan(database, schema, counts, retained, keep_assignments,
                preserved_digest, full_digest, fingerprint)


def format_plan(plan: Plan) -> str:
    lines = [
        f"Development reset preview: database={plan.database} schema={plan.schema}",
        "Retained administrators (email, active, roles):",
        *(f"  {email} | active={active} | roles={','.join(roles)}"
          for email, active, roles in plan.retained),
        "Table | current | keep | delete",
    ]
    for name, count in sorted(plan.counts.items()):
        keep = (count if name in PRESERVED else
                len(plan.retained) if name == "users" else
                plan.keep_assignments if name == "user_roles" else 0)
        lines.append(f"  {name}: {count} | {keep} | {count - keep}")
    return "\n".join(lines)


def make_backup(db: Session, plan: Plan, path: Path) -> None:
    url = db.bind.url
    if any(os.environ.get(key) != str(value) for key, value in (
        ("PGDATABASE", url.database), ("PGHOST", url.host),
        ("PGPORT", url.port or 5432), ("PGUSER", url.username)
    )):
        raise ResetError("pg_dump connection variables do not match the application connection.")
    if path.exists() or Path(str(path) + ".json").exists():
        raise ResetError("Backup path or manifest already exists; use a new path.")
    if not path.parent.is_dir():
        raise ResetError("Backup directory does not exist.")
    # The archive contains credentials and personal data: restrict permissions.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        subprocess.run(["pg_dump", "--dbname", plan.database,
                        "--format=custom", "--no-owner", "--no-acl",
                        f"--schema={plan.schema}", "--file", str(path)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _restore_test(db, plan, path)
        db.rollback()
        if build_plan(db, database=plan.database, schema=plan.schema).fingerprint != plan.fingerprint:
            raise ResetError("Data changed during backup; discard archive and preview again.")
        manifest = Path(str(path) + ".json")
        fd = os.open(manifest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with path.open("rb") as archive:
            archive_digest = hashlib.file_digest(archive, "sha256").hexdigest()
        with os.fdopen(fd, "w") as output:
            json.dump({"database": plan.database, "schema": plan.schema,
                       "fingerprint": plan.fingerprint, "archive_sha256": archive_digest}, output)
    except Exception as exc:
        path.unlink(missing_ok=True)
        Path(str(path) + ".json").unlink(missing_ok=True)
        raise ResetError("Backup creation or verification failed; no reset performed.") from exc


def _restore_test(db: Session, plan: Plan, path: Path) -> None:
    """Actually restore the archive into a disposable DB and compare its scope."""
    scratch = "reset_check_" + uuid.uuid4().hex
    command = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
               "check": True}
    created = False
    try:
        subprocess.run(["createdb", "--maintenance-db", plan.database, scratch],
                       **command)
        created = True
        # New PostgreSQL databases already have an empty public schema, while
        # pg_dump includes CREATE SCHEMA public. Remove only that empty schema
        # in the disposable DB before restoring it.
        if plan.schema == "public":
            scratch_engine = create_engine(db.bind.url.set(database=scratch))
            try:
                with scratch_engine.begin() as connection:
                    connection.execute(text("DROP SCHEMA public"))
            finally:
                scratch_engine.dispose()
        subprocess.run(["pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
                        "--dbname", scratch, str(path)], **command)
        scratch_engine = create_engine(db.bind.url.set(database=scratch))
        try:
            with sessionmaker(bind=scratch_engine)() as restored:
                restored.execute(text(f'SET search_path TO "{plan.schema}"'))
                restored_plan = build_plan(restored, database=scratch, schema=plan.schema)
                if restored_plan.counts != plan.counts:
                    raise ResetError("Restored backup counts differ from the preview.")
                if (restored_plan.retained != plan.retained or
                        restored_plan.preserved_digest != plan.preserved_digest or
                        restored_plan.full_digest != plan.full_digest):
                    raise ResetError("Restored backup contents differ from preview.")
        finally:
            scratch_engine.dispose()
    finally:
        if created:
            subprocess.run(["dropdb", "--if-exists", "--force", "--maintenance-db",
                            plan.database, scratch], **command)


def _verify_backup(plan: Plan, path: Path) -> None:
    try:
        manifest = json.loads(Path(str(path) + ".json").read_text())
        with path.open("rb") as archive:
            digest = hashlib.file_digest(archive, "sha256").hexdigest()
        if manifest != {"database": plan.database, "schema": plan.schema,
                        "fingerprint": plan.fingerprint, "archive_sha256": digest}:
            raise ResetError("Backup does not match the current target and preview.")
        subprocess.run(["pg_restore", "--file", os.devnull, str(path)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise ResetError("Missing, unreadable, or invalid backup archive/manifest.") from exc


def _delete_order(graph: dict[str, set[str]]) -> list[str]:
    remaining = set(graph) - PRESERVED - {"users", "user_roles"}
    order = []
    while remaining:
        ready = sorted(t for t in remaining if not any(
            t in graph[other] for other in remaining if other != t
        ))
        if not ready:
            raise ResetError("Cyclic table references require manual review.")
        order.extend(ready)
        remaining.difference_update(ready)
    return order


def execute_reset(db: Session, *, database: str, schema: str, confirmation: str | None,
                  backup: Path) -> tuple[Plan, Plan]:
    db.rollback()
    try:
        before = build_plan(db, database=database, schema=schema)
        if confirmation != before.confirmation:
            raise ResetError(f"Confirmation required: --confirm {before.confirmation}")
        _verify_backup(before, backup)
        db.rollback()
        # Lock all reset tables before rechecking the entire scope; reads are
        # still allowed, but inserts/updates/deletes wait until commit.
        db.execute(text("LOCK TABLE " + ", ".join(
            f'"{schema}"."{table}"' for table in sorted(EXPECTED)
        ) + " IN SHARE ROW EXCLUSIVE MODE"))
        locked = build_plan(db, database=database, schema=schema)
        if locked.fingerprint != before.fingerprint:
            raise ResetError("Scope changed before locking; create a new preview and backup.")
        _, graph = _schema(db, schema)
        for table in _delete_order(graph):
            db.execute(text(f'DELETE FROM "{schema}"."{table}"'))
        db.execute(text(f'DELETE FROM "{schema}".user_roles ur WHERE NOT EXISTS '
                        f'(SELECT 1 FROM "{schema}".users u JOIN "{schema}".roles r '
                        'ON r.id = ur.role_id WHERE u.id = ur.user_id AND r.name = \'admin\')'))
        db.execute(text(f'DELETE FROM "{schema}".users u WHERE NOT EXISTS '
                        f'(SELECT 1 FROM "{schema}".roles r WHERE r.id = u.role_id AND r.name = \'admin\') '
                        f'AND NOT EXISTS (SELECT 1 FROM "{schema}".user_roles ur '
                        f'JOIN "{schema}".roles r ON r.id = ur.role_id '
                        "WHERE ur.user_id = u.id AND r.name = 'admin')"))
        after = build_plan(db, database=database, schema=schema)
        for table, count in after.counts.items():
            expected = (before.counts[table] if table in PRESERVED else
                        len(before.retained) if table == "users" else
                        before.keep_assignments if table == "user_roles" else 0)
            if count != expected:
                raise ResetError(f"Post-reset verification failed for {table}.")
        if after.retained != before.retained or after.preserved_digest != before.preserved_digest:
            raise ResetError("Preserved records changed during reset.")
        db.commit()
        return before, after
    except Exception:
        db.rollback()
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--create-backup", type=Path)
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        plan = build_plan(db, database=args.database, schema=args.schema)
        print(format_plan(plan))
        if args.create_backup:
            make_backup(db, plan, args.create_backup)
            print(f"Verified backup: {args.create_backup} (keep archive and .json manifest secure).")
        if args.confirm is not None:
            if args.create_backup or not args.backup:
                raise ResetError("Execution needs --backup and cannot create the backup in the same invocation.")
            before, after = execute_reset(db, database=args.database, schema=args.schema,
                                          confirmation=args.confirm, backup=args.backup)
            print("Reset committed. After counts and retained administrators:")
            print(format_plan(after))
        else:
            print(f"No changes made. Back up first, then confirm with {plan.confirmation}.")
        return 0
    except ResetError as exc:
        print(f"Reset refused: {exc}", file=sys.stderr)
        return 2
    except Exception:
        db.rollback()
        print("Reset failed; transaction rolled back. Check target and backup.", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())