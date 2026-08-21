"""Unauthenticated, privacy-safe public telemetry endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rate_limit import check_public_visit_rate_limit, check_subscriber_rate_limit
from app.db.session import get_db
from app.models.public_visit import PublicVisitDaily
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.core.time_standards import system_today
from app.schemas.subscriber import (
    SubscriberRegistrationRequest,
    SubscriberRegistrationResponse,
)
from app.services.subscriber_service import SubscriberService

router = APIRouter(prefix="/public", tags=["Public"])
_DB = Annotated[Session, Depends(get_db)]


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