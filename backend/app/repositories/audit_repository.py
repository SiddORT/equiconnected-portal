"""
Audit log data access.
"""
import ipaddress
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


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
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=_sanitize_ip(ip_address),
            user_agent=user_agent,
            event_metadata=metadata,
        )
        self._db.add(entry)
        self._db.flush()
        return entry
