"""
Admin-only endpoints.
GET /api/v1/admin/dashboard/stats
"""
from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role, CurrentUser
from app.db.session import get_db
from app.models.enums import (
    InvitationStatus,
    ProviderStatus,
    ProviderType,
    PublicAccountApprovalStatus,
)
from app.models.invitation import ProviderInvitation
from app.models.public_visit import PublicVisitDaily
from app.models.provider import Provider, ProviderLocation
from app.models.role import Role
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User, UserRole
from app.repositories.audit_repository import AuditRepository, context_from_request
from app.schemas.audit_log import AuditActor, AuditChange, AuditLogListResponse, AuditLogResponse
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.user import PublicRegistrantResponse
from app.repositories.user_repository import UserRepository
from app.services.public_account_service import (
    PublicAccountAlreadyDecidedError,
    PublicAccountService,
    PublicRegistrantNotFoundError,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/dashboard/stats",
    dependencies=[Depends(require_role("admin"))],
)
def dashboard_stats(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Dashboard statistics: providers, invitations, public accounts, visits, and map markers."""
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

    public_role_names = ("horse_owner", "stable_manager")
    public_role_counts = dict(
        db.execute(
            select(Role.name, func.count(func.distinct(UserRole.user_id)))
            .join(UserRole, UserRole.role_id == Role.id)
            .where(Role.name.in_(public_role_names))
            .group_by(Role.name)
        ).all()
    )
    public_user_ids = (
        select(UserRole.user_id)
        .join(Role, UserRole.role_id == Role.id)
        .where(Role.name.in_(public_role_names))
        .distinct()
        .subquery()
    )
    public_user_id_select = select(public_user_ids.c.user_id)
    registration_counts = {
        "requests": db.scalar(select(func.count()).select_from(public_user_ids)) or 0,
        "approved": db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.id.in_(public_user_id_select),
                User.approval_status == PublicAccountApprovalStatus.APPROVED,
            )
        )
        or 0,
        "rejected": db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.id.in_(public_user_id_select),
                User.approval_status == PublicAccountApprovalStatus.REJECTED,
            )
        )
        or 0,
        "horse_owners": public_role_counts.get("horse_owner", 0),
        "stable_managers": public_role_counts.get("stable_manager", 0),
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
        "registration_counts": registration_counts,
        "visitor_visits": visitor_visits,
        "location_markers": location_markers,
    }


def _public_registrant_response(user: User) -> PublicRegistrantResponse:
    """Serialize the list/detail payload without leaking credentials or tokens."""
    roles = sorted(
        {
            assignment.role.name
            for assignment in user.role_assignments
            if assignment.role.name in PUBLIC_ACCOUNT_ROLE_NAMES
        }
    )
    return PublicRegistrantResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        email=user.email,
        mobile_number=user.mobile_number,
        country=user.country,
        city=user.city,
        roles=roles,
        email_verified_at=user.email_verified_at,
        approval_status=user.approval_status or PublicAccountApprovalStatus.PENDING,
        approval_decided_at=user.approval_decided_at,
        approval_decided_by=user.approval_decided_by,
        created_at=user.created_at,
    )


@router.get(
    "/users",
    response_model=PaginatedResponse[PublicRegistrantResponse],
    dependencies=[Depends(require_role("admin"))],
)
def list_public_registrants(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(None, max_length=100),
    role: str | None = Query(None),
    approval_status: PublicAccountApprovalStatus | None = Query(None),
    email_verified: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[PublicRegistrantResponse]:
    """Search and filter only public registrations; administrator accounts are excluded."""
    if role and role not in PUBLIC_ACCOUNT_ROLE_NAMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_role_filter", "message": "Invalid public-account role."},
        )
    users, total = UserRepository(db).list_public_registrants(
        search=search,
        role=role,
        approval_status=approval_status,
        email_verified=email_verified,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=[_public_registrant_response(user) for user in users],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


@router.get(
    "/users/{user_id}",
    response_model=PublicRegistrantResponse,
    dependencies=[Depends(require_role("admin"))],
)
def get_public_registrant(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PublicRegistrantResponse:
    user = UserRepository(db).get_public_registrant(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "registrant_not_found", "message": "Public registrant not found."},
        )
    return _public_registrant_response(user)


def _record_decision(
    *,
    user_id: UUID,
    decision: PublicAccountApprovalStatus,
    request: Request,
    current_user: CurrentUser,
    db: Session,
) -> PublicRegistrantResponse:
    try:
        user = PublicAccountService(db).decide(
            user_id=user_id,
            administrator_id=current_user.id,
            decision=decision,
            audit_context=context_from_request(request, user_id=current_user.id),
        )
    except PublicRegistrantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "registrant_not_found", "message": "Public registrant not found."},
        )
    except PublicAccountAlreadyDecidedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "approval_already_decided", "message": str(exc)},
        )
    # Relationships are fetched after the service's commit so the response has all roles.
    refreshed = UserRepository(db).get_public_registrant(user.id)
    return _public_registrant_response(refreshed or user)


@router.post(
    "/users/{user_id}/approve",
    response_model=PublicRegistrantResponse,
    dependencies=[Depends(require_role("admin"))],
)
def approve_public_registrant(
    user_id: UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PublicRegistrantResponse:
    return _record_decision(
        user_id=user_id,
        decision=PublicAccountApprovalStatus.APPROVED,
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/users/{user_id}/reject",
    response_model=PublicRegistrantResponse,
    dependencies=[Depends(require_role("admin"))],
)
def reject_public_registrant(
    user_id: UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PublicRegistrantResponse:
    return _record_decision(
        user_id=user_id,
        decision=PublicAccountApprovalStatus.REJECTED,
        request=request,
        current_user=current_user,
        db=db,
    )


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
