"""Safely remove non-administrator accounts from the configured database.

The command is deliberately preview-first. It never changes data unless the
operator supplies the exact confirmation phrase with ``--confirm``. It is not
an application endpoint and must not be run automatically during deployment,
startup, or demo-data seeding.
"""
import argparse
import os
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

# Allow running from the backend/ directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

import app.db.base  # noqa: F401, E402 — register all mapped models before querying
from app.db.session import SessionLocal  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.models.invitation import ProviderInvitation  # noqa: E402
from app.models.profile import Horse, StableProfile  # noqa: E402
from app.models.provider import ProviderReview  # noqa: E402
from app.models.refresh_token import RefreshToken  # noqa: E402
from app.models.user import EmailVerificationToken, User, UserRole  # noqa: E402


ADMIN_ROLE_NAME = "admin"
RESET_CONFIRMATION = "DELETE_NON_ADMIN_USERS"


class ResetError(Exception):
    """Base class for reset command errors that leave the database unchanged."""


class ConfirmationRequiredError(ResetError):
    """Raised when an operator did not provide the exact destructive confirmation."""


class NoActiveAdministratorError(ResetError):
    """Raised when executing would leave no active administrator account."""


class RestrictiveReferenceError(ResetError):
    """Raised when a non-cascading foreign key makes the reset unsafe."""


@dataclass(frozen=True)
class AccountSummary:
    """Display-safe identity and authorization state for a user account."""

    user_id: uuid.UUID
    email: str
    is_active: bool
    role_names: tuple[str, ...]


@dataclass(frozen=True)
class InvitationBlocker:
    """A safe summary of invitations that prevent deleting their creator."""

    creator_email: str
    invitation_count: int


@dataclass(frozen=True)
class ResetPlan:
    """The complete, non-mutating preview of a reset operation."""

    retained_administrators: tuple[AccountSummary, ...]
    targeted_users: tuple[AccountSummary, ...]
    active_administrator_count: int
    dependent_record_counts: dict[str, int]
    audit_logs_to_unlink: int
    invitation_blockers: tuple[InvitationBlocker, ...]

    @property
    def can_execute(self) -> bool:
        return (
            self.active_administrator_count > 0
            and not self.invitation_blockers
        )


@dataclass(frozen=True)
class ResetResult:
    """The committed outcome of a confirmed reset."""

    plan: ResetPlan
    deleted_user_count: int


def _account_summary(user: User) -> AccountSummary:
    role_names = {user.role.name}
    role_names.update(assignment.role.name for assignment in user.role_assignments)
    return AccountSummary(
        user_id=user.id,
        email=user.email,
        is_active=user.is_active,
        role_names=tuple(sorted(role_names)),
    )


def _load_users(db: Session, *, lock: bool) -> list[User]:
    statement = (
        select(User)
        .options(
            # Keep role data in separate queries. A joined eager load would add
            # an outer join, and PostgreSQL cannot apply FOR UPDATE to that
            # nullable join side.
            selectinload(User.role),
            selectinload(User.role_assignments).joinedload(UserRole.role),
        )
        .order_by(User.email)
    )
    if lock:
        # Lock the accounts that establish the safety boundary. PostgreSQL's FK
        # checks also prevent a concurrently-created reference from slipping
        # past the following delete.
        statement = statement.with_for_update()
    return list(db.scalars(statement).all())


