"""Private member platform feedback and browsing history APIs."""
from math import ceil
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AdminUser, CurrentUser
from app.db.session import get_db
from app.models.enums import MemberFeedbackCategory, MemberFeedbackStatus
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User
from app.repositories.audit_repository import context_from_request
from app.repositories.member_feedback_repository import MemberFeedbackRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.member_feedback import (
    AdminFeedbackActionItem,
    AdminFeedbackDetail,
    AdminFeedbackItem,
    AdminFeedbackUpdate,
    FeedbackCounts,
    MemberFeedbackActionItem,
    MemberFeedbackCreate,
    MemberFeedbackDetail,
    MemberFeedbackItem,
    MemberFeedbackUpdate,
    MemberHistoryCreate,
    MemberHistoryItem,
)
from app.services.member_feedback_service import (
    FeedbackConflictError,
    FeedbackNotFoundError,
    FeedbackStaleVersionError,
    HistoryProviderNotFoundError,
    MemberFeedbackService,
)

member_router = APIRouter(prefix="/member", tags=["Member Feedback and History"])
admin_router = APIRouter(
    prefix="/admin/feedback",
    tags=["Platform Feedback"],
)
_DB = Annotated[Session, Depends(get_db)]


def _service(db: _DB) -> MemberFeedbackService:
    return MemberFeedbackService(MemberFeedbackRepository(db))


_Service = Annotated[MemberFeedbackService, Depends(_service)]


def _verified_member(user: CurrentUser) -> User:
    roles = {user.role.name, *(assignment.role.name for assignment in user.role_assignments)}
    if user.email_verified_at is None or not roles.intersection(PUBLIC_ACCOUNT_ROLE_NAMES):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "member_feedback_forbidden",
                "message": "This member service is available to verified members only.",
            },
        )
    return user


MemberUser = Annotated[User, Depends(_verified_member)]


def _item(feedback) -> MemberFeedbackItem:
    return MemberFeedbackItem(
        id=feedback.id,
        category=feedback.category,
        subject=feedback.subject,
        rating=feedback.rating,
        message=feedback.message,
        status=feedback.status,
        member_response=feedback.member_response,
        submitted_at=feedback.submitted_at,
        updated_at=feedback.updated_at,
        version=feedback.version,
        withdrawn_at=feedback.withdrawn_at,
    )


def _admin_item(feedback) -> AdminFeedbackItem:
    return AdminFeedbackItem(
        **_item(feedback).model_dump(),
        member_id=feedback.member_id,
        submitter_name=feedback.submitter_name,
        submitter_email=feedback.submitter_email,
        internal_note=feedback.internal_note,
    )


def _history_item(item, svc: MemberFeedbackService) -> MemberHistoryItem:
    provider_event = item.event_type == "provider"
    return MemberHistoryItem(
        id=item.id,
        event_key=item.event_key,
        type=item.event_type,
        provider_id=item.provider_id,
        provider_name=item.provider_name,
        provider_available=svc.provider_available(item.provider_id) if provider_event else None,
        filters=item.filters,
        occurred_at=item.occurred_at,
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "feedback_not_found", "message": "Feedback not found."},
    )


def _conflict(exc: FeedbackConflictError) -> HTTPException:
    stale = isinstance(exc, FeedbackStaleVersionError)
    return HTTPException(
        status_code=409,
        detail={
            "code": "stale_version" if stale else "feedback_state_conflict",
            "message": (
                "This feedback changed while you were editing it. Reload the latest version and try again."
                if stale
                else str(exc)
            ),
        },
    )


