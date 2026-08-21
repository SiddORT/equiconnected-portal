"""
Simple in-memory brute-force rate limiter for the login endpoint.

Limits each remote IP to MAX_ATTEMPTS login attempts within WINDOW_SECONDS.
The counter resets on server restart. For multi-process/production deployments
replace this with a Redis-backed strategy (e.g. slowapi + Redis).

Usage:
    from app.core.rate_limit import check_login_rate_limit

    @router.post("/login", dependencies=[Depends(check_login_rate_limit)])
    def login(...): ...
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

# ── Configuration ─────────────────────────────────────────────────────────────

_WINDOW_SECONDS: int = 300   # sliding 5-minute window
_MAX_ATTEMPTS: int = 10       # maximum login attempts per window per IP

# ── State ─────────────────────────────────────────────────────────────────────

_lock = threading.Lock()
# Maps IP → deque of monotonic timestamps of recent attempts
_attempts: dict[str, deque[float]] = defaultdict(deque)
_invitation_attempts: dict[str, deque[float]] = defaultdict(deque)
_public_visit_attempts: dict[str, deque[float]] = defaultdict(deque)
_subscriber_attempts: dict[str, deque[float]] = defaultdict(deque)
_registration_attempts: dict[str, deque[float]] = defaultdict(deque)
_email_verification_attempts: dict[str, deque[float]] = defaultdict(deque)


# ── Dependency ────────────────────────────────────────────────────────────────

def check_login_rate_limit(request: Request) -> None:
    """
    FastAPI dependency — raises HTTP 429 if the caller has exceeded the
    login attempt threshold. Safe to use as a sync dependency.

    :raises HTTPException: 429 Too Many Requests when the limit is exceeded.
    """
    ip: str = (request.client.host if request.client else None) or "unknown"
    now: float = time.monotonic()
    cutoff: float = now - _WINDOW_SECONDS

    with _lock:
        q = _attempts[ip]

        # Evict timestamps outside the rolling window
        while q and q[0] < cutoff:
            q.popleft()

        if len(q) >= _MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "rate_limited",
                    "message": "Too many login attempts. Please try again later.",
                },
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )

        q.append(now)


def check_invitation_rate_limit(request: Request) -> None:
    """Limit public invitation-token requests without retaining raw tokens."""
    ip: str = (request.client.host if request.client else None) or "unknown"
    now: float = time.monotonic()
    window_seconds = 300
    max_attempts = 60
    cutoff = now - window_seconds
    with _lock:
        q = _invitation_attempts[ip]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "rate_limited",
                    "message": "Too many invitation requests. Please try again later.",
                },
                headers={"Retry-After": str(window_seconds)},
            )
        q.append(now)


def check_public_visit_rate_limit(request: Request) -> None:
    """Limit anonymous visit events without persisting visitor identifiers."""
    ip: str = (request.client.host if request.client else None) or "unknown"
    now: float = time.monotonic()
    window_seconds = 60
    max_attempts = 30
    cutoff = now - window_seconds
    with _lock:
        q = _public_visit_attempts[ip]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "rate_limited",
                    "message": "Too many visit events. Please try again later.",
                },
                headers={"Retry-After": str(window_seconds)},
            )
        q.append(now)


def check_subscriber_rate_limit(request: Request) -> None:
    """Limit anonymous subscriber submissions per remote IP."""
    _check_rate_limit(
        request,
        _subscriber_attempts,
        window_seconds=600,
        max_attempts=5,
        message="Too many subscriber registrations. Please try again later.",
    )


def _check_rate_limit(
    request: Request,
    attempts: dict[str, deque[float]],
    *,
    window_seconds: int,
    max_attempts: int,
    message: str,
) -> None:
    ip: str = (request.client.host if request.client else None) or "unknown"
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        q = attempts[ip]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "rate_limited", "message": message},
                headers={"Retry-After": str(window_seconds)},
            )
        q.append(now)


def check_registration_rate_limit(request: Request) -> None:
    """Limit unauthenticated account creation attempts per IP."""
    _check_rate_limit(
        request,
        _registration_attempts,
        window_seconds=600,
        max_attempts=5,
        message="Too many registration attempts. Please try again later.",
    )


def check_email_verification_rate_limit(request: Request) -> None:
    """Limit verification attempts without retaining supplied tokens."""
    _check_rate_limit(
        request,
        _email_verification_attempts,
        window_seconds=300,
        max_attempts=20,
        message="Too many verification attempts. Please try again later.",
    )
