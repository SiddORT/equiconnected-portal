"""
Specialization model — independent master-data entity.

Hospitals, clinics, and doctors will later reference specializations
through many-to-many join tables (hospital_specializations, etc.).
Those relationship tables are NOT created in this phase.
"""
import uuid

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import TimestampMixin


class Specialization(TimestampMixin, Base):
    __tablename__ = "specializations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_specializations_name"),
        Index("ix_specializations_name", "name"),
        Index("ix_specializations_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Specialization id={self.id} name={self.name!r} active={self.is_active}>"
