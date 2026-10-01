"""Member-only password recovery with serialized, single-use links."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.models.member_recovery_token import MemberPasswordRecoveryToken
from app.models.invitation import ProviderInvitation
from app.models.provider import DirectProviderPortalAccess
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.email_delivery_repository import EmailDeliveryRepository, safe_failure_message
from app.services.email_service import EmailService


MEMBER_RECOVERY_COOLDOWN = timedelta(minutes=5)
MEMBER_PASSWORD_RECOVERY_ACKNOWLEDGEMENT = (
    "If an eligible member account matches this email, a password reset link will be sent when available."
)


class MemberPasswordRecoveryError(Exception):
    """Base exception for member password recovery."""


class MemberPasswordRecoveryUnavailableError(MemberPasswordRecoveryError):
    pass


class MemberPasswordRecoveryCooldownError(MemberPasswordRecoveryError):
    pass


class MemberPasswordRecoveryDeliveryError(MemberPasswordRecoveryError):
    pass


class MemberPasswordRecoveryTokenInvalidError(MemberPasswordRecoveryError):
    pass


class MemberPasswordRecoveryTokenExpiredError(MemberPasswordRecoveryError):
    pass


class MemberPasswordRecoveryTokenUsedError(MemberPasswordRecoveryError):
    pass


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MemberPasswordRecoveryService:
    """Issue and redeem recovery tokens only for active, verified member accounts."""

    def __init__(self, db: Session, email: EmailService | None = None) -> None:
        self.db = db
        self.email = email or EmailService()
        self.logs = EmailDeliveryRepository(db)
        self.audit = AuditRepository(db)

    def _locked_user(self, user_id: UUID) -> User | None:
        return self.db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update(of=User)
            .execution_options(populate_existing=True)
        )

    def _is_eligible(self, user: User) -> bool:
        """Require only member roles, including the legacy primary role column."""
        if not user.is_active or user.email_verified_at is None:
            return False
        # An account linked to any provider workflow must never be treated as
        # a member recovery identity, even if it also carries a member role.
        linked_provider_account = any(
            (
                self.db.scalar(
                    select(DirectProviderPortalAccess.provider_id).where(
                        DirectProviderPortalAccess.user_id == user.id
                    )
                )
                is not None,
                self.db.scalar(
                    select(ProviderInvitation.id).where(
                        ProviderInvitation.portal_user_id == user.id
                    ).limit(1)
                )
                is not None,
                self.db.scalar(
                    select(ProviderRegistrationApplication.id).where(
                        ProviderRegistrationApplication.user_id == user.id
                    )
                )
                is not None,
            )
        )
        if linked_provider_account:
            return False
        assigned_names = set(
            self.db.scalars(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
            ).all()
        )
        primary_role_name = self.db.scalar(
            select(Role.name).where(Role.id == user.role_id)
        )
        effective_names = assigned_names | ({primary_role_name} if primary_role_name else set())
        return bool(effective_names) and effective_names.issubset(
            set(PUBLIC_ACCOUNT_ROLE_NAMES)
        )

    def _recent_delivery(self, normalized_email: str, now: datetime) -> bool:
        latest = self.db.scalar(
            select(EmailDeliveryLog)
            .where(
                EmailDeliveryLog.recipient_email == normalized_email,
                EmailDeliveryLog.purpose == EmailPurpose.MEMBER_PASSWORD_RECOVERY.value,
                EmailDeliveryLog.status.in_(
                    (
                        EmailDeliveryStatus.PENDING.value,
                        EmailDeliveryStatus.SUCCESS.value,
                        EmailDeliveryStatus.FAILED.value,
                    )
                ),
            )
            .order_by(EmailDeliveryLog.created_at.desc(), EmailDeliveryLog.id.desc())
            .limit(1)
        )
        return latest is not None and now - latest.created_at < MEMBER_RECOVERY_COOLDOWN

    def request_for_email(self, email: str) -> bool:
        """Attempt background recovery without disclosing whether a member exists."""
        normalized_email = email.strip().lower()
        user_id = self.db.scalar(
            select(User.id).where(User.email == normalized_email)
        )
        if user_id is None:
            self.db.rollback()
            return False
        user = self._locked_user(user_id)
        if user is None or not self._is_eligible(user):
            self.db.rollback()
            return False
        try:
            self._issue_locked(user)
        except MemberPasswordRecoveryCooldownError:
            self.db.rollback()
            return False
        return True

    def request_for_current_member(self, user_id: UUID) -> None:
        """Issue a recovery link to the fresh session account, never client email."""
        user = self._locked_user(user_id)
        if user is None or not self._is_eligible(user):
            self.db.rollback()
            raise MemberPasswordRecoveryUnavailableError(
                "Password recovery is available only to active, verified member accounts."
            )
        try:
            self._issue_locked(user)
        except MemberPasswordRecoveryCooldownError:
            self.db.rollback()
            raise

    def _issue_locked(self, user: User) -> bool:
        """Hold the user lock from eligibility check through replacement and commit."""
        now = datetime.now(timezone.utc)
        normalized_email = user.email.strip().lower()
        if self._recent_delivery(normalized_email, now):
            raise MemberPasswordRecoveryCooldownError(
                "A password reset email was sent recently. Please wait a few minutes before retrying."
            )

        raw_token = secrets.token_urlsafe(48)
        expires_at = now + timedelta(
            hours=get_settings().MEMBER_PASSWORD_RECOVERY_EXPIRE_HOURS
        )
        token = MemberPasswordRecoveryToken(
            user_id=user.id,
            token_hash=_token_hash(raw_token),
            expires_at=expires_at,
        )
        self.db.add(token)
        self.db.flush()
        try:
            attempt_id = self.logs.record_durable_attempt(
                recipient_email=normalized_email,
                purpose=EmailPurpose.MEMBER_PASSWORD_RECOVERY,
            )
        except Exception as exc:
            self.db.rollback()
            raise MemberPasswordRecoveryDeliveryError(
                "Password recovery is temporarily unavailable. Please try again later."
            ) from exc

        recovery_url = f"{get_settings().public_link('/reset-password')}#token={raw_token}"
        try:
            self.email.send_member_password_recovery_email(
                normalized_email, recovery_url, expires_at
            )
        except Exception as exc:
            # The new token was never committed and the previous delivered link
            # remains untouched when SMTP fails.
            self.db.rollback()
            try:
                self.logs.complete_durable_attempt(
                    attempt_id,
                    status=EmailDeliveryStatus.FAILED,
                    failure_message=safe_failure_message(exc),
                )
            except Exception:
                pass
            raise MemberPasswordRecoveryDeliveryError(
                "Password reset email could not be sent. Please try again later."
            ) from exc

        self.db.execute(
            update(MemberPasswordRecoveryToken)
            .where(
                MemberPasswordRecoveryToken.user_id == user.id,
                MemberPasswordRecoveryToken.id != token.id,
                MemberPasswordRecoveryToken.used_at.is_(None),
                MemberPasswordRecoveryToken.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        self.audit.log(
            action="member.password_recovery_sent",
            user_id=user.id,
            actor_type="member",
            resource_type="user",
            resource_id=str(user.id),
            summary="Issued a member password reset link.",
        )
        self.db.commit()
        # A delivered, committed link remains usable even if delivery-log
        # finalization has a transient storage failure; its durable attempt
        # correctly remains pending for reconciliation.
        try:
            self.logs.complete_durable_attempt(
                attempt_id, status=EmailDeliveryStatus.SUCCESS
            )
        except Exception:
            pass
        return True

    def redeem(self, raw_token: str, password: str) -> None:
        token_hash = _token_hash(raw_token)
        # Every write path locks user before token; candidate lookup is
        # intentionally unlocked, then both decision-bearing rows are reread.
        candidate = self.db.scalar(
            select(MemberPasswordRecoveryToken).where(
                MemberPasswordRecoveryToken.token_hash == token_hash
            )
        )
        if candidate is None:
            raise MemberPasswordRecoveryTokenInvalidError(
                "Password reset link is invalid."
            )
        user = self._locked_user(candidate.user_id)
        token = self.db.scalar(
            select(MemberPasswordRecoveryToken)
            .where(MemberPasswordRecoveryToken.id == candidate.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if token is None:
            raise MemberPasswordRecoveryTokenInvalidError(
                "Password reset link is invalid."
            )
        if token.invalidated_at is not None or token.used_at is not None:
            self.db.rollback()
            raise MemberPasswordRecoveryTokenUsedError(
                "This password reset link has already been used or replaced."
            )
        now = datetime.now(timezone.utc)
        if token.expires_at <= now:
            self.db.rollback()
            raise MemberPasswordRecoveryTokenExpiredError(
                "This password reset link has expired."
            )
        if user is None or not self._is_eligible(user):
            self.db.rollback()
            raise MemberPasswordRecoveryTokenUsedError(
                "This password reset link is no longer available."
            )

        user.password_hash = hash_password(password)
        token.used_at = now
        self.db.execute(
            update(MemberPasswordRecoveryToken)
            .where(
                MemberPasswordRecoveryToken.user_id == user.id,
                MemberPasswordRecoveryToken.id != token.id,
                MemberPasswordRecoveryToken.used_at.is_(None),
                MemberPasswordRecoveryToken.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        self.audit.log(
            action="member.password_recovered",
            user_id=user.id,
            actor_type="member",
            resource_type="user",
            resource_id=str(user.id),
            summary="Reset a member password.",
        )
        self.db.commit()