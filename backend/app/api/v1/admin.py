"""
Admin-only endpoints.
GET /api/v1/admin/dashboard/stats
"""
from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role, CurrentUser
from app.db.session import get_db
from app.models.enums import (
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderProfileUpdateStatus,
    ProviderStatus,
    ProviderType,
)
from app.models.invitation import ProviderInvitation
from app.models.public_visit import PublicVisitDaily
from app.models.provider import Provider, ProviderLocation
from app.models.role import Role
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit_log import AuditActor, AuditChange, AuditLogListResponse, AuditLogResponse
from app.repositories.email_delivery_repository import EmailDeliveryRepository
from app.schemas.email_delivery_log import (
    EmailDeliveryLogListResponse,
    EmailDeliveryLogResponse,
)
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.user import PublicRegistrantResponse
from app.schemas.provider_registration import (
    ProviderApplicationDecisionRequest,
    ProviderApplicationResponse,
)
from app.schemas.provider import ProviderProfileUpdateAdminResponse
from app.repositories.provider_registration_repository import ProviderRegistrationRepository
from app.repositories.provider_profile_update_repository import ProviderProfileUpdateRepository
from app.repositories.provider_repository import ProviderRepository
from app.services.provider_registration_service import (
    ProviderApplicationDecisionError,
    ProviderApplicationNotFoundError,
    ProviderRegistrationService,
)
from app.services.provider_profile_update_service import (
    ProviderProfileUpdateDecisionError,
    ProviderProfileUpdateConflictError,
    ProviderProfileUpdateNotFoundError,
    ProviderProfileUpdateService,
    editable_profile_from_provider,
)
from app.repositories.user_repository import UserRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.core.time_standards import system_today

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
        "registrations": db.scalar(select(func.count()).select_from(public_user_ids)) or 0,
        "verified": db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.id.in_(public_user_id_select),
                User.email_verified_at.is_not(None),
            )
        )
        or 0,
        "unverified": db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.id.in_(public_user_id_select),
                User.email_verified_at.is_(None),
            )
        )
        or 0,
        "horse_owners": public_role_counts.get("horse_owner", 0),
        "stable_managers": public_role_counts.get("stable_manager", 0),
    }

    system_settings = SystemSettingsRepository(db).get_or_create()
    today = system_today(system_settings.timezone)
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


def _provider_application_response(application) -> ProviderApplicationResponse:
    user = application.user
    reviewer = application.reviewer
    return ProviderApplicationResponse(
        id=application.id,
        user_id=application.user_id,
        provider_id=application.provider_id,
        provider_type=application.provider_type,
        provider_name=application.provider_name,
        visit_stability=application.visit_stability,
        review_status=application.review_status,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        email=user.email,
        mobile_number=user.mobile_number,
        country=user.country,
        state_province=user.state_province,
        city=user.city,
        email_verified_at=user.email_verified_at,
        reviewed_by_user_id=application.reviewed_by_user_id,
        reviewed_by_name=reviewer.full_name if reviewer else None,
        reviewed_at=application.reviewed_at,
        rejection_reason=application.rejection_reason,
        created_at=application.created_at,
    )


def _provider_application_service(db: Session) -> ProviderRegistrationService:
    return ProviderRegistrationService(ProviderRegistrationRepository(db))


def _provider_profile_update_service(db: Session) -> ProviderProfileUpdateService:
    return ProviderProfileUpdateService(
        ProviderProfileUpdateRepository(db), ProviderRepository(db)
    )


def _provider_profile_update_response(
    profile_update, db: Session
) -> ProviderProfileUpdateAdminResponse:
    provider = ProviderRepository(db).get_by_id(profile_update.provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_profile_update_not_found", "message": "Provider profile update not found."},
        )
    return ProviderProfileUpdateAdminResponse(
        id=profile_update.id,
        provider_id=provider.id,
        provider_name=provider.name,
        provider_type=provider.provider_type,
        review_status=profile_update.review_status,
        proposed_profile=profile_update.proposed_profile,
        current_profile=editable_profile_from_provider(provider),
        submitted_at=profile_update.submitted_at,
        reviewed_by_user_id=profile_update.reviewed_by_user_id,
        reviewed_by_name=(
            profile_update.reviewer.full_name if profile_update.reviewer else None
        ),
        reviewed_at=profile_update.reviewed_at,
        rejection_reason=profile_update.rejection_reason,
        created_at=profile_update.created_at,
    )


@router.get(
    "/provider-profile-updates",
    response_model=PaginatedResponse[ProviderProfileUpdateAdminResponse],
    dependencies=[Depends(require_role("admin"))],
)
def list_provider_profile_updates(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(None, max_length=100),
    review_status: ProviderProfileUpdateStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[ProviderProfileUpdateAdminResponse]:
    profile_updates, total = _provider_profile_update_service(db).list(
        search=search,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=[_provider_profile_update_response(item, db) for item in profile_updates],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


@router.get(
    "/provider-profile-updates/{update_id}",
    response_model=ProviderProfileUpdateAdminResponse,
    dependencies=[Depends(require_role("admin"))],
)
def get_provider_profile_update(
    update_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> ProviderProfileUpdateAdminResponse:
    try:
        update = _provider_profile_update_service(db).get(update_id)
    except ProviderProfileUpdateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_profile_update_not_found", "message": "Provider profile update not found."},
        )
    return _provider_profile_update_response(update, db)


@router.post(
    "/provider-profile-updates/{update_id}/approve",
    response_model=ProviderProfileUpdateAdminResponse,
    dependencies=[Depends(require_role("admin"))],
)
def approve_provider_profile_update(
    update_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProviderProfileUpdateAdminResponse:
    try:
        update = _provider_profile_update_service(db).approve(update_id, current_user.id)
    except ProviderProfileUpdateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_profile_update_not_found", "message": "Provider profile update not found."},
        )
    except ProviderProfileUpdateDecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "provider_profile_update_conflict"
                    if isinstance(exc, ProviderProfileUpdateConflictError)
                    else "provider_profile_update_not_pending"
                ),
                "message": str(exc),
            },
        )
    return _provider_profile_update_response(update, db)


