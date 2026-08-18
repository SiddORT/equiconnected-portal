"""
Authentication business logic.
All auth decisions go through this service — never directly in route handlers.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginResponse, UserProfile

logger = get_logger(__name__)


class AuthenticationError(Exception):
    """Raised when credentials are invalid."""


class InactiveUserError(Exception):
    """Raised when the user account is disabled."""


class InvalidTokenError(Exception):
    """Raised when a refresh token is invalid or expired."""


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # access token lifetime in seconds


class AuthService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._users = UserRepository(db)
        self._tokens = TokenRepository(db)
        self._audit = AuditRepository(db)

    # ── Login ────────────────────────────────────────────────────────────────

    def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponse:
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
        return LoginResponse(
            access_token=pair.access_token,
            token_type="bearer",
            expires_in=pair.expires_in,
            user=profile,
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
