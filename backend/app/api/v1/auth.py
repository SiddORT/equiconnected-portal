"""
Authentication endpoints.
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, UserProfile
from app.schemas.common import MessageResponse
from app.services.auth_service import (
    AuthService,
    AuthenticationError,
    InactiveUserError,
    InvalidTokenError,
    LoginResult,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)

REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth")


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    """Authenticate with email + password. Returns access token; sets httpOnly refresh cookie."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    try:
        result: LoginResult = AuthService(db).login(
            email=body.email,
            password=body.password,
            ip_address=ip,
            user_agent=ua,
        )
    except (AuthenticationError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": str(exc)},
        )

    # Refresh token goes in httpOnly cookie; access token in body
    _set_refresh_cookie(response, result.refresh_token)

    return LoginResponse(
        access_token=result.access_token,
        token_type="bearer",
        expires_in=result.expires_in,
        user=result.user_profile,
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> LoginResponse:
    """Exchange a valid refresh token for a new access token + rotated refresh token."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "no_refresh_token", "message": "Refresh token missing"},
        )

    try:
        payload = decode_token(refresh_token)
        user_id = uuid.UUID(payload["sub"])

        svc = AuthService(db)
        pair = svc.refresh(refresh_token)
        _set_refresh_cookie(response, pair.refresh_token)

        from app.repositories.user_repository import UserRepository
        user = UserRepository(db).get_by_id(user_id)
        if user is None:
            raise InvalidTokenError("User not found")

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
    except InvalidTokenError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_refresh_token", "message": str(exc)},
        )
    except Exception:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_refresh_token", "message": "Token is invalid or expired"},
        )


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> MessageResponse:
    """Revoke the current session. Clears refresh token cookie."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    AuthService(db).logout(
        user_id=current_user.id,
        raw_refresh_token=refresh_token,
        ip_address=ip,
        user_agent=ua,
    )
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserProfile)
def me(current_user: CurrentUser) -> UserProfile:
    """Return the authenticated user's profile."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        full_name=current_user.full_name,
        role=current_user.role.name,
        is_active=current_user.is_active,
    )
