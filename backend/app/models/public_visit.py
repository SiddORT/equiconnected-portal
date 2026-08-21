"""Daily aggregate page visits for the public EquiConnected landing page."""
from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import TimestampMixin


class PublicVisitDaily(TimestampMixin, Base):
    """Stores counts only; no IP address, email, or visitor identifier is retained."""

    __tablename__ = "public_visit_daily"

    visit_date: Mapped[date] = mapped_column(Date, primary_key=True)
    visit_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )