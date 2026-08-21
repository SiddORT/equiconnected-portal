"""Public read and administrator-only write endpoints for time standards."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.schemas.system_settings import SystemSettingsResponse, SystemSettingsUpdate


public_router = APIRouter(prefix="/system-settings", tags=["System settings"])
admin_router = APIRouter(
    prefix="/admin/system-settings",
    tags=["System settings"],
    dependencies=[Depends(require_role("admin"))],
)
_DB = Annotated[Session, Depends(get_db)]


def _read_settings(db: Session) -> SystemSettingsResponse:
    settings = SystemSettingsRepository(db).get_or_create()
    # A missing row is initialized on the first read, so defaults are durable
    # across process restarts rather than an in-memory fallback.
    db.commit()
    db.refresh(settings)
    return SystemSettingsResponse.model_validate(settings)


@public_router.get("", response_model=SystemSettingsResponse)
def get_public_system_settings(db: _DB) -> SystemSettingsResponse:
    """Presentation settings are intentionally readable by all display clients."""
    return _read_settings(db)


@admin_router.get("", response_model=SystemSettingsResponse)
def get_admin_system_settings(db: _DB) -> SystemSettingsResponse:
    return _read_settings(db)


@admin_router.patch("", response_model=SystemSettingsResponse)
def update_system_settings(
    body: SystemSettingsUpdate,
    db: _DB,
) -> SystemSettingsResponse:
    """Only administrators can change the shared time presentation standard."""
    settings = SystemSettingsRepository(db).update(**body.model_dump())
    db.commit()
    db.refresh(settings)
    return SystemSettingsResponse.model_validate(settings)