def _acquire_reset_locks(db: Session) -> None:
    """Serialize writes that could change the reset's authorization boundary.

    This command targets PostgreSQL only. SHARE ROW EXCLUSIVE blocks concurrent
    INSERT, UPDATE, and DELETE statements against these tables while allowing
    ordinary reads. That keeps user creation, primary-role changes, relational
    role changes, and provider-invitation creation out of the preflight/delete
    window without leaving a long-lived application lock behind.
    """
    db.execute(
        text(
            "LOCK TABLE users, user_roles, roles, provider_invitations "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
    )


def _count_for_users(db: Session, model, column, user_ids: Sequence[uuid.UUID]) -> int:
    if not user_ids:
        return 0
    return int(
        db.scalar(
            select(func.count()).select_from(model).where(column.in_(user_ids))
        )
        or 0
    )


def _invitation_blockers(
    db: Session, user_ids: Sequence[uuid.UUID]
) -> tuple[InvitationBlocker, ...]:
    if not user_ids:
        return ()
    rows = db.execute(
        select(User.email, func.count(ProviderInvitation.id))
        .join(User, ProviderInvitation.created_by == User.id)
        .where(ProviderInvitation.created_by.in_(user_ids))
        .group_by(User.email)
        .order_by(User.email)
    ).all()
    return tuple(
        InvitationBlocker(creator_email=email, invitation_count=count)
        for email, count in rows
    )


def build_reset_plan(db: Session, *, lock_users: bool = False) -> ResetPlan:
    """Inspect the reset scope without changing any rows.

    An account is retained if its primary role or any relational role assignment
    is ``admin``. This intentionally supports users created before or after the
    multi-role assignment table existed.
    """
    retained: list[AccountSummary] = []
    targeted: list[AccountSummary] = []
    for user in _load_users(db, lock=lock_users):
        summary = _account_summary(user)
        if ADMIN_ROLE_NAME in summary.role_names:
            retained.append(summary)
        else:
            targeted.append(summary)

    target_ids = [summary.user_id for summary in targeted]
    dependent_record_counts = {
        "role_assignments": _count_for_users(db, UserRole, UserRole.user_id, target_ids),
        "refresh_sessions": _count_for_users(
            db, RefreshToken, RefreshToken.user_id, target_ids
        ),
        "email_verification_tokens": _count_for_users(
            db, EmailVerificationToken, EmailVerificationToken.user_id, target_ids
        ),
        "stable_profiles": _count_for_users(
            db, StableProfile, StableProfile.user_id, target_ids
        ),
        "horses": _count_for_users(db, Horse, Horse.user_id, target_ids),
        "provider_reviews": _count_for_users(
            db, ProviderReview, ProviderReview.member_id, target_ids
        ),
    }

    return ResetPlan(
        retained_administrators=tuple(retained),
        targeted_users=tuple(targeted),
        active_administrator_count=sum(
            account.is_active for account in retained
        ),
        dependent_record_counts=dependent_record_counts,
        audit_logs_to_unlink=_count_for_users(
            db, AuditLog, AuditLog.user_id, target_ids
        ),
        invitation_blockers=_invitation_blockers(db, target_ids),
    )


def execute_reset(db: Session, *, confirmation: str | None) -> ResetResult:
    """Commit an all-or-nothing non-admin account reset.

    The plan is built while user rows are locked, validated, and then deleted in
    the same transaction. Database cascades handle member-owned records; audit
    history is retained and its actor reference is set to NULL by its FK.
    """
    if confirmation != RESET_CONFIRMATION:
        raise ConfirmationRequiredError(
            "Refusing destructive reset. Supply "
            f"--confirm {RESET_CONFIRMATION} exactly."
        )

    # Lock tables before reading the account/role boundary. The plan is then
    # derived and deleted in one transaction, rather than trusting a separate
    # preview snapshot that may have gone stale.
    _acquire_reset_locks(db)
    plan = build_reset_plan(db, lock_users=True)
    if plan.active_administrator_count == 0:
        db.rollback()
        raise NoActiveAdministratorError(
            "Refusing reset because no active administrator account would remain. "
            "Restore or activate an administrator, then run the preview again."
        )
    if plan.invitation_blockers:
        details = ", ".join(
            f"{blocker.creator_email} ({blocker.invitation_count})"
            for blocker in plan.invitation_blockers
        )
        db.rollback()
        raise RestrictiveReferenceError(
            "Refusing reset because provider invitations created by targeted "
            f"accounts still exist: {details}. Their created_by reference is "
            "restrictive; resolve those invitation records first. No changes "
            "were committed."
        )

    target_ids = [account.user_id for account in plan.targeted_users]
    try:
        if target_ids:
            result = db.execute(delete(User).where(User.id.in_(target_ids)))
            deleted_user_count = int(result.rowcount or 0)
        else:
            deleted_user_count = 0
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RestrictiveReferenceError(
            "Refusing reset because the database rejected deleting a targeted "
            "account due to a restrictive reference. No changes were committed. "
            "Inspect user-linked references, resolve them, and rerun the preview."
        ) from exc

    return ResetResult(plan=plan, deleted_user_count=deleted_user_count)


def _format_accounts(title: str, accounts: Sequence[AccountSummary]) -> list[str]:
    lines = [f"{title} ({len(accounts)}):"]
    if not accounts:
        return lines + ["  (none)"]
    return lines + [
        "  - "
        f"{account.email} | active={'yes' if account.is_active else 'no'} "
        f"| roles={','.join(account.role_names)}"
        for account in accounts
    ]


def _format_scope(plan: ResetPlan, heading: str) -> str:
    """Return a credential-safe report for either preview or execution."""
    lines = [
        heading,
        *_format_accounts("Retained administrator accounts", plan.retained_administrators),
        *_format_accounts("Targeted non-admin accounts", plan.targeted_users),
        "Dependent records removed on a confirmed reset:",
    ]
    lines.extend(
        f"  - {label}: {count}"
        for label, count in plan.dependent_record_counts.items()
    )
    lines.append(
        "Audit log records retained with user reference cleared: "
        f"{plan.audit_logs_to_unlink}"
    )
    lines.append(f"Active retained administrators: {plan.active_administrator_count}")
    if plan.invitation_blockers:
        lines.append(
            "Execution blocked by restrictive provider invitations "
            "(creator email: count):"
        )
        lines.extend(
            f"  - {blocker.creator_email}: {blocker.invitation_count}"
            for blocker in plan.invitation_blockers
        )
    elif plan.active_administrator_count == 0:
        lines.append("Execution blocked: no active administrator would remain.")
    else:
        lines.append("Execution preflight: safe to confirm.")
    return "\n".join(lines)


def format_plan(plan: ResetPlan) -> str:
    """Return a credential-safe human-readable dry-run report."""
    return _format_scope(plan, "Non-admin user reset preview — no changes have been made.")


def format_result(result: ResetResult) -> str:
    """Return the committed, auditable result without exposing credentials."""
    return (
        f"{_format_scope(result.plan, 'Confirmed non-admin user reset scope:')}\n"
        "Non-admin user reset committed: "
        f"users_deleted={result.deleted_user_count}."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview or explicitly reset all non-administrator accounts."
    )
    parser.add_argument(
        "--confirm",
        metavar="PHRASE",
        help=f"Required for deletion; must exactly equal {RESET_CONFIRMATION}.",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        if args.confirm is None:
            print(format_plan(build_reset_plan(db)))
            print(
                "Dry run only. To delete the listed accounts, rerun with "
                f"--confirm {RESET_CONFIRMATION}."
            )
            return 0

        if args.confirm != RESET_CONFIRMATION:
            # Show the scope before refusing a typo or vague confirmation.
            print(format_plan(build_reset_plan(db)))
            raise ConfirmationRequiredError(
                f"--confirm must exactly equal {RESET_CONFIRMATION}. No changes were made."
            )

        result = execute_reset(db, confirmation=args.confirm)
        print(format_result(result))
        return 0
    except ResetError as exc:
        print(f"Reset not performed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        db.rollback()
        print(f"Reset failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())