"""Request and response models for portal-wide time standards."""
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.system_settings import DATE_FORMATS, TIME_FORMATS


DateFormat = Literal["month_day_year", "day_month_year", "year_month_day"]
TimeFormat = Literal["12_hour", "24_hour"]


class SystemSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timezone: str
    date_format: DateFormat
    time_format: TimeFormat


class SystemSettingsUpdate(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)
    date_format: DateFormat
    time_format: TimeFormat

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        timezone_name = value.strip()
        if not timezone_name:
            raise ValueError("Timezone is required.")
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone.") from exc
        return timezone_name


assert set(DateFormat.__args__) == DATE_FORMATS
assert set(TimeFormat.__args__) == TIME_FORMATS