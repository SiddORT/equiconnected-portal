"""
Specialization CSV import/export service.

Responsibilities:
  - export_csv:            stream the current specialization list as UTF-8 CSV
  - template_csv:          static import template (headers + guidance row)
  - parse_and_validate:    parse an uploaded CSV and classify every row
  - commit_import:         insert valid rows in a single transaction
"""
import csv
import io
from dataclasses import dataclass, field
from datetime import date
from typing import Iterator

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.specialization import Specialization

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
REQUIRED_HEADERS = ["Name", "Description", "Status"]
EXPORT_HEADERS = ["ID", "Name", "Description", "Status", "Created At", "Updated At"]
VALID_STATUSES = {"ACTIVE", "INACTIVE"}
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ImportRowResult:
    row_num: int
    name: str
    description: str | None
    status: str
    state: str  # "valid" | "duplicate" | "invalid"
    reason: str | None = None


@dataclass
class ImportResult:
    imported: int
    skipped: int
    errors: int
    row_details: list[ImportRowResult] = field(default_factory=list)


# ── Errors ────────────────────────────────────────────────────────────────────

class ImportFileError(Exception):
    """Raised when the uploaded file cannot be processed at all."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize_cell(value: str) -> str:
    """Prevent CSV formula injection by prefixing dangerous cells with a tab."""
    if value and value[0] in ("=", "+", "-", "@"):
        return "\t" + value
    return value


def _normalise(name: str) -> str:
    return " ".join(name.split()).lower()


def validate_row_fields(row: "ImportRowResult") -> None:
    """
    Canonical field validation shared by preview parsing and commit-time
    re-validation. Normalizes name/status in place and downgrades the row to
    'invalid' when it fails the specialization contract.
    """
    row.name = " ".join((row.name or "").split())
    row.status = (row.status or "").strip().upper()
    if not row.name:
        row.state, row.reason = "invalid", "Name is required."
    elif len(row.name) > MAX_NAME_LENGTH:
        row.state, row.reason = "invalid", f"Name exceeds {MAX_NAME_LENGTH} characters."
    elif row.description and len(row.description) > MAX_DESCRIPTION_LENGTH:
        row.state, row.reason = (
            "invalid",
            f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters.",
        )
    elif row.status not in VALID_STATUSES:
        row.state, row.reason = (
            "invalid",
            f"Status must be ACTIVE or INACTIVE (got '{row.status or 'empty'}').",
        )


def export_filename() -> str:
    return f"equiconnected-specializations-{date.today().isoformat()}.csv"


# ── Export ────────────────────────────────────────────────────────────────────

def export_csv(
    db: Session,
    *,
    search: str | None = None,
    is_active: bool | None = None,
) -> Iterator[str]:
    """Yield CSV lines (UTF-8 text) for all matching specializations."""
    stmt = select(Specialization)
    if search:
        stmt = stmt.where(Specialization.name.ilike(f"%{search.strip()}%"))
    if is_active is not None:
        stmt = stmt.where(Specialization.is_active == is_active)
    stmt = stmt.order_by(Specialization.name)

    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(EXPORT_HEADERS)
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)

    for spec in db.scalars(stmt):
        writer.writerow(
            [
                str(spec.id),
                _sanitize_cell(spec.name),
                _sanitize_cell(spec.description or ""),
                "Active" if spec.is_active else "Inactive",
                spec.created_at.isoformat() if spec.created_at else "",
                spec.updated_at.isoformat() if spec.updated_at else "",
            ]
        )
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

    # ACTIVITY_LOG_HOOK: record specialization CSV export (filters, row count, actor)


def template_csv() -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(REQUIRED_HEADERS)
    writer.writerow(
        [
            "Example: Cardiology (replace this row)",
            "Optional description text",
            "ACTIVE or INACTIVE",
        ]
    )
    return buf.getvalue()


# ── Import: parse & validate ──────────────────────────────────────────────────

def parse_and_validate(file_bytes: bytes, db: Session) -> list[ImportRowResult]:
    """Parse CSV bytes and classify each data row. Never writes to the DB."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ImportFileError("File exceeds the 5 MB size limit.")

    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportFileError("File is not valid UTF-8 encoded text.")

    try:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    except csv.Error as exc:
        raise ImportFileError(f"Malformed CSV file: {exc}")

    if not rows:
        raise ImportFileError("The CSV file is empty.")

    headers = [h.strip() for h in rows[0]]
    missing = [h for h in REQUIRED_HEADERS if h.lower() not in [x.lower() for x in headers]]
    if missing:
        raise ImportFileError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected headers: {', '.join(REQUIRED_HEADERS)}."
        )

    header_index = {h.lower(): i for i, h in enumerate(headers)}
    name_i = header_index["name"]
    desc_i = header_index["description"]
    status_i = header_index["status"]

    # Existing names (case-insensitive, whitespace-normalised)
    existing = {
        _normalise(n)
        for n in db.scalars(select(func.lower(Specialization.name))).all()
    }

    seen_in_file: set[str] = set()
    results: list[ImportRowResult] = []

    for idx, raw in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in raw):
            continue  # skip fully blank lines

        def cell(i: int) -> str:
            return raw[i].strip() if i < len(raw) else ""

        row = ImportRowResult(
            row_num=idx,
            name=cell(name_i),
            description=cell(desc_i) or None,
            status=cell(status_i),
            state="valid",
        )
        validate_row_fields(row)

        if row.state == "valid":
            key = _normalise(row.name)
            if key in existing:
                row.state, row.reason = (
                    "duplicate",
                    "A specialization with this name already exists.",
                )
            elif key in seen_in_file:
                row.state, row.reason = "duplicate", "Duplicate name within the uploaded file."
            else:
                seen_in_file.add(key)

        results.append(row)

    if not results:
        raise ImportFileError("The CSV file contains no data rows.")

    return results


# ── Import: commit ────────────────────────────────────────────────────────────

def commit_import(db: Session, validated_rows: list[ImportRowResult]) -> ImportResult:
    """Insert only rows with state == 'valid' inside a single transaction."""
    # Re-check duplicates against the live DB at commit time — the payload may
    # be stale (rows created between preview and confirm) or client-tampered.
    existing = {
        _normalise(n)
        for n in db.scalars(select(func.lower(Specialization.name))).all()
    }

    to_insert: list[ImportRowResult] = []
    for r in validated_rows:
        if r.state == "valid":
            key = _normalise(r.name)
            if key in existing:
                r.state = "duplicate"
                r.reason = "A specialization with this name already exists."
            else:
                existing.add(key)
                to_insert.append(r)

    skipped = [r for r in validated_rows if r.state != "valid"]

    try:
        for row in to_insert:
            db.add(
                Specialization(
                    name=row.name,
                    description=row.description,
                    is_active=(row.status == "ACTIVE"),
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    # ACTIVITY_LOG_HOOK: record specialization CSV import (imported/skipped counts, actor)

    return ImportResult(
        imported=len(to_insert),
        skipped=len(skipped),
        errors=len([r for r in skipped if r.state == "invalid"]),
        row_details=validated_rows,
    )
