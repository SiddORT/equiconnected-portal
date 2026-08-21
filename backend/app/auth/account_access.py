"""Public-account access policy shared by login, refresh, and dependencies."""
from dataclasses import dataclass

from app.models.enums import PublicAccountApprovalStatus
from app.models.user import User


@dataclass(frozen=True)
class PublicAccountAccessIssue:
    code: str
    message: str


def public_account_access_issue(user: User) -> PublicAccountAccessIssue | None:
    """Return a stable denial reason only for public registration accounts."""
    if not user.is_public_registrant:
        return None
    if user.approval_status == PublicAccountApprovalStatus.REJECTED:
        return PublicAccountAccessIssue(
            code="account_rejected",
            message="This account registration was not approved.",
        )
    if user.email_verified_at is None:
        return PublicAccountAccessIssue(
            code="email_not_verified",
            message="Please verify your email address before signing in.",
        )
    if user.approval_status != PublicAccountApprovalStatus.APPROVED:
        return PublicAccountAccessIssue(
            code="account_pending",
            message="Your account is awaiting administrator approval.",
        )
    return None