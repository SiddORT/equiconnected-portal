"""
Audit log data access.
"""
import ipaddress
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.audit_log import AuditLog
from app.models.user import User


@dataclass(frozen=True)
class AuditContext:
    user_id: uuid.UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    actor_type: str = "admin"


def context_from_request(request: Any, user_id: uuid.UUID | None = None,
                         actor_type: str = "admin") -> AuditContext:
    client = getattr(request, "client", None)
    return AuditContext(
        user_id=user_id,
        ip_address=client.host if client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        actor_type=actor_type,
    )


_REDACTED = "[redacted]"
_SENSITIVE_PARTS = (
    "password", "token", "secret", "credential", "authorization", "cookie",
    "invitation_url", "raw_url", "file", "upload", "content", "storage_reference",
    "recipient_email", "email", "phone",
)
_DISPLAY_SAFE_FIELDS = {
    "name", "provider_name", "provider_type", "status", "publication_status",
    "visit_stability", "is_active", "professional_title", "years_experience",
    "display_order", "is_primary", "is_thumbnail", "specialization_id",
    "specialization_name", "organization_id", "organization_name",
    "relationship_status", "result_count", "exported_count", "imported_count",
    "skipped_count", "error_count", "updated_fields", "field", "approval_status",
}


def _safe_value(key: str, value: Any) -> Any:
    lower_key = key.lower().split(".")[-1]
    if any(part in lower_key for part in _SENSITIVE_PARTS):
        return _REDACTED
    # Values recorded as changed fields are intentionally restrictive. Names,
    # statuses, and simple flags help admins understand a change; free text,
    # addresses, contacts, files, and arbitrary request data do not.
    if lower_key not in _DISPLAY_SAFE_FIELDS:
        return _REDACTED
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (uuid.UUID, date, datetime)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(key, item) for item in value]
    return str(value)


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Keep audit metadata structured while removing secrets and raw payloads."""
    if not metadata:
        return {}
    return {str(key): _safe_value(str(key), value) for key, value in metadata.items()}


def _sanitize_ip(ip: str | None) -> str | None:
    """
    Return *ip* only when it is a valid IPv4 or IPv6 address string.
    Returns None for None, hostnames, or test client placeholders so that the
    PostgreSQL INET column never receives an invalid value.
    """
    if ip is None:
        return None
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return None


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def log(
        self,
        action: str,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor_type: str = "admin",
        summary: str | None = None,
        changes: list[dict[str, Any]] | None = None,
    ) -> AuditLog:
        safe_metadata = sanitize_metadata(metadata)
        if summary is not None:
            safe_metadata["summary"] = summary
        if changes:
            safe_metadata["changes"] = [
                {
                    "field": str(change.get("field", "")),
                    "before": _safe_value(str(change.get("field", "")), change.get("before")),
                    "after": _safe_value(str(change.get("field", "")), change.get("after")),
                }
                for change in changes
            ]
        entry = AuditLog(
            action=action,
            user_id=user_id,
            actor_type=actor_type,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=_sanitize_ip(ip_address),
            user_agent=user_agent,
            event_metadata=safe_metadata,
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    def record(
        self,
        action: str,
        *,
        context: AuditContext | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        summary: str | None = None,
        changes: list[dict[str, Any]] | None = None,
    ) -> AuditLog:
        ctx = context or AuditContext(actor_type="system")
        return self.log(
            action=action,
            user_id=ctx.user_id,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            actor_type=ctx.actor_type,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            summary=summary,
            changes=changes,
        )

    @staticmethod
    def _bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
        start = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else None
        end = datetime.combine(date_to, time.max, tzinfo=timezone.utc) if date_to else None
        return start, end

    def list(self, *, date_from: date | None = None, date_to: date | None = None,
             page: int = 1, page_size: int = 25) -> tuple[list[AuditLog], int]:
        start, end = self._bounds(date_from, date_to)
        filters = []
        if start:
            filters.append(AuditLog.created_at >= start)
        if end:
            filters.append(AuditLog.created_at <= end)
        total = self._db.scalar(
            select(func.count()).select_from(AuditLog).where(*filters)
        ) or 0
        rows = self._db.scalars(
            select(AuditLog)
            .options(selectinload(AuditLog.user))
            .where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total
