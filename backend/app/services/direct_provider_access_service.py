"""Administrator-issued first-password links for directly added listings."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.enums import EmailDeliveryStatus, EmailPurpose, InvitationStatus
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.invitation import ProviderInvitation, ProviderPortalSetupToken
from app.models.provider import DirectProviderPortalAccess, Provider
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.user import User
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.email_delivery_repository import EmailDeliveryRepository, safe_failure_message
from app.repositories.user_repository import UserRepository
from app.schemas.provider import _valid_email
from app.services.email_service import EmailService


def invalidate_if_recipient_removed(
    db: Session, provider: Provider, *, excluded_email_id: UUID | None = None
) -> None:
    """Revoke pending links when a saved contact address is removed or changed."""
    access = db.get(DirectProviderPortalAccess, provider.id)
    if access is None:
        return
    contacts = {
        row.email.strip().lower()
        for row in provider.emails if row.id != excluded_email_id and _valid_email(row.email)
    }
    if _valid_email(provider.email):
        contacts.add(provider.email.strip().lower())
    if access.recipient_email in contacts:
        return
    user = db.get(User, access.user_id)
    if user is None or user.is_active or not user.provider_portal_setup_pending:
        return
    now = datetime.now(timezone.utc)
    db.execute(
        update(ProviderPortalSetupToken).where(
            ProviderPortalSetupToken.direct_provider_id == provider.id,
            ProviderPortalSetupToken.used_at.is_(None),
            ProviderPortalSetupToken.invalidated_at.is_(None),
        ).values(invalidated_at=now)
    )


class DirectAccessError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class DirectProviderAccessService:
    def __init__(self, db: Session, email: EmailService | None = None):
        self.db = db
        self.email = email or EmailService()
        self.audit = AuditRepository(db)
        self.logs = EmailDeliveryRepository(db)

    def _provider(self, provider_id: UUID, *, lock: bool = False) -> Provider:
        stmt = select(Provider).where(Provider.id == provider_id)
        if lock:
            stmt = stmt.with_for_update(of=Provider)
        provider = self.db.scalar(stmt)
        if provider is None:
            raise DirectAccessError("provider_not_found", "Provider not found.")
        return provider

    def status(self, provider_id: UUID) -> dict:
        provider = self._provider(provider_id)
        access = self.db.get(DirectProviderPortalAccess, provider_id)
        invitation = self.db.scalar(
            select(ProviderInvitation).where(ProviderInvitation.provider_id == provider_id)
            .order_by(ProviderInvitation.completed_at.desc().nullslast(), ProviderInvitation.created_at.desc())
            .limit(1)
        )
        registration = self.db.scalar(
            select(ProviderRegistrationApplication.id).where(ProviderRegistrationApplication.provider_id == provider_id)
        )
        contacts = [
            {"email_id": str(item.id), "email": item.email.strip().lower()}
            for item in provider.emails if _valid_email(item.email)
        ]
        if _valid_email(provider.email) and not any(item["email"] == provider.email.strip().lower() for item in contacts):
            contacts.append({"email_id": None, "email": provider.email.strip().lower()})
        if access:
            user = self.db.get(User, access.user_id)
            if user and user.provider_portal_setup_pending and not user.is_active:
                if any(c["email"] == access.recipient_email for c in contacts):
                    state, message = "pending", None
                    contacts = [c for c in contacts if c["email"] == access.recipient_email]
                    if access.sent_at:
                        latest = self.db.scalar(
                            select(EmailDeliveryLog).where(
                                EmailDeliveryLog.recipient_email == access.recipient_email,
                                EmailDeliveryLog.purpose == EmailPurpose.PROVIDER_PORTAL_ACCESS.value,
                                EmailDeliveryLog.created_at >= access.sent_at,
                            ).order_by(EmailDeliveryLog.created_at.desc(), EmailDeliveryLog.id.desc()).limit(1)
                        )
                        if latest and latest.status == EmailDeliveryStatus.FAILED.value:
                            message = "The latest portal access email failed to send. Retry sending it."
                else:
                    state, message = "unavailable", "The selected contact email was removed. Cancel pending access to choose a corrected contact."
            elif user and user.is_active and not user.provider_portal_setup_pending:
                state, message = "active", "Portal access is already set up."
            else:
                state, message = "unavailable", "This provider account is disabled or unavailable."
        elif invitation:
            state = "invitation" if invitation.status == InvitationStatus.COMPLETED else "unavailable"
            message = ("Use Send portal access in the completed invitation." if state == "invitation"
                       else "Finish or resolve the provider invitation before sending portal access.")
        elif registration:
            state, message = "registration", "This listing belongs to a provider registration."
        else:
            state, message = ("eligible", None) if contacts else ("unavailable", "Add a valid provider contact email first.")
        return {
            "status": state,
            "recipient_email": (
                access.recipient_email if access else
                invitation.recipient_email if state == "invitation" else
                contacts[0]["email"] if len(contacts) == 1 else None
            ),
            "email_id": next((c["email_id"] for c in contacts if access and c["email"] == access.recipient_email), None),
            "invitation_id": str(invitation.id) if state == "invitation" else None,
            "sent_at": access.sent_at if access else None,
            "message": message,
            "selectable_emails": contacts if state in ("eligible", "pending") else [],
            "can_revoke": bool(access and user and user.provider_portal_setup_pending and not user.is_active and user.email_verified_at is None),
        }

    def revoke(self, provider_id: UUID, *, context: AuditContext) -> dict:
        self._provider(provider_id, lock=True)
        access = self.db.get(DirectProviderPortalAccess, provider_id)
        user = self.db.get(User, access.user_id) if access else None
        if (not access or not user or not user.provider_portal_setup_pending
                or user.is_active or user.email_verified_at is not None):
            self.db.rollback()
            raise DirectAccessError("portal_access_unavailable", "Only unactivated direct portal access can be cancelled.")
        # The pending account exists solely for this listing. Removing its
        # explicit ownership and token rows frees the address, without
        # reassigning an active or disabled established account.
        self.audit.record(
            "provider.portal_access_cancelled", context=context, resource_type="provider",
            resource_id=str(provider_id), summary="Cancelled pending provider portal access.",
            metadata={"recipient_email": access.recipient_email},
        )
        self.db.delete(access)
        self.db.flush()
        self.db.delete(user)
        self.db.commit()
        return self.status(provider_id)

    def send(self, provider_id: UUID, email_id: UUID | None, *, context: AuditContext) -> dict:
        # Provider row serializes concurrent sends and redemption for one listing.
        provider = self._provider(provider_id, lock=True)
        state = self.status(provider_id)
        if state["status"] not in ("eligible", "pending"):
            self.db.rollback()
            raise DirectAccessError("portal_access_unavailable", state["message"] or "Portal access is unavailable.")
        contact = next((c for c in state["selectable_emails"] if c["email_id"] == (str(email_id) if email_id else None)), None)
        if contact is None:
            self.db.rollback()
            raise DirectAccessError("invalid_contact_email", "Select a valid email address saved on this provider.")
        recipient = contact["email"]
        access = self.db.get(DirectProviderPortalAccess, provider_id)
        users = UserRepository(self.db)
        if access:
            user = self.db.get(User, access.user_id)
            if (user is None or user.email != access.recipient_email or recipient != access.recipient_email
                    or not user.provider_portal_setup_pending or user.is_active):
                self.db.rollback()
                raise DirectAccessError("portal_access_unavailable", "This account is no longer eligible for setup.")
        else:
            if users.get_by_email(recipient):
                self.db.rollback()
                raise DirectAccessError("portal_access_account_conflict", "This email already belongs to an account. Choose another provider contact email.")
            role = users.get_role_by_name("provider")
            if role is None:
                self.db.rollback()
                raise DirectAccessError("portal_access_unavailable", "Provider portal role is unavailable.")
            try:
                user = users.create_user(
                    email=recipient, password_hash=hash_password(secrets.token_urlsafe(48)),
                    role=role, roles=[role], is_active=False, provider_portal_setup_pending=True,
                )
                access = DirectProviderPortalAccess(provider_id=provider.id, user_id=user.id, recipient_email=recipient)
                self.db.add(access)
                self.db.flush()
            except IntegrityError as exc:
                self.db.rollback()
                raise DirectAccessError("portal_access_account_conflict", "This email already belongs to an account.") from exc
        now = datetime.now(timezone.utc)
        raw = secrets.token_urlsafe(48)
        self.db.execute(
            update(ProviderPortalSetupToken).where(
                ProviderPortalSetupToken.direct_provider_id == provider_id,
                ProviderPortalSetupToken.used_at.is_(None),
                ProviderPortalSetupToken.invalidated_at.is_(None),
            ).values(invalidated_at=now)
        )
        expiry = now + timedelta(hours=get_settings().PROVIDER_PORTAL_SETUP_EXPIRE_HOURS)
        self.db.add(ProviderPortalSetupToken(
            direct_provider_id=provider_id, user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=expiry,
        ))
        access.sent_at = now
        self.audit.record(
            "provider.portal_access_sent", context=context, resource_type="provider",
            resource_id=str(provider_id), summary="Issued provider portal setup link.",
            metadata={"recipient_email": recipient, "portal_user_id": str(user.id)},
        )
        self.db.commit()
        try:
            attempt_id = self.logs.record_durable_attempt(
                recipient_email=recipient, purpose=EmailPurpose.PROVIDER_PORTAL_ACCESS
            )
        except Exception as exc:
            self.db.rollback()
            raise DirectAccessError("portal_access_delivery_failed", "Email delivery could not be recorded. Retry sending portal access.") from exc
        try:
            self.email.send_provider_portal_access_email(
                recipient, get_settings().public_link(f"/provider/setup-password?token={raw}"), expiry
            )
        except Exception as exc:
            self.logs.complete_durable_attempt(
                attempt_id, status=EmailDeliveryStatus.FAILED, failure_message=safe_failure_message(exc)
            )
            self.audit.record(
                "provider.portal_access_delivery_failed", context=context, resource_type="provider",
                resource_id=str(provider_id), summary="Provider portal access email delivery failed.",
                metadata={"recipient_email": recipient},
            )
            self.db.commit()
            raise DirectAccessError("portal_access_delivery_failed", "Email delivery failed. The provider was saved; retry sending portal access.") from exc
        self.logs.complete_durable_attempt(attempt_id, status=EmailDeliveryStatus.SUCCESS)
        self.db.commit()
        return self.status(provider_id)