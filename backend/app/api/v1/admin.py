"""
Admin-only endpoints.
GET /api/v1/admin/dashboard/stats
"""
from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role, CurrentUser
from app.db.session import get_db
from app.models.enums import InvitationStatus, ProviderStatus, ProviderType
from app.models.invitation import ProviderInvitation
from app.models.public_visit import PublicVisitDaily
from app.models.provider import Provider, ProviderLocation
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit_log import AuditActor, AuditChange, AuditLogListResponse, AuditLogResponse
from app.schemas.common import PaginationMeta

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/dashboard/stats",
    dependencies=[Depends(require_role("admin"))],
)
def dashboard_stats(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Dashboard statistics: providers, invitations, visitors, and map markers."""
    total_users = db.scalar(select(func.count()).select_from(User))
    active_providers = db.scalar(
        select(func.count())
        .select_from(Provider)
        .where(Provider.status == ProviderStatus.ACTIVE)
    )

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

    invitation_status_counts = dict(
        db.execute(
            select(ProviderInvitation.status, func.count())
            .group_by(ProviderInvitation.status)
        ).all()
    )
    invitation_counts = {
        "sent": sum(invitation_status_counts.values()),
        "accepted": (
            invitation_status_counts.get(InvitationStatus.ACCEPTED, 0)
            + invitation_status_counts.get(InvitationStatus.COMPLETED, 0)
        ),
        "rejected": (
            invitation_status_counts.get(InvitationStatus.CANCELLED, 0)
            + invitation_status_counts.get(InvitationStatus.EXPIRED, 0)
        ),
    }

    today = datetime.now(timezone.utc).date()
    first_visit_date = today - timedelta(days=6)
    visit_rows = db.execute(
        select(PublicVisitDaily.visit_date, PublicVisitDaily.visit_count)
        .where(PublicVisitDaily.visit_date >= first_visit_date)
        .order_by(PublicVisitDaily.visit_date)
    ).all()
    visits_by_date = dict(visit_rows)
    visitor_visits = [
        {
            "date": (first_visit_date + timedelta(days=offset)).isoformat(),
            "count": visits_by_date.get(first_visit_date + timedelta(days=offset), 0),
        }
        for offset in range(7)
    ]

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
        "active_providers": active_providers,
        "provider_counts": provider_counts,
        "invitation_counts": invitation_counts,
        "visitor_visits": visitor_visits,
        "location_markers": location_markers,
    }


def _audit_response(event) -> AuditLogResponse:
    metadata = event.event_metadata or {}
    if event.user:
        actor = AuditActor(
            id=event.user.id,
            name=event.user.full_name,
            email=event.user.email,
            kind=event.actor_type or "admin",
        )
    elif event.actor_type == "public_invitation":
        actor = AuditActor(name="Public invitation", kind="public_invitation")
    else:
        actor = AuditActor(name="System", kind=event.actor_type or "system")
    return AuditLogResponse(
        id=event.id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        actor=actor,
        created_at=event.created_at,
        summary=str(metadata.get("summary") or event.action.replace(".", " ").replace("_", " ").title()),
        changes=[AuditChange(**item) for item in metadata.get("changes", [])],
        metadata=metadata,
    )


@router.get(
    "/activity-logs",
    response_model=AuditLogListResponse,
    dependencies=[Depends(require_role("admin"))],
)
def list_activity_logs(
    db: Annotated[Session, Depends(get_db)],
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> AuditLogListResponse:
    """Newest-first, inclusive date-filtered administrator activity history."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_date_range",
                "message": "Start date must be on or before end date.",
            },
        )
    events, total = AuditRepository(db).list(
        date_from=date_from, date_to=date_to, page=page, page_size=page_size
    )
    return AuditLogListResponse(
        data=[_audit_response(event) for event in events],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )
