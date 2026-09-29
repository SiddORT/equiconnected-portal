"""Verified-member provider directory and one-review-per-provider endpoints."""
from __future__ import annotations

from math import ceil
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.models.enums import ProviderType, VisitStability
from app.models.provider_favorite import ProviderFavorite
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User
from app.repositories.audit_repository import context_from_request
from app.repositories.review_repository import ReviewRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.review import (
    DirectoryLocation,
    MemberProviderDetail,
    MemberProviderListItem,
    MemberReviewResponse,
    MemberReviewUpsert,
    PublicProviderReview,
)
from app.services.review_service import DiscoverableProviderNotFoundError, ReviewService

router = APIRouter(prefix="/member/providers", tags=["Member Provider Directory"])
_DB = Annotated[Session, Depends(get_db)]


def require_verified_member(user: CurrentUser) -> User:
    role_names = {user.role.name, *(assignment.role.name for assignment in user.role_assignments)}
    if user.email_verified_at is None or not role_names.intersection(PUBLIC_ACCOUNT_ROLE_NAMES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "member_directory_forbidden",
                "message": "This directory is available to verified members only.",
            },
        )
    return user


MemberUser = Annotated[User, Depends(require_verified_member)]


def _svc(db: _DB) -> ReviewService:
    return ReviewService(ReviewRepository(db))


_Svc = Annotated[ReviewService, Depends(_svc)]


def _location(provider) -> DirectoryLocation | None:
    locations = sorted(provider.locations, key=lambda item: (not item.is_primary, item.created_at, item.id))
    if not locations:
        return None
    primary = locations[0]
    return DirectoryLocation(
        city=primary.city,
        state_province=primary.state_province,
        country=primary.country,
    )


def _contact(provider, field: str) -> str | None:
    entries = getattr(provider, f"{field}s")
    value = next((getattr(item, field) for item in entries if item.is_primary), None)
    return value or (getattr(entries[0], field) if entries else getattr(provider, field))


def _thumbnail(provider):
    if not provider.photos:
        return None
    return next(
        (photo for photo in provider.photos if photo.is_thumbnail),
        min(
            provider.photos,
            key=lambda photo: (photo.display_order, photo.created_at, str(photo.id)),
        ),
    )


def _item(provider, average_rating, review_count, distance=None, is_saved=False) -> MemberProviderListItem:
    thumbnail = _thumbnail(provider)
    return MemberProviderListItem(
        id=provider.id,
        is_saved=is_saved,
        provider_type=provider.provider_type,
        name=provider.name,
        description=provider.description,
        thumbnail_url=thumbnail.storage_reference if thumbnail else None,
        thumbnail_alt_text=thumbnail.alt_text if thumbnail else None,
        website=provider.website,
        email=_contact(provider, "email"),
        phone=_contact(provider, "phone"),
        visit_stability=provider.visit_stability,
        location=_location(provider),
        average_rating=float(average_rating) if average_rating is not None else None,
        review_count=int(review_count or 0),
        distance_km=round(float(distance), 2) if distance is not None else None,
        specializations=sorted(
            link.specialization.name for link in provider.provider_specializations
        ),
        emergency_services_available=provider.emergency_services_available is True,
    )


def _review_response(review) -> MemberReviewResponse:
    return MemberReviewResponse(
        id=review.id,
        rating=review.rating,
        comment=review.comment if review.comment_visible else "",
        comment_visible=review.comment_visible,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.get("/filters")
def member_provider_filters(user: MemberUser, svc: _Svc) -> dict:
    return svc.directory_facets()


def _saved_ids(db: Session, member_id: UUID, provider_ids: list[UUID]) -> set[UUID]:
    if not provider_ids:
        return set()
    return set(db.scalars(select(ProviderFavorite.provider_id).where(
        ProviderFavorite.member_id == member_id,
        ProviderFavorite.provider_id.in_(provider_ids),
    )).all())


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "provider_not_found", "message": "Provider not found."},
    )


