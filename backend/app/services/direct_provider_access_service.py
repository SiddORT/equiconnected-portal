"""Administrator-issued first-password links for directly added listings."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.enums import (
    EmailDeliveryStatus,
    EmailPurpose,
    InvitationStatus,
    ProviderApplicationStatus,
)
from app.models.invitation import ProviderInvitation, ProviderPortalSetupToken
from app.models.provider import DirectProviderPortalAccess, Provider
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.user import User
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.email_delivery_repository import EmailDeliveryRepository, safe_failure_message
from app.repositories.user_repository import UserRepository
from app.schemas.provider import _valid_email
from app.services.email_service import EmailDeliveryError, EmailService
from app.services.provider_portal_recovery_service import ProviderPortalRecoveryService
from app.services.contact_encryption import normalize_contact


def invalidate_if_recipient_removed(
    db: Session, provider: Provider, *, excluded_email_id: UUID | None = None
) -> None:
    """Revoke pending links when a saved contact address is removed or changed."""
    access = db.get(DirectProviderPortalAccess, provider.id)
    if access is None:
        return
    contacts = {
        normalize_contact(row.email, field="email")
        for row in provider.emails
        if row.id != excluded_email_id and _valid_email(row.email)
    }
    if _valid_email(provider.email):
        contacts.add(normalize_contact(provider.email, field="email"))
    if normalize_contact(access.recipient_email, field="email") in contacts:
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
        return self._metadata_for_providers([provider])[provider_id]

    def list_metadata(self, providers: list[Provider]) -> dict[UUID, dict]:
        """Resolve ownership and available portal actions in bounded batch queries."""
        return self._metadata_for_providers(providers)

    def _metadata_for_providers(self, providers: list[Provider]) -> dict[UUID, dict]:
        if not providers:
            return {}
        provider_ids = [provider.id for provider in providers]
        access_rows = self.db.scalars(
            select(DirectProviderPortalAccess).where(
                DirectProviderPortalAccess.provider_id.in_(provider_ids)
            )
        ).all()
        invitation_rows = self.db.scalars(
            select(ProviderInvitation)
            .where(ProviderInvitation.provider_id.in_(provider_ids))
            .order_by(
                ProviderInvitation.provider_id,
                ProviderInvitation.completed_at.desc().nullslast(),
                ProviderInvitation.created_at.desc(),
            )
        ).all()
        registration_rows = self.db.scalars(
            select(ProviderRegistrationApplication).where(
                ProviderRegistrationApplication.provider_id.in_(provider_ids)
            )
        ).all()
        access_by_provider = {row.provider_id: row for row in access_rows}
        invitation_by_provider: dict[UUID, ProviderInvitation] = {}
        for row in invitation_rows:
            invitation_by_provider.setdefault(row.provider_id, row)
        registration_by_provider = {row.provider_id: row for row in registration_rows}

        account_ids = {row.user_id for row in access_rows}
        account_ids.update(
            row.portal_user_id for row in invitation_rows
            if row.portal_user_id is not None
        )
        account_ids.update(row.user_id for row in registration_rows)
        accounts = self.db.scalars(
            select(User).where(User.id.in_(account_ids)).options(joinedload(User.role))
        ).all() if account_ids else []
        users_by_id = {row.id: row for row in accounts}

        emails_to_check = {
            normalize_contact(email, field="email")
            for provider in providers
            for email in [*(item.email for item in provider.emails), provider.email]
            if _valid_email(email)
        }
        matching_accounts = self.db.scalars(
            select(User).where(User.email.in_(emails_to_check))
        ).all() if emails_to_check else []
        users_by_email = {
            normalize_contact(row.email, field="email"): row
            for row in matching_accounts
        }

        result: dict[UUID, dict] = {}
        for provider in providers:
            access = access_by_provider.get(provider.id)
            invitation = invitation_by_provider.get(provider.id)
            registration = registration_by_provider.get(provider.id)
            owner_ids = set()
            if access:
                owner_ids.add(access.user_id)
            if invitation and invitation.portal_user_id:
                owner_ids.add(invitation.portal_user_id)
            if registration:
                owner_ids.add(registration.user_id)
            owner = users_by_id.get(next(iter(owner_ids))) if len(owner_ids) == 1 else None

            contacts = [
                {
                    "email_id": str(item.id),
                    "email": normalize_contact(item.email, field="email"),
                }
                for item in provider.emails if _valid_email(item.email)
            ]
            if _valid_email(provider.email) and not any(
                item["email"] == normalize_contact(provider.email, field="email")
                for item in contacts
            ):
                contacts.append(
                    {
                        "email_id": None,
                        "email": normalize_contact(provider.email, field="email"),
                    }
                )

            action = None
            state = "unavailable"
            reason = None
            recipient = None
            sent_at = access.sent_at if access else None
            if len(owner_ids) > 1:
                reason = "Portal access is unavailable because this listing has conflicting account ownership."
            elif owner:
                recipient = owner.email
                if owner.role.name != "provider":
                    reason = "The linked account does not have provider portal access."
                elif getattr(owner, "provider_portal_approval_pending", False):
                    reason = "Portal access is waiting for provider approval."
                elif not owner.is_active:
                    if owner.provider_portal_setup_pending and not registration:
                        action, state = "setup", "pending"
                        reason = "A password setup link can be sent to the linked provider login email."
                    else:
                        reason = "The linked provider account is disabled."
                elif owner.provider_portal_setup_pending:
                    reason = "The linked provider account is not ready for portal access."
                elif registration and registration.review_status != ProviderApplicationStatus.APPROVED:
                    reason = "Portal access is waiting for provider application approval."
                elif invitation and invitation.status != InvitationStatus.COMPLETED:
                    reason = "The provider invitation must be completed before portal access can be used."
                else:
                    action, state = "reset", "active"
                    reason = "A password reset link can be sent to the linked provider login email."
                if access and owner.provider_portal_setup_pending:
                    selected = [
                        item for item in contacts
                        if normalize_contact(item["email"], field="email")
                        == normalize_contact(access.recipient_email, field="email")
                    ]
                    if not selected:
                        action, state = None, "unavailable"
                        reason = "The selected setup email was removed. Cancel pending access to choose a corrected contact."
                    else:
                        contacts = selected
                if invitation and not access:
                    sent_at = invitation.portal_access_sent_at
                    recipient = owner.email
                    if action == "setup":
                        state = "invitation"
            elif owner_ids:
                reason = "The explicitly linked provider account is unavailable."
            elif invitation:
                sent_at = invitation.portal_access_sent_at
                recipient = invitation.recipient_email
                if invitation.status == InvitationStatus.COMPLETED:
                    if users_by_email.get(normalize_contact(recipient, field="email")):
                        reason = "This email already belongs to an EquiConnected account and cannot be linked automatically."
                    else:
                        action, state = "setup", "invitation"
                        reason = "Send a first-password setup link to the invitation login email."
                else:
                    reason = "Complete or resolve the provider invitation before sending portal access."
            elif registration:
                state = "registration"
                reason = "This listing belongs to a provider registration and requires an explicitly linked account."
            else:
                available = [
                    item for item in contacts if not users_by_email.get(item["email"])
                ]
                if available:
                    action, state = "setup", "eligible"
                    if len(available) == 1:
                        recipient = available[0]["email"]
                    reason = "Select a saved provider contact email for first-password setup."
                else:
                    reason = (
                        "Add a valid provider contact email first."
                        if not contacts else
                        "Every provider contact email already belongs to an EquiConnected account."
                    )

            if action == "reset" and invitation:
                state = "invitation"
            if action == "reset" and registration:
                state = "registration"
            result[provider.id] = {
                "status": state,
                "available": action is not None,
                "reason": reason,
                "action": action,
                "recipient_email": access.recipient_email if access else recipient,
                "portal_login_email": owner.email if owner and action == "reset" else recipient,
                "email_id": next(
                    (item["email_id"] for item in contacts
                     if access and normalize_contact(item["email"], field="email")
                     == normalize_contact(access.recipient_email, field="email")),
                    None,
                ),
                "invitation_id": (
                    str(invitation.id)
                    if invitation and invitation.status == InvitationStatus.COMPLETED
                    else None
                ),
                "sent_at": sent_at,
                "message": reason,
                "selectable_emails": contacts if state in ("eligible", "pending") else [],
                "can_revoke": bool(
                    access and owner and owner.provider_portal_setup_pending
                    and not owner.is_active and owner.email_verified_at is None
                ),
            }
        return result

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
        if state["action"] == "reset":
            access = self.db.get(DirectProviderPortalAccess, provider_id)
            invitation = self.db.scalar(
                select(ProviderInvitation).where(
                    ProviderInvitation.provider_id == provider_id,
                    ProviderInvitation.portal_user_id.is_not(None),
                ).order_by(ProviderInvitation.completed_at.desc().nullslast())
            )
            registration = self.db.scalar(
                select(ProviderRegistrationApplication).where(
                    ProviderRegistrationApplication.provider_id == provider_id
                )
            )
            user_id = (
                access.user_id if access else
                invitation.portal_user_id if invitation else
                registration.user_id if registration else None
            )
            if user_id is None:
                self.db.rollback()
                raise DirectAccessError(
                    "portal_access_unavailable",
                    "The explicitly linked provider account is unavailable.",
                )
            from app.services.provider_portal_recovery_service import (
                ProviderPortalRecoveryCooldownError,
                ProviderPortalRecoveryDeliveryError,
                ProviderPortalRecoveryUnavailableError,
            )
            try:
                ProviderPortalRecoveryService(self.db, self.email).send(
                    provider_id, user_id, context=context
                )
            except ProviderPortalRecoveryCooldownError as exc:
                raise DirectAccessError("portal_access_cooldown", str(exc)) from exc
            except ProviderPortalRecoveryDeliveryError as exc:
                raise DirectAccessError("portal_access_delivery_failed", str(exc)) from exc
            except ProviderPortalRecoveryUnavailableError as exc:
                raise DirectAccessError("portal_access_unavailable", str(exc)) from exc
            return self.status(provider_id)
        if state["action"] == "setup" and state.get("invitation_id"):
            invitation_id = UUID(state["invitation_id"])
            from app.repositories.invitation_repository import InvitationRepository
            from app.repositories.provider_repository import ProviderRepository
            from app.services.invitation_service import (
                InvitationService,
                PortalAccessAccountConflictError,
                PortalAccessUnavailableError,
            )
            try:
                InvitationService(
                    InvitationRepository(self.db), ProviderRepository(self.db), self.email
                ).send_portal_access(invitation_id, audit_context=context)
            except PortalAccessAccountConflictError as exc:
                self.db.rollback()
                raise DirectAccessError(
                    "portal_access_account_conflict", str(exc)
                ) from exc
            except PortalAccessUnavailableError as exc:
                self.db.rollback()
                raise DirectAccessError(
                    "portal_access_unavailable", str(exc)
                ) from exc
            except EmailDeliveryError as exc:
                self.db.rollback()
                raise DirectAccessError(
                    "portal_access_delivery_failed",
                    "Provider portal setup email could not be sent. The account state is unchanged; retry sending it.",
                ) from exc
            return self.status(provider_id)
        if state["status"] not in ("eligible", "pending", "invitation"):
            self.db.rollback()
            raise DirectAccessError("portal_access_unavailable", state["message"] or "Portal access is unavailable.")
        if state["action"] != "setup":
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
            if (
                user is None
                or normalize_contact(user.email, field="email")
                != normalize_contact(access.recipient_email, field="email")
                or normalize_contact(recipient, field="email")
                != normalize_contact(access.recipient_email, field="email")
                or not user.provider_portal_setup_pending
                or user.is_active
                or getattr(user, "provider_portal_approval_pending", False)
            ):
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