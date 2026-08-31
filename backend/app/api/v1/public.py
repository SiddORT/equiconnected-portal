"""Unauthenticated, privacy-safe public telemetry endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rate_limit import (
    check_public_provider_rate_limit,
    check_public_visit_rate_limit,
    check_subscriber_rate_limit,
)
from app.db.session import get_db
from app.models.public_visit import PublicVisitDaily
from app.models.enums import ProviderType
from app.repositories.review_repository import ReviewRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.core.time_standards import system_today
from app.schemas.subscriber import (
    SubscriberRegistrationRequest,
    SubscriberRegistrationResponse,
)
from app.schemas.review import PublicProviderDiscovery, PublicProviderLocation
from app.services.subscriber_service import SubscriberService

router = APIRouter(prefix="/public", tags=["Public"])
_DB = Annotated[Session, Depends(get_db)]


def _public_location(provider, latitude: float, longitude: float) -> PublicProviderLocation:
    locations = sorted(
        (
            location
            for location in provider.locations
            if location.latitude is not None and location.longitude is not None
        ),
        key=lambda item: (not item.is_primary, item.created_at, item.id),
    )
    location = locations[0]
    return PublicProviderLocation(
        city=location.city,
        state_province=location.state_province,
        country=location.country,
        latitude=latitude,
        longitude=longitude,
    )


@router.get(
    "/providers",
    response_model=list[PublicProviderDiscovery],
    dependencies=[Depends(check_public_provider_rate_limit)],
)
def list_public_providers(
    db: _DB,
    provider_type: ProviderType | None = Query(None),
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(6, ge=1, le=12),
) -> list[PublicProviderDiscovery]:
    """Return safe, published provider summaries for the public homepage."""
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "location_pair_required",
                "message": "Latitude and longitude must be provided together.",
            },
        )

    rows = ReviewRepository(db).list_public_discoverable(
        provider_type=provider_type,
        latitude=latitude,
        longitude=longitude,
        limit=limit,
    )
    return [
        PublicProviderDiscovery(
            id=provider.id,
            provider_type=provider.provider_type,
            name=provider.name,
            specializations=[
                link.specialization.name
                for link in provider.provider_specializations
                if link.specialization.is_active
            ],
            location=_public_location(provider, float(provider_latitude), float(provider_longitude)),
            thumbnail_url=(
                next(
                    (
                        photo.storage_reference
                        for photo in sorted(
                            provider.photos,
                            key=lambda item: (
                                not item.is_thumbnail,
                                item.display_order,
                                item.created_at,
                                str(item.id),
                            ),
                        )
                    ),
                    None,
                )
            ),
            average_rating=float(average_rating) if average_rating is not None else None,
            review_count=int(review_count or 0),
            distance_km=round(float(distance), 2) if distance is not None else None,
        )
        for provider, average_rating, review_count, provider_latitude, provider_longitude, distance in rows
    ]


@router.post(
    "/visits",
    dependencies=[Depends(check_public_visit_rate_limit)],
    status_code=status.HTTP_204_NO_CONTENT,
)
def record_public_visit(db: _DB) -> Response:
    """Increment today's landing-page visit aggregate without retaining visitor data."""
    settings = SystemSettingsRepository(db).get_or_create()
    visit_date = system_today(settings.timezone)
    result = db.execute(
        update(PublicVisitDaily)
        .where(PublicVisitDaily.visit_date == visit_date)
        .values(visit_count=PublicVisitDaily.visit_count + 1)
    )

    if result.rowcount == 0:
        try:
            db.add(PublicVisitDaily(visit_date=visit_date, visit_count=1))
            db.commit()
        except IntegrityError:
            # Another request created today's aggregate first; increment it instead.
            db.rollback()
            db.execute(
                update(PublicVisitDaily)
                .where(PublicVisitDaily.visit_date == visit_date)
                .values(visit_count=PublicVisitDaily.visit_count + 1)
            )
            db.commit()
    else:
        db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/subscribers",
    response_model=SubscriberRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_subscriber_rate_limit)],
)
def register_subscriber(
    body: SubscriberRegistrationRequest,
    db: _DB,
) -> SubscriberRegistrationResponse:
    """Store launch interest and acknowledge it by email."""
    delivered = SubscriberService(db).register(
        email=str(body.email),
        registration_type=body.registration_type,
    )
    if not delivered:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "subscriber_confirmation_failed",
                "message": "We saved your registration, but could not send the confirmation email. Please try again later.",
            },
        )
    return SubscriberRegistrationResponse(
        message="Thanks for registering. EquiConnected will be in touch soon."
    )