@member_router.get("/feedback", response_model=PaginatedResponse[MemberFeedbackItem])
def list_member_feedback(
    user: MemberUser,
    svc: _Service,
    feedback_status: MemberFeedbackStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    items, total = svc.list_member(
        member_id=user.id, status=feedback_status, page=page, page_size=page_size
    )
    return PaginatedResponse(
        data=[_item(item) for item in items],
        meta=PaginationMeta(
            page=page, page_size=page_size, total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


@member_router.get("/feedback/counts", response_model=FeedbackCounts)
def member_feedback_counts(user: MemberUser, svc: _Service):
    return svc.member_counts(user.id)


@member_router.post("/feedback", response_model=MemberFeedbackItem)
def submit_member_feedback(
    body: MemberFeedbackCreate,
    request: Request,
    user: MemberUser,
    svc: _Service,
):
    feedback = svc.create(
        user,
        category=body.category,
        subject=body.subject or None,
        rating=body.rating,
        message=body.message,
        idempotency_key=body.idempotency_key,
        audit_context=context_from_request(request, user.id, actor_type="member"),
    )
    return _item(feedback)


@member_router.get("/feedback/{feedback_id}", response_model=MemberFeedbackDetail)
def get_member_feedback(
    feedback_id: UUID, user: MemberUser, svc: _Service
) -> MemberFeedbackDetail:
    try:
        feedback = svc.member_detail(feedback_id, user.id)
    except FeedbackNotFoundError:
        raise _not_found()
    return MemberFeedbackDetail(
        **_item(feedback).model_dump(),
        history=[
            MemberFeedbackActionItem(
                action=action.action,
                from_status=action.from_status,
                to_status=action.to_status,
                version=action.version,
                created_at=action.created_at,
                actor_name=action.actor_name,
                member_response=action.content_snapshot.get("member_response"),
            )
            for action in feedback.actions
        ],
    )


@member_router.patch("/feedback/{feedback_id}", response_model=MemberFeedbackItem)
def update_member_feedback(
    feedback_id: UUID,
    body: MemberFeedbackUpdate,
    request: Request,
    user: MemberUser,
    svc: _Service,
):
    try:
        feedback = svc.update_member(
            feedback_id,
            user,
            expected_version=body.expected_version,
            changes=body.model_dump(exclude_unset=True, exclude={"expected_version"}),
            audit_context=context_from_request(request, user.id, actor_type="member"),
        )
    except FeedbackNotFoundError:
        raise _not_found()
    except FeedbackConflictError as exc:
        raise _conflict(exc)
    return _item(feedback)


@member_router.delete("/feedback/{feedback_id}", response_model=MemberFeedbackItem)
def withdraw_member_feedback(
    feedback_id: UUID,
    request: Request,
    user: MemberUser,
    svc: _Service,
    expected_version: int = Query(..., ge=1),
):
    try:
        feedback = svc.withdraw(
            feedback_id,
            user,
            expected_version=expected_version,
            audit_context=context_from_request(request, user.id, actor_type="member"),
        )
    except FeedbackNotFoundError:
        raise _not_found()
    except FeedbackConflictError as exc:
        raise _conflict(exc)
    return _item(feedback)


@member_router.post("/history", response_model=MemberHistoryItem)
def record_member_history(
    body: MemberHistoryCreate, user: MemberUser, svc: _Service
):
    filters = body.filters.model_dump(mode="json", exclude_none=True) if body.filters else None
    try:
        item = svc.append_history(
            user.id,
            event_key=body.event_key,
            event_type=body.type,
            provider_id=body.provider_id,
            filters=filters,
        )
    except HistoryProviderNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "provider_not_found",
                "message": "Only providers currently available in the directory can be added to history.",
            },
        )
    return _history_item(item, svc)


@member_router.get("/history", response_model=PaginatedResponse[MemberHistoryItem])
def list_member_history(
    user: MemberUser,
    svc: _Service,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    items, total = svc.list_history(member_id=user.id, page=page, page_size=page_size)
    return PaginatedResponse(
        data=[_history_item(item, svc) for item in items],
        meta=PaginationMeta(
            page=page, page_size=page_size, total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


@member_router.get("/history/recent", response_model=list[MemberHistoryItem])
def recent_member_history(
    user: MemberUser,
    svc: _Service,
    limit: int = Query(5, ge=1, le=10),
):
    return [
        _history_item(item, svc)
        for item in svc.recent_history(member_id=user.id, limit=limit)
    ]


@admin_router.get("", response_model=PaginatedResponse[AdminFeedbackItem])
def list_admin_feedback(
    user: AdminUser,
    svc: _Service,
    feedback_status: MemberFeedbackStatus | Literal["withdrawn"] | None = Query(
        None, alias="status"
    ),
    category: MemberFeedbackCategory | None = Query(None),
    q: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = svc.list_admin(
        status=feedback_status,
        category=category,
        query=q,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=[_admin_item(item) for item in items],
        meta=PaginationMeta(
            page=page, page_size=page_size, total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


@admin_router.get("/{feedback_id}", response_model=AdminFeedbackDetail)
def get_admin_feedback(feedback_id: UUID, user: AdminUser, svc: _Service):
    try:
        feedback = svc.admin_detail(feedback_id)
    except FeedbackNotFoundError:
        raise _not_found()
    return AdminFeedbackDetail(
        **_admin_item(feedback).model_dump(),
        history=[
            AdminFeedbackActionItem(
                id=action.id,
                actor_id=action.actor_id,
                actor_name=action.actor_name,
                actor_email=action.actor_email,
                actor_type=action.actor_type,
                action=action.action,
                from_status=action.from_status,
                to_status=action.to_status,
                version=action.version,
                content_snapshot=action.content_snapshot,
                created_at=action.created_at,
            )
            for action in feedback.actions
        ],
    )


@admin_router.patch("/{feedback_id}", response_model=AdminFeedbackDetail)
def update_admin_feedback(
    feedback_id: UUID,
    body: AdminFeedbackUpdate,
    request: Request,
    user: AdminUser,
    svc: _Service,
):
    try:
        feedback = svc.update_admin(
            feedback_id,
            user,
            expected_version=body.expected_version,
            changes=body.model_dump(exclude_unset=True, exclude={"expected_version"}),
            audit_context=context_from_request(request, user.id),
        )
        feedback = svc.admin_detail(feedback.id)
    except FeedbackNotFoundError:
        raise _not_found()
    except FeedbackConflictError as exc:
        raise _conflict(exc)
    return get_admin_feedback(feedback.id, user, svc)