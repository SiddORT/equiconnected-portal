"""
FastAPI dependency functions for authentication and authorization.
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"code": "unauthorized", "message": "Authentication required"},
    headers={"WWW-Authenticate": "Bearer"},
)
FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail={"code": "forbidden", "message": "You do not have permission to access this resource"},
)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Extract and validate the JWT access token, return the authenticated user."""
    if not credentials:
        raise UNAUTHORIZED

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise UNAUTHORIZED

    if payload.get("type") != "access":
        raise UNAUTHORIZED

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise UNAUTHORIZED

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise UNAUTHORIZED
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "account_disabled", "message": "Account is disabled"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    """
    Dependency factory that enforces role membership.

    Usage:
        @router.get("/admin/x", dependencies=[Depends(require_role("admin"))])
    """
    def _check(user: CurrentUser) -> User:
        if user.role.name not in roles:
            logger.warning(
                "auth.forbidden",
                user_id=str(user.id),
                required_roles=roles,
                user_role=user.role.name,
            )
            raise FORBIDDEN
        return user

    return _check


AdminUser = Annotated[User, Depends(require_role("admin"))]
