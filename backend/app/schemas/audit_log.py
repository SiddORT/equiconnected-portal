"""Display-safe schemas for the administrator activity log."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import PaginatedResponse


class AuditActor(BaseModel):
    id: UUID | None = None
    name: str
    email: str | None = None
    kind: str


class AuditChange(BaseModel):
    field: str
    before: Any = None
    after: Any = None


class AuditLogResponse(BaseModel):
    id: UUID
    action: str
    resource_type: str | None
    resource_id: str | None
    actor: AuditActor
    created_at: datetime
    summary: str
    changes: list[AuditChange] = []
    metadata: dict[str, Any] = {}
    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(PaginatedResponse[AuditLogResponse]):
    pass