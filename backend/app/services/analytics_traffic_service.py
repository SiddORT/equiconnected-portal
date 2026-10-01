"""Atomic, aggregate-only traffic ingestion."""
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.analytics_traffic import (
    TrafficPageCategoryDaily,
    TrafficProviderProfileDaily,
    TrafficTrackingReceipt,
    TrafficVisitorDaily,
)


RECEIPT_RETENTION = timedelta(hours=48)
RECEIPT_CLEANUP_BATCH_SIZE = 200
TRAFFIC_CATEGORIES = frozenset(
    {
        "home",
        "animation",
        "signup",
        "provider_signup",
        "terms",
        "privacy",
        "provider_directory",
        "provider_profile",
    }
)


def record_successful_view(
    db: Session,
    *,
    visit_date: date,
    category: str,
    navigation_key: UUID,
    first_eligible_view_today: bool,
    provider_id: UUID | None = None,
) -> bool:
    """Atomically count a successful view once per short-lived navigation key.

    The only retained key is the UUID receipt itself. Its row contains no
    category, date, provider, account or client/network identifier and expires
    after 48 hours. ``False`` means this was a duplicate delivery.
    """
    if category not in TRAFFIC_CATEGORIES:
        raise ValueError("Traffic category is not allowlisted.")
    if (category == "provider_profile") != (provider_id is not None):
        raise ValueError("Provider identifier must match the page category.")

    now = datetime.now(timezone.utc)
    receipt_table = TrafficTrackingReceipt.__table__
    page_table = TrafficPageCategoryDaily.__table__
    try:
        inserted_key = db.execute(
            insert(TrafficTrackingReceipt)
            .values(
                navigation_key=navigation_key,
                created_at=now,
                expires_at=now + RECEIPT_RETENTION,
            )
            .on_conflict_do_update(
                index_elements=[receipt_table.c.navigation_key],
                set_={
                    "created_at": now,
                    "expires_at": now + RECEIPT_RETENTION,
                },
                where=receipt_table.c.expires_at <= now,
            )
            .returning(receipt_table.c.navigation_key)
        ).scalar_one_or_none()
        if inserted_key is None:
            return False

        db.execute(
            insert(TrafficPageCategoryDaily)
            .values(
                visit_date=visit_date,
                category=category,
                page_views=1,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[page_table.c.visit_date, page_table.c.category],
                set_={
                    "page_views": page_table.c.page_views + 1,
                    "updated_at": now,
                },
            )
        )

        if provider_id is not None:
            provider_table = TrafficProviderProfileDaily.__table__
            db.execute(
                insert(TrafficProviderProfileDaily)
                .values(
                    visit_date=visit_date,
                    provider_id=provider_id,
                    profile_views=1,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[
                        provider_table.c.visit_date,
                        provider_table.c.provider_id,
                    ],
                    set_={
                        "profile_views": provider_table.c.profile_views + 1,
                        "updated_at": now,
                    },
                )
            )

        if first_eligible_view_today:
            visitor_table = TrafficVisitorDaily.__table__
            db.execute(
                insert(TrafficVisitorDaily)
                .values(
                    visit_date=visit_date,
                    estimated_visitors=1,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[visitor_table.c.visit_date],
                    set_={
                        "estimated_visitors": visitor_table.c.estimated_visitors + 1,
                        "updated_at": now,
                    },
                )
            )

        expired_keys = select(receipt_table.c.navigation_key).where(
            receipt_table.c.expires_at < now
        ).order_by(receipt_table.c.expires_at).limit(RECEIPT_CLEANUP_BATCH_SIZE)
        db.execute(
            delete(receipt_table).where(
                receipt_table.c.navigation_key.in_(expired_keys)
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise