"""Create or safely verify the configured bootstrap administrator.

Normal usage is non-destructive: an existing account is never activated,
promoted, deleted, or assigned a new password. Its configured credential is
only verified and the result is reported without exposing credentials or
hashes.

Set ``ADMIN_RECOVERY_CONFIRM=RESET_BOOTSTRAP_PASSWORD`` only for the deliberate
recovery action. That rotates the existing active admin's password and revokes
all of its refresh sessions. Credentials must never be command-line arguments
or hard-coded.
"""
import os
import sys
import uuid
from dataclasses import dataclass

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.core.security import hash_password, verify_password  # noqa: E402
import app.db.base  # noqa: F401, E402 — registers all models in the mapper registry
from app.db.session import SessionLocal  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402

configure_logging()
logger = get_logger(__name__)

RECOVERY_CONFIRM_ENV = "ADMIN_RECOVERY_CONFIRM"
RECOVERY_CONFIRM_VALUE = "RESET_BOOTSTRAP_PASSWORD"


@dataclass(frozen=True)
class BootstrapResult:
    """Secret-safe outcome returned by the bootstrap operation."""

    status: str
    email: str
    user_id: uuid.UUID | None
    is_active: bool | None
    has_admin_role: bool | None
    credential_matches: bool | None
    revoked_refresh_sessions: int = 0


def bootstrap_admin(
    db,
    *,
    email: str,
    password: str,
    first_name: str | None = None,
    last_name: str | None = None,
    recover_password: bool = False,
) -> BootstrapResult:
    """Create a bootstrap admin once, then only verify it unless recovery is explicit."""
    repo = UserRepository(db)
    existing = repo.get_by_email(email)

    if existing is not None:
        has_admin_role = existing.role.name == "admin"
        credential_matches = verify_password(password, existing.password_hash)

        if recover_password:
            if not existing.is_active or not has_admin_role:
                return BootstrapResult(
                    status="recovery_not_allowed",
                    email=email,
                    user_id=existing.id,
                    is_active=existing.is_active,
                    has_admin_role=has_admin_role,
                    credential_matches=credential_matches,
                )

            revoked_sessions = AuthService(db).recover_bootstrap_admin_password(
                existing.id, password
            )
            return BootstrapResult(
                status="recovered",
                email=email,
                user_id=existing.id,
                is_active=existing.is_active,
                has_admin_role=has_admin_role,
                credential_matches=credential_matches,
                revoked_refresh_sessions=revoked_sessions,
            )

        return BootstrapResult(
            status=(
                "verified"
                if existing.is_active and has_admin_role and credential_matches
                else "verification_requires_attention"
            ),
            email=email,
            user_id=existing.id,
            is_active=existing.is_active,
            has_admin_role=has_admin_role,
            credential_matches=credential_matches,
        )

    if recover_password:
        raise ValueError(
            "Recovery was requested but the configured administrator does not exist. "
            f"Unset {RECOVERY_CONFIRM_ENV} and run the normal bootstrap command first."
        )

    role = repo.get_role_by_name("admin")
    if role is None:
        logger.info("seed.creating_role", role="admin")
        role = repo.create_role("admin", description="Full system administrator")

    user = repo.create_user(
        email=email,
        password_hash=hash_password(password),
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    repo.commit()
    return BootstrapResult(
        status="created",
        email=email,
        user_id=user.id,
        is_active=user.is_active,
        has_admin_role=True,
        credential_matches=True,
    )


def _recovery_requested() -> bool:
    confirmation = os.environ.get(RECOVERY_CONFIRM_ENV, "")
    if not confirmation:
        return False
    if confirmation != RECOVERY_CONFIRM_VALUE:
        raise ValueError(
            f"{RECOVERY_CONFIRM_ENV} must be exactly {RECOVERY_CONFIRM_VALUE} "
            "to rotate a bootstrap password."
        )
    return True


def _format_result(result: BootstrapResult) -> str:
    """Format a diagnostic that intentionally contains no password or hash."""
    state = (
        f"email={result.email} active={'yes' if result.is_active else 'no'} "
        f"admin_role={'yes' if result.has_admin_role else 'no'}"
    )
    if result.status == "created":
        return f"Admin bootstrap created: {state}"
    if result.status == "verified":
        return f"Admin bootstrap verified: {state} credential=matches"
    if result.status == "recovered":
        return (
            f"Admin bootstrap recovery completed: {state} "
            f"refresh_sessions_revoked={result.revoked_refresh_sessions}"
        )
    if result.status == "recovery_not_allowed":
        return (
            f"Admin bootstrap recovery blocked: {state}. "
            "The account was not changed."
        )
    return (
        f"Admin bootstrap needs attention: {state} "
        f"credential={'matches' if result.credential_matches else 'does-not-match'}. "
        f"The account was not changed. To deliberately rotate an active admin "
        f"password, set {RECOVERY_CONFIRM_ENV}={RECOVERY_CONFIRM_VALUE}."
    )


def main() -> int:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")

    if not email:
        logger.error("seed.missing_env", var="ADMIN_EMAIL")
        return 1
    if len(password) < 12:
        logger.error("seed.password_too_short", min_length=12)
        return 1

    db = SessionLocal()
    try:
        recover_password = _recovery_requested()
        result = bootstrap_admin(
            db,
            email=email,
            password=password,
            first_name=os.environ.get("ADMIN_FIRST_NAME"),
            last_name=os.environ.get("ADMIN_LAST_NAME"),
            recover_password=recover_password,
        )
        logger.info(
            "seed.admin_result",
            status=result.status,
            user_id=str(result.user_id) if result.user_id else None,
            email=result.email,
            is_active=result.is_active,
            has_admin_role=result.has_admin_role,
            credential_matches=result.credential_matches,
            revoked_refresh_sessions=result.revoked_refresh_sessions,
        )
        print(_format_result(result))
        return 0 if result.status in {"created", "verified", "recovered"} else 2

    except Exception as exc:
        db.rollback()
        logger.error("seed.failed", error=str(exc))
        print(f"✗ Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
