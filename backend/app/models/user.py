"""
User model.
Covers admin users for Phase 1.
Future phases extend roles to cover hospital and visitor users.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, event, inspect, update
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import TimestampMixin


PUBLIC_ACCOUNT_ROLE_NAMES = ("horse_owner", "stable_manager")
PROVIDER_ACCOUNT_ROLE_NAME = "provider"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    # Argon2id hash — NEVER store plaintext, NEVER return via API
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mobile_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_successful_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Only invitation-created provider accounts use this temporary state. It is
    # intentionally distinct from account activation so an admin-disabled user
    # can never be activated by redeeming an old public setup URL.
    provider_portal_setup_pending: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="users")  # noqa: F821
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # noqa: F821
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        "AuditLog", back_populates="user"
    )
    role_assignments: Mapped[list["UserRole"]] = relationship(  # noqa: F821
        "UserRole", back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(  # noqa: F821
        "EmailVerificationToken", back_populates="user", cascade="all, delete-orphan"
    )
    stable_profile: Mapped["StableProfile | None"] = relationship(  # noqa: F821
        "StableProfile", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    horses: Mapped[list["Horse"]] = relationship(  # noqa: F821
        "Horse", back_populates="user", cascade="all, delete-orphan"
    )
    provider_reviews: Mapped[list["ProviderReview"]] = relationship(  # noqa: F821
        "ProviderReview", back_populates="member", cascade="all, delete-orphan"
    )
    provider_registration_application: Mapped["ProviderRegistrationApplication | None"] = relationship(  # noqa: F821
        "ProviderRegistrationApplication",
        foreign_keys="ProviderRegistrationApplication.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    provider_portal_invitation: Mapped["ProviderInvitation | None"] = relationship(  # noqa: F821
        "ProviderInvitation",
        foreign_keys="ProviderInvitation.portal_user_id",
        back_populates="portal_user",
        uselist=False,
    )
    provider_portal_setup_tokens: Mapped[list["ProviderPortalSetupToken"]] = relationship(  # noqa: F821
        "ProviderPortalSetupToken", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        parts = filter(None, [self.first_name, self.last_name])
        return " ".join(parts) or self.email

    @property
    def is_public_registrant(self) -> bool:
        """Whether this account is governed by the public registration workflow."""
        return self.role.name in PUBLIC_ACCOUNT_ROLE_NAMES

    @property
    def is_provider_registrant(self) -> bool:
        """Whether this account is governed by provider application review."""
        return self.role.name == PROVIDER_ACCOUNT_ROLE_NAME

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role_id}>"


class UserRole(Base):
    """Relational role assignments for public accounts that may hold multiple roles."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="role_assignments")
    role: Mapped["Role"] = relationship("Role", back_populates="user_assignments")  # noqa: F821


@event.listens_for(Session, "before_flush")
def invalidate_provider_setup_tokens_on_deactivation(session, _flush_context, _instances):
    """A real account disable revokes public setup URLs in the same transaction."""
    for candidate in session.dirty:
        if not isinstance(candidate, User):
            continue
        state = inspect(candidate)
        if (
            candidate.is_active is False
            and state.attrs.is_active.history.has_changes()
            and state.persistent
        ):
            candidate.provider_portal_setup_pending = False
            # Import lazily to keep the bidirectional model relationship free
            # of module-import cycles.
            from app.models.invitation import ProviderPortalSetupToken

            session.execute(
                update(ProviderPortalSetupToken)
                .where(
                    ProviderPortalSetupToken.user_id == candidate.id,
                    ProviderPortalSetupToken.used_at.is_(None),
                    ProviderPortalSetupToken.invalidated_at.is_(None),
                )
                .values(invalidated_at=datetime.now(timezone.utc))
            )


class EmailVerificationToken(TimestampMixin, Base):
    """Hashed, expiring, single-use token used to activate a public account."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="email_verification_tokens")
