"""Secure password recovery for explicitly owned provider portal accounts."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.enums import (
    EmailDeliveryStatus,
    EmailPurpose,
    InvitationStatus,
    ProviderApplicationStatus,
)
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.invitation import ProviderInvitation, ProviderPortalRecoveryToken
from app.models.provider import DirectProviderPortalAccess, Provider
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.email_delivery_repository import (
    EmailDeliveryRepository,
    safe_failure_message,
)
from app.services.contact_encryption import normalize_contact
from app.services.email_service import EmailDeliveryError, EmailService


RECOVERY_COOLDOWN = timedelta(minutes=5)


class ProviderPortalRecoveryError(Exception):
    """Base recovery exception."""


class ProviderPortalRecoveryUnavailableError(ProviderPortalRecoveryError):
    pass


class ProviderPortalRecoveryCooldownError(ProviderPortalRecoveryError):
    pass


class ProviderPortalRecoveryDeliveryError(ProviderPortalRecoveryError):
    pass


class ProviderPortalRecoveryTokenNotFoundError(ProviderPortalRecoveryError):
    pass


class ProviderPortalRecoveryTokenExpiredError(ProviderPortalRecoveryError):
    pass


class ProviderPortalRecoveryTokenUsedError(ProviderPortalRecoveryError):
    pass


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _provider_owner_is_eligible(db: Session, provider_id: UUID, user: User) -> bool:
    """Require a unique, explicit provider ownership route and approved state."""
    direct = db.get(DirectProviderPortalAccess, provider_id)
    invitations = db.scalars(
        select(ProviderInvitation).where(
            ProviderInvitation.provider_id == provider_id,
            ProviderInvitation.portal_user_id.is_not(None),
        )
    ).all()
    application = db.scalar(
        select(ProviderRegistrationApplication).where(
            ProviderRegistrationApplication.provider_id == provider_id
        )
    )
    owner_ids = set()
    if direct:
        owner_ids.add(direct.user_id)
    owner_ids.update(inv.portal_user_id for inv in invitations if inv.portal_user_id)
    if application:
        owner_ids.add(application.user_id)
    if owner_ids != {user.id}:
        return False
    if user.role.name != "provider" or not user.is_active:
        return False
    if user.provider_portal_setup_pending or getattr(user, "provider_portal_approval_pending", False):
        return False
    if direct and (
        direct.user_id != user.id
        or normalize_contact(direct.recipient_email, field="email")
        != normalize_contact(user.email, field="email")
    ):
        return False
    if any(
        inv.portal_user_id == user.id
        and (
            inv.status != InvitationStatus.COMPLETED
            or normalize_contact(inv.recipient_email, field="email")
            != normalize_contact(user.email, field="email")
        )
        for inv in invitations
    ):
        return False
    if application and (
        application.user_id != user.id
        or application.review_status != ProviderApplicationStatus.APPROVED
    ):
        return False
    return bool(direct or invitations or application)


class ProviderPortalRecoveryService:
    def __init__(self, db: Session, email: EmailService | None = None) -> None:
        self.db = db
        self.email = email or EmailService()
        self.logs = EmailDeliveryRepository(db)
        self.audit = AuditRepository(db)

    def send(
        self,
        provider_id: UUID,
        user_id: UUID,
        *,
        context: AuditContext,
    ) -> dict:
        # The provider row is the common serialization point for recovery sends
        # and redemptions; user locking then makes the per-account cooldown
        # atomic for providers that share no ownership route.
        provider = self.db.scalar(
            select(Provider).where(Provider.id == provider_id).with_for_update(of=Provider)
        )
        if provider is None:
            raise ProviderPortalRecoveryUnavailableError("Provider not found.")
        user = self.db.scalar(
            select(User).where(User.id == user_id).with_for_update(of=User)
        )
        if user is None or not _provider_owner_is_eligible(self.db, provider_id, user):
            self.db.rollback()
            raise ProviderPortalRecoveryUnavailableError(
                "Password reset is available only for an explicitly linked, active, approved provider account."
            )

        now = datetime.now(timezone.utc)
        latest = self.db.scalar(
            select(EmailDeliveryLog)
            .where(
                EmailDeliveryLog.recipient_email == user.email,
                EmailDeliveryLog.purpose == EmailPurpose.PROVIDER_PORTAL_RECOVERY.value,
            )
            .order_by(EmailDeliveryLog.created_at.desc(), EmailDeliveryLog.id.desc())
            .limit(1)
        )
        if latest and latest.status in (
            EmailDeliveryStatus.PENDING.value,
            EmailDeliveryStatus.SUCCESS.value,
        ) and now - latest.created_at < RECOVERY_COOLDOWN:
            self.db.rollback()
            raise ProviderPortalRecoveryCooldownError(
                "A password reset email was sent recently. Please wait a few minutes before retrying."
            )

        raw_token = secrets.token_urlsafe(48)
        expires_at = now + timedelta(
            hours=get_settings().PROVIDER_PORTAL_RECOVERY_EXPIRE_HOURS
        )
        token = ProviderPortalRecoveryToken(
            provider_id=provider_id,
            user_id=user.id,
            token_hash=_token_hash(raw_token),
            expires_at=expires_at,
        )
        self.db.add(token)
        self.db.flush()
        self.audit.record(
            "provider_portal.password_recovery_sent",
            context=context,
            resource_type="provider",
            resource_id=str(provider_id),
            summary="Issued a provider portal password reset link.",
            metadata={"portal_user_id": str(user.id), "recipient_email": user.email},
        )
        self.db.commit()

        try:
            attempt_id = self.logs.record_durable_attempt(
                recipient_email=user.email,
                purpose=EmailPurpose.PROVIDER_PORTAL_RECOVERY,
            )
        except Exception as exc:
            self.db.rollback()
            raise ProviderPortalRecoveryDeliveryError(
                "Email delivery could not be recorded. Retry sending the password reset email."
            ) from exc
        recovery_url = get_settings().public_link(
            f"/provider/reset-password?token={raw_token}"
        )
        try:
            self.email.send_provider_portal_recovery_email(
                user.email, recovery_url, expires_at
            )
        except Exception as exc:
            self.logs.complete_durable_attempt(
                attempt_id,
                status=EmailDeliveryStatus.FAILED,
                failure_message=safe_failure_message(exc),
            )
            self.audit.record(
                "provider_portal.password_recovery_delivery_failed",
                context=context,
                resource_type="provider",
                resource_id=str(provider_id),
                summary="Provider portal password reset email delivery failed.",
                metadata={"portal_user_id": str(user.id), "recipient_email": user.email},
            )
            self.db.commit()
            raise ProviderPortalRecoveryDeliveryError(
                "Email delivery failed. The provider account and current password are unchanged; retry sending the reset email."
            ) from exc

        # Revoke older links only after delivery succeeds. A failed SMTP attempt
        # can therefore never strand a recipient who still has an older link.
        self.db.execute(
            update(ProviderPortalRecoveryToken)
            .where(
                ProviderPortalRecoveryToken.user_id == user.id,
                ProviderPortalRecoveryToken.id != token.id,
                ProviderPortalRecoveryToken.used_at.is_(None),
                ProviderPortalRecoveryToken.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        self.logs.complete_durable_attempt(
            attempt_id, status=EmailDeliveryStatus.SUCCESS
        )
        self.db.commit()
        return {
            "available": True,
            "action": "reset",
            "recipient_email": user.email,
            "sent_at": now,
        }

    def redeem(self, raw_token: str, password: str) -> None:
        token_hash = _token_hash(raw_token)
        # The initial lookup is intentionally unlocked. Both issue and redeem
        # then use provider -> user -> token as the single lock order.
        candidate = self.db.scalar(
            select(ProviderPortalRecoveryToken).where(
                ProviderPortalRecoveryToken.token_hash == token_hash
            )
        )
        if candidate is None:
            raise ProviderPortalRecoveryTokenNotFoundError("Password reset link is invalid.")
        self.db.scalar(
            select(Provider)
            .where(Provider.id == candidate.provider_id)
            .with_for_update(of=Provider)
            .execution_options(populate_existing=True)
        )
        user = self.db.scalar(
            select(User)
            .where(User.id == candidate.user_id)
            .with_for_update(of=User)
            .execution_options(populate_existing=True)
        )
        token = self.db.scalar(
            select(ProviderPortalRecoveryToken)
            .where(ProviderPortalRecoveryToken.id == candidate.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if token is None:
            raise ProviderPortalRecoveryTokenNotFoundError("Password reset link is invalid.")
        if token.invalidated_at is not None or token.used_at is not None:
            raise ProviderPortalRecoveryTokenUsedError(
                "This password reset link has already been used or replaced."
            )
        now = datetime.now(timezone.utc)
        if token.expires_at <= now:
            raise ProviderPortalRecoveryTokenExpiredError("Password reset link has expired.")
        if (
            user is None
            or not _provider_owner_is_eligible(self.db, token.provider_id, user)
        ):
            raise ProviderPortalRecoveryTokenUsedError(
                "This password reset link is no longer available."
            )

        user.password_hash = hash_password(password)
        token.used_at = now
        self.db.execute(
            update(ProviderPortalRecoveryToken)
            .where(
                ProviderPortalRecoveryToken.user_id == user.id,
                ProviderPortalRecoveryToken.id != token.id,
                ProviderPortalRecoveryToken.used_at.is_(None),
                ProviderPortalRecoveryToken.invalidated_at.is_(None),
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
            action="provider_portal.password_recovered",
            user_id=user.id,
            actor_type="provider_portal",
            resource_type="provider",
            resource_id=str(token.provider_id),
            summary="Reset a provider portal password.",
        )
        self.db.commit()
