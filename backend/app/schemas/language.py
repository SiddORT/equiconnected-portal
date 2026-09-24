from uuid import UUID
import re
from pydantic import BaseModel, Field, field_validator


class LanguageResponse(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool
    model_config = {"from_attributes": True}


class LanguageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=2, max_length=10)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Language name is required.")
        return value

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2,4})?", value):
            raise ValueError("Enter a valid language code (for example, en or zh-hans).")
        return value


class LanguageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=2, max_length=10)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return LanguageCreate.clean_name(value) if value is not None else None

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        return LanguageCreate.clean_code(value) if value is not None else None