@router.get("", response_model=PaginatedResponse[MemberProviderListItem])
def list_member_providers(
    user: MemberUser,
    svc: _Svc,
    db: _DB,
    saved_only: bool = Query(False),
    provider_type: ProviderType | None = Query(None),
    minimum_rating: float | None = Query(None, ge=1, le=5),
    visit_stability: VisitStability | None = Query(None),
    specialization_id: UUID | None = Query(None),
    region: str | None = Query(None, min_length=1, max_length=200),
    emergency_only: bool = Query(False),
    sort: str = Query("relevance", pattern="^(relevance|name)$"),
    closest_first: bool = Query(False),
    within_working_radius: bool = Query(False),
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
) -> PaginatedResponse[MemberProviderListItem]:
    if (closest_first or within_working_radius) and (latitude is None or longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "location_required",
                "message": "Allow location access to sort providers by distance.",
            },
        )
    if not closest_first:
        # The radius filter still needs coordinates; otherwise discard them only
        # when neither distance feature is enabled.
        if not within_working_radius:
            latitude = longitude = None
    rows, total = svc.list_discoverable(
        provider_type=provider_type,
        minimum_rating=minimum_rating,
        page=page,
        page_size=page_size,
        latitude=latitude,
        longitude=longitude,
        closest_first=closest_first,
        within_working_radius=within_working_radius,
        visit_stability=visit_stability,
        specialization_id=specialization_id,
        region=region,
        emergency_only=emergency_only,
        sort=sort,
        saved_only_member_id=user.id if saved_only else None,
    )
    saved_ids = _saved_ids(db, user.id, [row[0].id for row in rows])
    return PaginatedResponse(
        data=[
            _item(provider, average_rating, review_count, distance if closest_first else None, provider.id in saved_ids)
            for provider, average_rating, review_count, *rest in rows
            for distance in ([rest[0]] if rest else [None])
        ],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


@router.put("/{provider_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def save_provider(provider_id: UUID, user: MemberUser, svc: _Svc, db: _DB) -> None:
    try:
        svc.get_discoverable(provider_id)
    except DiscoverableProviderNotFoundError:
        raise _not_found()
    db.execute(insert(ProviderFavorite).values(
        id=uuid4(), member_id=user.id, provider_id=provider_id,
        created_at=datetime.now(timezone.utc),
    ).on_conflict_do_nothing(constraint="uq_provider_favorites_member_provider"))
    db.commit()


@router.delete("/{provider_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_provider(provider_id: UUID, user: MemberUser, db: _DB) -> None:
    db.execute(delete(ProviderFavorite).where(
        ProviderFavorite.provider_id == provider_id, ProviderFavorite.member_id == user.id,
    ))
    db.commit()


@router.get("/{provider_id}", response_model=MemberProviderDetail)
def get_member_provider(provider_id: UUID, user: MemberUser, svc: _Svc, db: _DB) -> MemberProviderDetail:
    try:
        provider = svc.get_discoverable(provider_id)
    except DiscoverableProviderNotFoundError:
        raise _not_found()
    average_rating, review_count = svc.totals(provider_id)
    visible_reviews = [
        PublicProviderReview(
            id=review.id,
            rating=review.rating,
            comment=review.comment,
            reviewer_name=reviewer.full_name,
            created_at=review.created_at,
        )
        for review, reviewer in svc.visible_reviews(provider_id)
    ]
    return MemberProviderDetail(
        **_item(provider, average_rating, review_count, is_saved=provider_id in _saved_ids(db, user.id, [provider_id])).model_dump(),
        visible_reviews=visible_reviews,
        own_review=(
            _review_response(own_review)
            if (own_review := svc.member_review(provider_id, user.id)) is not None
            else None
        ),
    )


@router.put("/{provider_id}/review", response_model=MemberReviewResponse)
def save_member_provider_review(
    provider_id: UUID,
    body: MemberReviewUpsert,
    request: Request,
    user: MemberUser,
    svc: _Svc,
) -> MemberReviewResponse:
    try:
        review = svc.save_member_review(
            provider_id,
            user.id,
            rating=body.rating,
            comment=body.comment,
            audit_context=context_from_request(request, user.id),
        )
    except DiscoverableProviderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_not_found", "message": "Provider not found."},
        )
    return _review_response(review)