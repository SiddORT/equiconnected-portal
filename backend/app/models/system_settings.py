"""Singleton portal-wide presentation and calendar standards."""
from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import TimestampMixin


DEFAULT_TIMEZONE = "UTC"
DEFAULT_DATE_FORMAT = "month_day_year"
DEFAULT_TIME_FORMAT = "12_hour"

DATE_FORMATS = frozenset({"month_day_year", "day_month_year", "year_month_day"})
TIME_FORMATS = frozenset({"12_hour", "24_hour"})


class SystemSettings(TimestampMixin, Base):
    """
    One global settings row. The fixed primary key makes the singleton invariant
    explicit and avoids an ambiguous "latest" record.
    """

    __tablename__ = "system_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_system_settings_singleton"),
        CheckConstraint(
            "date_format IN ('month_day_year', 'day_month_year', 'year_month_day')",
            name="ck_system_settings_date_format",
        ),
        CheckConstraint(
            "time_format IN ('12_hour', '24_hour')",
            name="ck_system_settings_time_format",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default=DEFAULT_TIMEZONE, server_default=DEFAULT_TIMEZONE
    )
    date_format: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_DATE_FORMAT,
        server_default=DEFAULT_DATE_FORMAT,
    )
    time_format: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=DEFAULT_TIME_FORMAT,
        server_default=DEFAULT_TIME_FORMAT,
    )