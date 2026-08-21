"""
Authentication business logic.
All auth decisions go through this service — never directly in route handlers.
"""
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.auth.account_access import PublicAccountAccessIssue, public_account_access_issue
from app.models.enums import PublicAccountApprovalStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegistrationRequest, UserProfile
from app.models.user import EmailVerificationToken
from app.services.email_service import EmailDeliveryError, EmailService

logger = get_logger(__name__)


class AuthenticationError(Exception):
    """Raised when credentials are invalid."""


class InactiveUserError(Exception):
    """Raised when the user account is disabled."""

class PublicAccountAccessError(Exception):
    """Raised when a public registration has not met member-access requirements."""

    def __init__(self, issue: PublicAccountAccessIssue) -> None:
        super().__init__(issue.message)
        self.code = issue.code
class InvalidTokenError(Exception):
    """Raised when a refresh token is invalid or expired."""


class DuplicateEmailError(Exception):
    """Raised when a registration attempts to reuse an account email."""


class RegistrationUnavailableError(Exception):
    """Raised when required public registration roles are unavailable."""


class VerificationTokenNotFoundError(Exception):
    """Raised when a verification token is invalid."""


class VerificationTokenExpiredError(Exception):
    """Raised when a verification token has expired."""


class VerificationTokenUsedError(Exception):
    """Raised when a verification token was already redeemed."""


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # access token lifetime in seconds


@dataclass
class LoginResult:
    """Full result of a successful login — includes both tokens and the user profile."""
    access_token: str
    refresh_token: str
    expires_in: int
    user_profile: "UserProfile"


