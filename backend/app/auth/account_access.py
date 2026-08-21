"""Public-account access policy shared by login, refresh, and dependencies."""
from dataclasses import dataclass

from app.models.enums import ProviderApplicationStatus
from app.models.user import User


@dataclass(frozen=True)
class PublicAccountAccessIssue:
    code: str
    message: str


def public_account_access_issue(user: User) -> PublicAccountAccessIssue | None:
    """Return a stable denial reason for self-registered member or provider accounts."""
    if user.is_public_registrant and user.email_verified_at is None:
        return PublicAccountAccessIssue(
            code="email_not_verified",
            message="Please verify your email address before signing in.",
        )
    if not user.is_provider_registrant:
        return None
    if user.email_verified_at is None:
        return PublicAccountAccessIssue(
            code="email_not_verified",
            message="Please verify your email address before signing in.",
        )
    # Administrator-invited providers are linked directly to a completed
    # invitation rather than to the self-service application workflow.
    if user.provider_portal_invitation is not None:
        return None
    application = user.provider_registration_application
    if application is None:
        return PublicAccountAccessIssue(
            code="provider_application_unavailable",
            message="Your provider application is unavailable. Please contact support.",
        )
    if application.review_status == ProviderApplicationStatus.PENDING_REVIEW:
        return PublicAccountAccessIssue(
            code="provider_application_pending_review",
            message="Your provider application is awaiting administrator review.",
        )
    if application.review_status == ProviderApplicationStatus.REJECTED:
        return PublicAccountAccessIssue(
            code="provider_application_rejected",
            message="Your provider application was not approved. Please contact support.",
        )
    if application.review_status != ProviderApplicationStatus.APPROVED:
        return PublicAccountAccessIssue(
            code="provider_application_pending_review",
            message="Your provider application is awaiting email verification.",
        )
    return None