@router.post(
    "/provider-profile-updates/{update_id}/reject",
    response_model=ProviderProfileUpdateAdminResponse,
    dependencies=[Depends(require_role("admin"))],
)
def reject_provider_profile_update(
    update_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    body: ProviderApplicationDecisionRequest | None = None,
) -> ProviderProfileUpdateAdminResponse:
    try:
        update = _provider_profile_update_service(db).reject(
            update_id,
            current_user.id,
            body.rejection_reason if body else None,
        )
    except ProviderProfileUpdateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_profile_update_not_found", "message": "Provider profile update not found."},
        )
    except ProviderProfileUpdateDecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "provider_profile_update_not_pending", "message": str(exc)},
        )
    return _provider_profile_update_response(update, db)


@router.get(
    "/provider-applications",
    response_model=PaginatedResponse[ProviderApplicationResponse],
    dependencies=[Depends(require_role("admin"))],
)
def list_provider_applications(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(None, max_length=100),
    provider_type: ProviderType | None = Query(None),
    email_verified: bool | None = Query(None),
    review_status: ProviderApplicationStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[ProviderApplicationResponse]:
    applications, total = _provider_application_service(db).list(
        search=search,
        provider_type=provider_type,
        email_verified=email_verified,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=[_provider_application_response(application) for application in applications],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


@router.get(
    "/provider-applications/{application_id}",
    response_model=ProviderApplicationResponse,
    dependencies=[Depends(require_role("admin"))],
)
def get_provider_application(
    application_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ProviderApplicationResponse:
    try:
        application = _provider_application_service(db).get(application_id)
    except ProviderApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_application_not_found", "message": "Provider application not found."},
        )
    return _provider_application_response(application)


@router.post(
    "/provider-applications/{application_id}/approve",
    response_model=ProviderApplicationResponse,
    dependencies=[Depends(require_role("admin"))],
)
def approve_provider_application(
    application_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProviderApplicationResponse:
    try:
        application = _provider_application_service(db).approve(application_id, current_user.id)
    except ProviderApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_application_not_found", "message": "Provider application not found."},
        )
    except ProviderApplicationDecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "provider_application_not_pending", "message": str(exc)},
        )
    return _provider_application_response(application)


@router.post(
    "/provider-applications/{application_id}/reject",
    response_model=ProviderApplicationResponse,
    dependencies=[Depends(require_role("admin"))],
)
def reject_provider_application(
    application_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    body: ProviderApplicationDecisionRequest | None = None,
) -> ProviderApplicationResponse:
    try:
        application = _provider_application_service(db).reject(
            application_id,
            current_user.id,
            body.rejection_reason if body else None,
        )
    except ProviderApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_application_not_found", "message": "Provider application not found."},
        )
    except ProviderApplicationDecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "provider_application_not_pending", "message": str(exc)},
        )
    return _provider_application_response(application)


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
        date_from=date_from,
        date_to=date_to,
        timezone_name=SystemSettingsRepository(db).get_or_create().timezone,
        page=page,
        page_size=page_size,
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


def _email_log_filter_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": code, "message": message},
    )


@router.get(
    "/email-logs",
    response_model=EmailDeliveryLogListResponse,
    dependencies=[Depends(require_role("admin"))],
)
def list_email_logs(
    db: Annotated[Session, Depends(get_db)],
    filter_mode: str | None = Query(None),
    filter_date: date | None = Query(None, alias="date"),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=9999),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> EmailDeliveryLogListResponse:
    """Newest-first transactional email handoff history for administrators."""
    valid_modes = {"day", "month", "year", "range"}
    if filter_mode is not None and filter_mode not in valid_modes:
        raise _email_log_filter_error(
            "invalid_email_log_filter_mode",
            "Filter mode must be day, month, year, or range.",
        )
    if filter_mode == "day" and filter_date is None:
        raise _email_log_filter_error(
            "email_log_date_required", "A date is required for the day filter."
        )
    if filter_mode == "month" and (month is None or year is None):
        raise _email_log_filter_error(
            "email_log_month_required",
            "A month and year are required for the month filter.",
        )
    if filter_mode == "year" and year is None:
        raise _email_log_filter_error(
            "email_log_year_required", "A year is required for the year filter."
        )
    if filter_mode == "range":
        if date_from is None or date_to is None:
            raise _email_log_filter_error(
                "email_log_range_required",
                "Start and end dates are required for the custom range.",
            )
        if date_from > date_to:
            raise _email_log_filter_error(
                "invalid_date_range", "Start date must be on or before end date."
            )

    logs, total = EmailDeliveryRepository(db).list(
        filter_mode=filter_mode,
        filter_date=filter_date,
        filter_month=month,
        filter_year=year,
        date_from=date_from,
        date_to=date_to,
        timezone_name=SystemSettingsRepository(db).get_or_create().timezone,
        page=page,
        page_size=page_size,
    )
    return EmailDeliveryLogListResponse(
        data=[
            EmailDeliveryLogResponse(
                id=entry.id,
                recipient_email=entry.recipient_email,
                purpose=entry.purpose,
                status=entry.status,
                failure_message=entry.failure_message,
                created_at=entry.created_at,
            )
            for entry in logs
        ],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )
