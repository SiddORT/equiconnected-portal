"""Shared, bounded rolling-window state for anonymous postal lookups."""
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PostalLookupRateLimit(Base):
    __tablename__ = "postal_lookup_rate_limits"

    # Store a digest rather than the caller's raw address.
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[list[datetime]] = mapped_column(
        ARRAY(DateTime(timezone=True)), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )