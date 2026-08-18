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
