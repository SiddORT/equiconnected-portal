"""Administrator review moderation endpoints."""
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_role
from app.db.session import get_db
from app.repositories.audit_repository import context_from_request
from app.repositories.review_repository import ReviewRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.models.enums import ProviderReviewStatus
from app.schemas.review import (
    AdminReviewDetail,
    AdminReviewListItem,
    AdminReviewStatusUpdate,
    CommentVisibilityUpdate,
    ProviderReviewActionResponse,
)
from app.services.review_service import (
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewService,
    ReviewStateError,
)

router = APIRouter(
    prefix="/admin/reviews",
    tags=["Review Moderation"],
    dependencies=[Depends(require_role("admin"))],
)
_DB = Annotated[Session, Depends(get_db)]


def _svc(db: _DB) -> ReviewService:
    return ReviewService(ReviewRepository(db))


_Svc = Annotated[ReviewService, Depends(_svc)]


def _response(review, provider, reviewer) -> AdminReviewListItem:
    return AdminReviewListItem(
        id=review.id,
        provider_id=provider.id,
        provider_name=provider.name,
        reviewer_id=reviewer.id,
        reviewer_name=reviewer.full_name,
        reviewer_email=reviewer.email,
        rating=review.rating,
        comment=review.comment,
        comment_visible=review.comment_visible,
        status=review.status,
        member_note=review.member_note,
        internal_note=review.internal_note,
        version=review.version,
        deleted_at=review.deleted_at,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.get("", response_model=PaginatedResponse[AdminReviewListItem])
def list_reviews(
    svc: _Svc,
    current_user: CurrentUser,
    provider_id: UUID | None = Query(None),
    comment_visible: bool | None = Query(None),
    review_status: ProviderReviewStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[AdminReviewListItem]:
    items, total = svc.list_admin_reviews(
        provider_id=provider_id,
        comment_visible=comment_visible,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=[_response(review, provider, reviewer) for review, provider, reviewer in items],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


def _history_response(action) -> ProviderReviewActionResponse:
    return ProviderReviewActionResponse(
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


@router.get("/{review_id}", response_model=AdminReviewDetail)
def get_review_detail(
    review_id: UUID, svc: _Svc, current_user: CurrentUser
) -> AdminReviewDetail:
    review = svc._repo.get_review(review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "review_not_found", "message": "Review not found."},
        )
    return AdminReviewDetail(
        **_response(review, review.provider, review.member).model_dump(),
        history=[
            _history_response(action)
            for action in svc.review_history(review_id)
        ],
    )


@router.patch("/{review_id}/comment-visibility", response_model=AdminReviewListItem)
def set_comment_visibility(
    review_id: UUID,
    body: CommentVisibilityUpdate,
    request: Request,
    current_user: CurrentUser,
    svc: _Svc,
) -> AdminReviewListItem:
    try:
        review = svc.set_comment_visibility(
            review_id,
            comment_visible=body.comment_visible,
            expected_version=body.expected_version,
            audit_context=context_from_request(request, current_user.id),
        )
    except ReviewNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "review_not_found", "message": "Review not found."},
        )
    except ReviewConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "review_conflict",
            "message": str(error),
        })
    except ReviewStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "review_state_conflict",
            "message": str(error),
        })
    return _response(review, review.provider, review.member)


@router.patch("/{review_id}/status", response_model=AdminReviewListItem)
def update_review_status(
    review_id: UUID,
    body: AdminReviewStatusUpdate,
    request: Request,
    current_user: CurrentUser,
    svc: _Svc,
) -> AdminReviewListItem:
    try:
        review = svc.update_admin_review(
            review_id,
            status=body.status,
            expected_version=body.expected_version,
            member_note=body.member_note,
            internal_note=body.internal_note,
            update_member_note="member_note" in body.model_fields_set,
            update_internal_note="internal_note" in body.model_fields_set,
            audit_context=context_from_request(request, current_user.id),
        )
    except ReviewNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "review_not_found", "message": "Review not found."},
        )
    except ReviewConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "review_conflict",
            "message": str(error),
        })
    except ReviewStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "review_state_conflict",
            "message": str(error),
        })
    return _response(review, review.provider, review.member)