"""
Admin-only endpoints.
GET /api/v1/admin/dashboard/stats
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role, CurrentUser
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import ProviderType
from app.models.provider import Provider, ProviderLocation
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/dashboard/stats",
    dependencies=[Depends(require_role("admin"))],
)
def dashboard_stats(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Dashboard statistics: user total, provider inventory, map markers, audit."""
    total_users = db.scalar(select(func.count()).select_from(User))
    recent_events = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)
    ).all()

    # Provider totals per type (single grouped query)
    type_counts = dict(
        db.execute(
            select(Provider.provider_type, func.count())
            .group_by(Provider.provider_type)
        ).all()
    )
    provider_counts = {
        "hospitals": type_counts.get(ProviderType.HOSPITAL, 0),
        "clinics": type_counts.get(ProviderType.CLINIC, 0),
        "doctors": type_counts.get(ProviderType.DOCTOR, 0),
    }

    # Locations that can be plotted (both coordinates present)
    rows = db.execute(
        select(ProviderLocation, Provider.name, Provider.provider_type)
        .join(Provider, ProviderLocation.provider_id == Provider.id)
        .where(
            ProviderLocation.latitude.is_not(None),
            ProviderLocation.longitude.is_not(None),
        )
        .order_by(Provider.name)
    ).all()

    location_markers = [
        {
            "location_id": str(loc.id),
            "provider_id": str(loc.provider_id),
            "provider_name": provider_name,
            "provider_type": provider_type.value,
            "location_name": loc.name,
            "address": ", ".join(
                part
                for part in [loc.address_line_1, loc.city, loc.state_province, loc.country]
                if part
            ),
            "city": loc.city,
            "latitude": float(loc.latitude),
            "longitude": float(loc.longitude),
            "is_primary": loc.is_primary,
        }
        for loc, provider_name, provider_type in rows
    ]

    return {
        "total_users": total_users,
        "provider_counts": provider_counts,
        "location_markers": location_markers,
        "recent_audit_events": [
            {
                "id": str(e.id),
                "action": e.action,
                "user_id": str(e.user_id) if e.user_id else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in recent_events
        ],
    }
