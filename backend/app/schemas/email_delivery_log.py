"""Display-safe administrator email delivery log schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import PaginatedResponse


class EmailDeliveryLogResponse(BaseModel):
    id: UUID
    recipient_email: str
    purpose: str
    status: str
    failure_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailDeliveryLogListResponse(PaginatedResponse[EmailDeliveryLogResponse]):
    pass