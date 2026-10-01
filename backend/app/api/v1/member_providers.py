"""Verified-member provider directory and one-review-per-provider endpoints."""
from __future__ import annotations

from math import ceil
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.core.rate_limit import check_analytics_traffic_rate_limit
from app.core.time_standards import system_today
from app.models.enums import ProviderType, VisitStability
from app.models.provider_favorite import ProviderFavorite
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User
from app.repositories.audit_repository import context_from_request
from app.repositories.review_repository import ReviewRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.schemas.analytics_traffic import MemberTrafficViewRequest
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.provider import selected_provider_photo
from app.schemas.review import (
    DirectoryLocation,
    MemberProviderDetail,
    MemberProviderListItem,
    MemberReviewResponse,
    MemberReviewItem,
    MemberReviewUpsert,
    PublicProviderReview,
)
from app.services.review_service import (
    DiscoverableProviderNotFoundError,
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewService,
    ReviewStateError,
)
from app.services.analytics_traffic_service import record_successful_view

router = APIRouter(prefix="/member/providers", tags=["Member Provider Directory"])
member_reviews_router = APIRouter(prefix="/member/reviews", tags=["Member Reviews"])
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


def _profile_locations(provider):
    locations = sorted(
        provider.locations,
        key=lambda item: (not item.is_primary, item.created_at, item.id),
    )
    return [
        {
            "city": location.city,
            "state_province": location.state_province,
            "country": location.country,
            "is_primary": location.is_primary,
        }
        for location in locations
    ]


def _member_photos(provider):
    return [
        {
            "url": photo.storage_reference,
            "alt_text": photo.alt_text,
            "caption": photo.caption,
            "display_order": photo.display_order,
            "is_thumbnail": photo.is_thumbnail,
        }
        for photo in sorted(
            provider.photos,
            key=lambda item: (item.display_order, item.created_at, item.id),
        )
    ]


def _member_visits(provider):
    visits = sorted(
        provider.doctor_visits,
        key=lambda item: (item.start_date, item.end_date, item.id),
    )
    return [
        {
            "start_date": visit.start_date,
            "end_date": visit.end_date,
            "location": {
                "city": visit.location.get("city", ""),
                "state_province": visit.location.get("state_province"),
                "country": visit.location.get("country"),
            },
        }
        for visit in visits
    ]


def _contact(provider, field: str) -> str | None:
    entries = getattr(provider, f"{field}s")
    value = next((getattr(item, field) for item in entries if item.is_primary), None)
    return value or (getattr(entries[0], field) if entries else getattr(provider, field))


def _thumbnail(provider):
    return selected_provider_photo(provider.photos)


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
        comment=review.comment,
        comment_visible=review.comment_visible,
        status=review.status,
        member_note=review.member_note,
        version=review.version,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def _member_review_item(review, provider) -> MemberReviewItem:
    return MemberReviewItem(
        **_review_response(review).model_dump(),
        provider_id=provider.id,
        provider_name=provider.name,
    )


@router.get("/filters")
def member_provider_filters(user: MemberUser, svc: _Svc) -> dict:
    return svc.directory_facets()


