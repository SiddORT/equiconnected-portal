"""
Shared Pydantic schemas used across the API.
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PaginationMeta


class MessageResponse(BaseModel):
    message: str


def make_error(code: str, message: str, field: str | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "field": field}}
