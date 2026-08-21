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
from app.schemas.review import AdminReviewListItem, CommentVisibilityUpdate
from app.services.review_service import ReviewNotFoundError, ReviewService

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
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.get("", response_model=PaginatedResponse[AdminReviewListItem])
def list_reviews(
    svc: _Svc,
    current_user: CurrentUser,
    comment_visible: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[AdminReviewListItem]:
    items, total = svc.list_admin_reviews(
        comment_visible=comment_visible, page=page, page_size=page_size
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
            audit_context=context_from_request(request, current_user.id),
        )
    except ReviewNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "review_not_found", "message": "Review not found."},
        )
    return _response(review, review.provider, review.member)