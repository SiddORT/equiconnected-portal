"""Administrator workflow for deciding public account registrations."""
import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.models.enums import PublicAccountApprovalStatus
from app.models.user import User
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailDeliveryError, EmailService

logger = get_logger(__name__)


class PublicRegistrantNotFoundError(Exception):
    """Raised when an ID is not a public registration."""


class PublicAccountAlreadyDecidedError(Exception):
    """Raised when an approval decision has already been recorded."""


class PublicAccountService:
    """Keeps account decisions atomic, immutable, and independently auditable."""

    def __init__(self, db) -> None:
        self._db = db
        self._users = UserRepository(db)
        self._tokens = TokenRepository(db)
        self._audit = AuditRepository(db)
        self._email = EmailService()

    def decide(
        self,
        *,
        user_id: uuid.UUID,
        administrator_id: uuid.UUID,
        decision: PublicAccountApprovalStatus,
        audit_context: AuditContext,
    ) -> User:
        if decision not in (
            PublicAccountApprovalStatus.APPROVED,
            PublicAccountApprovalStatus.REJECTED,
        ):
            raise ValueError("A public account can only be approved or rejected.")

        user = self._users.get_public_registrant_for_update(user_id)
        if user is None:
            raise PublicRegistrantNotFoundError(str(user_id))
        if user.approval_status != PublicAccountApprovalStatus.PENDING:
            raise PublicAccountAlreadyDecidedError(
                "This account already has an approval decision."
            )

        now = datetime.now(timezone.utc)
        user.approval_status = decision
        user.approval_decided_at = now
        user.approval_decided_by = administrator_id
        revoked_sessions = 0
        if decision == PublicAccountApprovalStatus.REJECTED:
            revoked_sessions = self._tokens.revoke_all_for_user(user.id)

        self._audit.record(
            action=f"public_account.{decision.value.lower()}",
            context=audit_context,
            resource_type="public_account",
            resource_id=str(user.id),
            metadata={"approval_status": decision.value},
            summary=f"Public account {decision.value.lower()}",
            changes=[
                {
                    "field": "approval_status",
                    "before": PublicAccountApprovalStatus.PENDING.value,
                    "after": decision.value,
                }
            ],
        )
        self._db.commit()

        try:
            self._email.send_account_decision_email(
                user.email, approved=decision == PublicAccountApprovalStatus.APPROVED
            )
        except EmailDeliveryError:
            # The decision must never be rolled back because optional SMTP is absent.
            logger.warning(
                "public_account.decision_email_failed",
                user_id=str(user.id),
                decision=decision.value,
            )
            self._audit.record(
                action="public_account.decision_email_failed",
                context=audit_context,
                resource_type="public_account",
                resource_id=str(user.id),
                metadata={"approval_status": decision.value},
                summary="Public account decision email could not be delivered",
            )
            self._db.commit()

        logger.info(
            "public_account.decided",
            user_id=str(user.id),
            administrator_id=str(administrator_id),
            decision=decision.value,
            revoked_sessions=revoked_sessions,
        )
        return user