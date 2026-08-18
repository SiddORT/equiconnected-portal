"""
Admin-only endpoints.
GET /api/v1/admin/dashboard/stats
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role, CurrentUser
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/dashboard/stats",
    dependencies=[Depends(require_role("admin"))],
)
def dashboard_stats(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Basic dashboard statistics — extends as more modules are added."""
    total_users = db.scalar(select(func.count()).select_from(User))
    recent_events = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)
    ).all()

    return {
        "total_users": total_users,
        "recent_audit_events": [
            {
                "id": str(e.id),
                "action": e.action,
                "user_id": str(e.user_id) if e.user_id else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in recent_events
        ],
    }
