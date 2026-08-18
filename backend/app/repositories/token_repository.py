"""
Refresh token data access.
Tokens are stored as SHA-256 hashes — never plaintext.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.refresh_token import RefreshToken


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of a raw JWT string for safe DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


class TokenRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def store(self, user_id: uuid.UUID, raw_token: str) -> RefreshToken:
        settings = get_settings()
        record = RefreshToken(
            user_id=user_id,
            token_hash=_hash_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self._db.add(record)
        self._db.flush()
        return record

    def get_valid(self, raw_token: str) -> RefreshToken | None:
        token_hash = _hash_token(raw_token)
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        return self._db.scalars(stmt).first()

    def revoke(self, record: RefreshToken) -> None:
        record.revoked_at = datetime.now(timezone.utc)
        self._db.flush()

    def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        """Revoke all active tokens for a user (e.g., on logout-all / security event)."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        tokens = self._db.scalars(stmt).all()
        for t in tokens:
            t.revoked_at = now
        self._db.flush()
        return len(tokens)

    def purge_expired(self) -> int:
        """Delete expired tokens — call periodically as a cleanup job."""
        stmt = delete(RefreshToken).where(
            RefreshToken.expires_at < datetime.now(timezone.utc)
        )
        result = self._db.execute(stmt)
        self._db.flush()
        return result.rowcount