class AuthService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._users = UserRepository(db)
        self._tokens = TokenRepository(db)
        self._audit = AuditRepository(db)
        self._email = EmailService()

    # ── Public registration and verification ───────────────────────────────────

    def register(self, registration: RegistrationRequest) -> None:
        """Create a pending public account and deliver its verification link."""
        from app.core.config import get_settings

        email = registration.email.lower().strip()
        if self._users.get_by_email(email) is not None:
            raise DuplicateEmailError("An account with this email already exists.")

        role_names = {
            "HORSE_OWNER": ["horse_owner"],
            "STABLE_MANAGER": ["stable_manager"],
            "BOTH": ["horse_owner", "stable_manager"],
        }[registration.role]
        try:
            roles = self._users.get_roles_by_names(role_names)
            roles_by_name = {role.name: role for role in roles}
            if set(roles_by_name) != set(role_names):
                logger.error(
                    "registration.configuration_missing",
                    required_roles=role_names,
                    configured_roles=sorted(roles_by_name),
                )
                raise RegistrationUnavailableError

            now = datetime.now(timezone.utc)
            primary_role = roles_by_name[role_names[0]]
            user = self._users.create_user(
                email=email,
                password_hash=hash_password(registration.password),
                role=primary_role,
                roles=[roles_by_name[name] for name in role_names],
                first_name=registration.first_name,
                last_name=registration.last_name,
                mobile_number=registration.mobile_number,
                country=registration.country,
                state_province=registration.state_province,
                city=registration.city,
                terms_accepted_at=now,
                privacy_accepted_at=now,
                is_active=True,
                approval_status=PublicAccountApprovalStatus.PENDING,
            )

            raw_token = secrets.token_urlsafe(32)
            expires_at = now + timedelta(
                hours=get_settings().EMAIL_VERIFICATION_EXPIRE_HOURS
            )
            self._db.add(
                EmailVerificationToken(
                    user_id=user.id,
                    token_hash=self._hash_verification_token(raw_token),
                    expires_at=expires_at,
                )
            )
            self._db.flush()

            verification_url = (
                f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/verify-email"
                f"?token={quote(raw_token, safe='')}"
            )
            self._email.send_verification_email(email, verification_url, expires_at)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise DuplicateEmailError("An account with this email already exists.") from exc
        except RegistrationUnavailableError:
            self._db.rollback()
            raise
        except EmailDeliveryError:
            self._db.rollback()
            raise

    def verify_email(self, raw_token: str) -> None:
        """Redeem a verification token without changing its approval state."""
        token_hash = self._hash_verification_token(raw_token)
        # Lock the token row while checking and consuming it. Under PostgreSQL's
        # READ COMMITTED isolation, a concurrent redemption waits here and then
        # observes ``used_at`` after the first request commits.
        token = (
            self._db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.token_hash == token_hash)
            .with_for_update()
            .first()
        )
        if token is None:
            raise VerificationTokenNotFoundError("Verification link is invalid.")
        if token.used_at is not None:
            raise VerificationTokenUsedError("Verification link was already used.")
        if token.expires_at <= datetime.now(timezone.utc):
            raise VerificationTokenExpiredError("Verification link has expired.")

        token.used_at = datetime.now(timezone.utc)
        token.user.email_verified_at = token.used_at
        self._db.commit()


    # ── Login ────────────────────────────────────────────────────────────────

    def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> "LoginResult":
        from app.core.config import get_settings
        settings = get_settings()

        user = self._users.get_by_email(email)

        # Constant-time check — always call verify even if user not found
        dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$dummysalt0000000$dummyhash0000000000000000000000000000000"
        if user is None:
            verify_password(password, dummy_hash)
            logger.warning("login.failed.unknown_email", email=email)
            raise AuthenticationError("Invalid email or password")

        if not verify_password(password, user.password_hash):
            logger.warning("login.failed.wrong_password", user_id=str(user.id))
            self._audit.log(
                action="admin.login.failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "wrong_password"},
            )
            self._db.commit()
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            logger.warning("login.failed.inactive", user_id=str(user.id))
            raise InactiveUserError("Account is disabled")
        self._require_member_access(user)

        # Optional: rehash if Argon2 parameters are outdated
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        pair = self._issue_token_pair(user.id)

        self._audit.log(
            action="admin.login.success",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._db.commit()

        logger.info("login.success", user_id=str(user.id))

        profile = UserProfile(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            role=user.role.name,
            is_active=user.is_active,
        )
        return LoginResult(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            expires_in=pair.expires_in,
            user_profile=profile,
        )

    # ── Refresh ──────────────────────────────────────────────────────────────

    def refresh(self, raw_refresh_token: str) -> TokenPair:
        from jose import JWTError
        from app.core.security import decode_token

        try:
            payload = decode_token(raw_refresh_token)
        except JWTError:
            raise InvalidTokenError("Token is invalid or expired")

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Wrong token type")

        record = self._tokens.get_valid(raw_refresh_token)
        if record is None:
            logger.warning("refresh.failed.token_not_found_or_revoked")
            raise InvalidTokenError("Token not found or revoked")

        user_id = uuid.UUID(payload["sub"])
        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError("User not found or inactive")
        self._require_member_access(user)

        # Rotate: revoke old, issue new
        self._tokens.revoke(record)
        pair = self._issue_token_pair(user.id)
        self._db.commit()

        return pair

    # ── Logout ───────────────────────────────────────────────────────────────

    def logout(
        self,
        user_id: uuid.UUID,
        raw_refresh_token: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if raw_refresh_token:
            record = self._tokens.get_valid(raw_refresh_token)
            if record:
                self._tokens.revoke(record)

        self._audit.log(
            action="admin.logout",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._db.commit()
        logger.info("logout.success", user_id=str(user_id))

    # ── Operational credential recovery ───────────────────────────────────────

    def recover_bootstrap_admin_password(
        self,
        user_id: uuid.UUID,
        new_password: str,
    ) -> int:
        """Rotate an active administrator's password and revoke refresh sessions.

        This is deliberately not exposed as an HTTP endpoint. The operational
        bootstrap command calls it only after its explicit recovery confirmation.
        """
        user = self._users.get_by_id(user_id)
        if user is None:
            raise ValueError("Bootstrap administrator no longer exists.")
        if not user.is_active or user.role.name != "admin":
            raise ValueError(
                "Only an active account with the administrator role can be recovered."
            )

        self._users.update_password_hash(user, hash_password(new_password))
        revoked_sessions = self._tokens.revoke_all_for_user(user.id)
        self._audit.log(
            action="admin.bootstrap_password_recovered",
            user_id=user.id,
            metadata={"revoked_refresh_sessions": revoked_sessions},
        )
        self._db.commit()
        logger.info(
            "admin.bootstrap_password_recovered",
            user_id=str(user.id),
            revoked_refresh_sessions=revoked_sessions,
        )
        return revoked_sessions

    # ── Internal ─────────────────────────────────────────────────────────────

    def _issue_token_pair(self, user_id: uuid.UUID) -> TokenPair:
        from app.core.config import get_settings
        settings = get_settings()

        access_token = create_access_token(subject=user_id)
        refresh_token = create_refresh_token(subject=user_id)
        self._tokens.store(user_id=user_id, raw_token=refresh_token)

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    @staticmethod
    def _require_member_access(user) -> None:
        issue = public_account_access_issue(user)
        if issue is not None:
            raise PublicAccountAccessError(issue)

    @staticmethod
    def _hash_verification_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
