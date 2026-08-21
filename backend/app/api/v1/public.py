"""Unauthenticated, privacy-safe public telemetry endpoints."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rate_limit import check_public_visit_rate_limit
from app.db.session import get_db
from app.models.public_visit import PublicVisitDaily

router = APIRouter(prefix="/public", tags=["Public"])
_DB = Annotated[Session, Depends(get_db)]


@router.post(
    "/visits",
    dependencies=[Depends(check_public_visit_rate_limit)],
    status_code=status.HTTP_204_NO_CONTENT,
)
def record_public_visit(db: _DB) -> Response:
    """Increment today's landing-page visit aggregate without retaining visitor data."""
    visit_date = datetime.now(timezone.utc).date()
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