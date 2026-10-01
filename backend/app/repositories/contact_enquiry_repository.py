"""Database access for persisted public contact enquiries."""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.time_standards import local_date_bounds
from app.models.contact_enquiry import ContactEnquiry
from app.models.enums import ContactEnquiryType
from app.schemas.contact import ContactMessageRequest


class ContactEnquirySaveError(Exception):
    """A contact enquiry could not be committed to durable storage."""


class ContactEnquiryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, body: ContactMessageRequest) -> ContactEnquiry:
        enquiry = ContactEnquiry(
            name=body.name,
            email=str(body.email),
            enquiry_type=body.enquiry_type,
            phone=body.phone,
            message=body.message,
        )
        try:
            self._db.add(enquiry)
            self._db.commit()
        except Exception as exc:
            self._db.rollback()
            raise ContactEnquirySaveError from exc
        return enquiry

    def get(self, enquiry_id: UUID) -> ContactEnquiry | None:
        return self._db.get(ContactEnquiry, enquiry_id)

    def list(
        self,
        *,
        search: str | None = None,
        enquiry_type: ContactEnquiryType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        timezone_name: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[ContactEnquiry], int]:
        filters: list[Any] = []
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    ContactEnquiry.name.ilike(pattern),
                    ContactEnquiry.email.ilike(pattern),
                    ContactEnquiry.phone.ilike(pattern),
                    ContactEnquiry.message.ilike(pattern),
                )
            )
        if enquiry_type is not None:
            filters.append(ContactEnquiry.enquiry_type == enquiry_type.value)
        start, end = local_date_bounds(date_from, date_to, timezone_name)
        if start is not None:
            filters.append(ContactEnquiry.submitted_at >= start)
        if end is not None:
            filters.append(ContactEnquiry.submitted_at < end)

        total = self._db.scalar(
            select(func.count()).select_from(ContactEnquiry).where(*filters)
        ) or 0
        rows = self._db.scalars(
            select(ContactEnquiry)
            .where(*filters)
            .order_by(ContactEnquiry.submitted_at.desc(), ContactEnquiry.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total