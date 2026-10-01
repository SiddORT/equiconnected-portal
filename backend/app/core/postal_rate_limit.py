"""PostgreSQL-backed postal budget shared by all application processes."""
from datetime import timedelta
from hashlib import sha256

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.postal_lookup_rate_limit import PostalLookupRateLimit

WINDOW_SECONDS = 60
MAX_ATTEMPTS = 20


def consume_postal_lookup_attempt(db: Session, ip: str) -> bool:
    """Commit an allowed attempt before calling the external postal source.

    An upsert reserves even a previously unseen caller's row. The row lock then
    serializes pruning and consumption across independent connections/processes.
    Use the database clock *after* acquiring that lock, never a worker's clock.
    """
    key = sha256(ip.encode("utf-8")).hexdigest()
    model = PostalLookupRateLimit
    try:
        db.execute(
            insert(model)
            .values(key=key, attempts=[], expires_at=func.clock_timestamp())
            .on_conflict_do_nothing(index_elements=[model.key])
        )
        bucket = db.execute(
            select(model).where(model.key == key).with_for_update()
        ).scalar_one()
        now = db.scalar(select(func.clock_timestamp()))
        # Bound stale-state cleanup work. Skip locked rows so maintenance cannot
        # block active callers. Always reserve our own row FIRST, so cleanup
        # cannot hold another consumer's row while waiting on our own.
        expired = (
            select(model.key)
            .where(model.expires_at < now, model.key != key)
            .order_by(model.expires_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        db.execute(
            delete(model).where(model.key.in_(expired)),
            execution_options={"synchronize_session": False},
        )
        cutoff = now - timedelta(seconds=WINDOW_SECONDS)
        recent = [attempt for attempt in bucket.attempts if attempt >= cutoff]
        allowed = len(recent) < MAX_ATTEMPTS
        if allowed:
            recent.append(now)
        bucket.attempts = recent
        bucket.expires_at = recent[-1] + timedelta(seconds=WINDOW_SECONDS)
        db.commit()
        return allowed
    except Exception:
        db.rollback()
        raise