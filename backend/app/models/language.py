"""Language master data and provider signup selections."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Language(Base):
    __tablename__ = "languages"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now")
    provider_languages: Mapped[list["ProviderLanguage"]] = relationship(back_populates="language")


class ProviderRegistrationLanguage(Base):
    __tablename__ = "provider_registration_languages"
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("provider_registration_applications.id", ondelete="CASCADE"), primary_key=True)
    language_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("languages.id", ondelete="RESTRICT"), primary_key=True)
    __table_args__ = (Index("ix_provider_registration_languages_language_id", "language_id"),)


class ProviderLanguage(Base):
    __tablename__ = "provider_languages"
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True)
    language_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("languages.id", ondelete="RESTRICT"), primary_key=True)
    __table_args__ = (Index("ix_provider_languages_language_id", "language_id"),)
    provider: Mapped["Provider"] = relationship(back_populates="provider_languages")
    language: Mapped[Language] = relationship(back_populates="provider_languages")