@router.post(
    "/traffic-view",
    status_code=204,
    dependencies=[Depends(check_analytics_traffic_rate_limit)],
)
def record_member_traffic_view(
    body: MemberTrafficViewRequest,
    user: MemberUser,
    svc: _Svc,
    db: _DB,
) -> Response:
    """Record only successful authorized directory/profile route views."""
    if body.category == "provider_profile":
        if body.provider_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "provider_id_required",
                    "message": "A provider identifier is required.",
                },
            )
        try:
            svc.get_discoverable(body.provider_id)
        except DiscoverableProviderNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "provider_not_found",
                    "message": "Provider not found.",
                },
            ) from None

    try:
        timezone_name = SystemSettingsRepository(db).get_or_create().timezone
        record_successful_view(
            db,
            visit_date=system_today(timezone_name),
            category=body.category,
            navigation_key=body.navigation_key,
            first_eligible_view_today=body.first_eligible_view_today,
            provider_id=body.provider_id,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "traffic_tracking_unavailable",
                "message": "Traffic tracking is temporarily unavailable.",
            },
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    name: str | None = Query(None, max_length=200),
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
        name=name,
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
        provider = svc.get_discoverable(provider_id, include_profile=True)
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
        biography=provider.doctor_profile.biography if provider.doctor_profile else None,
        professional_title=(
            provider.professional_title
            if provider.professional_title is not None
            else provider.doctor_profile.professional_title if provider.doctor_profile else None
        ),
        experience_description=(
            provider.doctor_profile.experience_description
            if provider.doctor_profile
            else None
        ),
        years_experience=(
            provider.years_experience
            if provider.years_experience is not None
            else provider.doctor_profile.years_experience if provider.doctor_profile else None
        ),
        qualifications=[
            {
                "title": qualification.title,
                "institution": qualification.institution,
                "year_obtained": qualification.year_obtained,
                "description": qualification.description,
                "display_order": qualification.display_order,
            }
            for qualification in sorted(
                provider.qualifications,
                key=lambda item: (item.display_order, item.created_at, item.id),
            )
        ],
        photos=_member_photos(provider),
        languages=[
            {"name": link.language.name, "code": link.language.code}
            for link in sorted(
                provider.provider_languages,
                key=lambda item: (item.language.name.casefold(), item.language.code),
            )
        ],
        locations=_profile_locations(provider),
        maximum_working_radius_km=(
            float(provider.maximum_working_radius_km)
            if provider.maximum_working_radius_km is not None
            else None
        ),
        clinic_hospital_visit=provider.clinic_hospital_visit,
        doctor_availability=provider.doctor_availability,
        doctor_visits=_member_visits(provider),
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
            expected_version=body.expected_version,
            audit_context=context_from_request(request, user.id, actor_type="member"),
        )
    except DiscoverableProviderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_not_found", "message": "Provider not found."},
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
    return _review_response(review)


@member_reviews_router.get("", response_model=PaginatedResponse[MemberReviewItem])
def list_own_reviews(
    svc: _Svc,
    user: MemberUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> PaginatedResponse[MemberReviewItem]:
    rows, total = svc.list_member_reviews(user.id, page=page, page_size=page_size)
    return PaginatedResponse(
        data=[_member_review_item(review, provider) for review, provider in rows],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, ceil(total / page_size)),
        ),
    )


@member_reviews_router.get("/counts", response_model=dict[str, int])
def own_review_counts(svc: _Svc, user: MemberUser) -> dict[str, int]:
    return svc.member_review_counts(user.id)


@member_reviews_router.get("/{review_id}", response_model=MemberReviewItem)
def get_own_review(review_id: UUID, svc: _Svc, user: MemberUser) -> MemberReviewItem:
    try:
        review = svc.get_member_review(review_id, user.id)
    except ReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "code": "review_not_found",
            "message": "Review not found.",
        })
    return _member_review_item(review, review.provider)


@member_reviews_router.put("/{review_id}", response_model=MemberReviewResponse)
def update_own_review(
    review_id: UUID,
    body: MemberReviewUpsert,
    request: Request,
    user: MemberUser,
    svc: _Svc,
) -> MemberReviewResponse:
    if body.expected_version is None:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail={
            "code": "review_version_required",
            "message": "Reload your review before editing it.",
        })
    try:
        review = svc.edit_member_review(
            review_id,
            user.id,
            rating=body.rating,
            comment=body.comment,
            expected_version=body.expected_version,
            audit_context=context_from_request(request, user.id, actor_type="member"),
        )
    except ReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "code": "review_not_found",
            "message": "Review not found.",
        })
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
    return _review_response(review)


@member_reviews_router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_own_review(
    review_id: UUID,
    request: Request,
    user: MemberUser,
    svc: _Svc,
    expected_version: int = Query(..., ge=1),
) -> None:
    try:
        svc.delete_member_review(
            review_id,
            user.id,
            expected_version=expected_version,
            audit_context=context_from_request(request, user.id, actor_type="member"),
        )
    except ReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "code": "review_not_found",
            "message": "Review not found.",
        })
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