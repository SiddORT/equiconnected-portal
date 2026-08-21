"""Persistence for the portal's singleton system-settings record."""
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.system_settings import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_TIME_FORMAT,
    DEFAULT_TIMEZONE,
    SystemSettings,
)


class SystemSettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create(self) -> SystemSettings:
        settings = self._db.get(SystemSettings, 1)
        if settings is None:
            # The migration seeds this row. This atomic fallback also protects
            # databases upgraded before that seed existed and concurrent first
            # requests without leaving an uncommitted request-local default.
            self._db.execute(
                insert(SystemSettings)
                .values(
                    id=1,
                    timezone=DEFAULT_TIMEZONE,
                    date_format=DEFAULT_DATE_FORMAT,
                    time_format=DEFAULT_TIME_FORMAT,
                    created_at=func.now(),
                    updated_at=func.now(),
                )
                .on_conflict_do_nothing(index_elements=[SystemSettings.id])
            )
            self._db.commit()
            settings = self._db.get(SystemSettings, 1)
        assert settings is not None
        return settings

    def update(self, **values: str) -> SystemSettings:
        settings = self.get_or_create()
        for field, value in values.items():
            setattr(settings, field, value)
        self._db.flush()
        return settings