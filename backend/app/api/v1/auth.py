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
from app.core.rate_limit import (
    check_email_verification_rate_limit,
    check_login_rate_limit,
    check_registration_rate_limit,
)
from app.core.security import decode_token
from app.db.session import get_db
from app.schemas.auth import (
    EmailVerificationRequest,
    LoginRequest,
    LoginResponse,
    RegistrationRequest,
    UserProfile,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import (
    AuthService,
    AuthenticationError,
    DuplicateEmailError,
    InactiveUserError,
    InvalidTokenError,
    LoginResult,
    PublicAccountAccessError,
    RegistrationUnavailableError,
    VerificationTokenExpiredError,
    VerificationTokenNotFoundError,
    VerificationTokenUsedError,
)
from app.services.email_service import EmailDeliveryError

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


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_registration_rate_limit)],
)
def register(
    body: RegistrationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    """Create a public account and send its email-verification link."""
    try:
        AuthService(db).register(body)
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "email_already_registered",
                "message": "An account with this email already exists.",
            },
        )
    except RegistrationUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "registration_unavailable",
                "message": "Registration is temporarily unavailable. Please try again later.",
            },
        )
    except EmailDeliveryError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "verification_email_failed",
                "message": "We could not send your verification email. Please try again.",
            },
        )
    return MessageResponse(
        message="Account created. Please check your email to verify your account."
    )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[Depends(check_email_verification_rate_limit)],
)
def verify_email(
    body: EmailVerificationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    """Verify a public account using the token delivered in its email link."""
    try:
        AuthService(db).verify_email(body.token)
    except VerificationTokenNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "verification_link_invalid", "message": "Verification link is invalid."},
        )
    except VerificationTokenUsedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "verification_link_used", "message": "This email is already verified."},
        )
    except VerificationTokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"code": "verification_link_expired", "message": "Verification link has expired."},
        )
    return MessageResponse(
        message="Your email has been verified. Your account is awaiting administrator approval."
    )


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(check_login_rate_limit)])
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
    except PublicAccountAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": str(exc)},
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

        profile = AuthService._safe_user_profile(user)
        return LoginResponse(
            access_token=pair.access_token,
            token_type="bearer",
            expires_in=pair.expires_in,
            user=profile,
        )
    except PublicAccountAccessError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": str(exc)},
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
    return AuthService._safe_user_profile(current_user)
