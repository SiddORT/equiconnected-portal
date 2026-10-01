"""Durable, idempotent delivery for approved provider portal credentials."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.models.user import User
from app.repositories.email_delivery_repository import (
    EmailDeliveryRepository,
    safe_failure_message,
)
from app.services.email_service import EmailService


def send_provider_approval_email(
    db: Session, user: User, email_service: EmailService
) -> bool:
    """Send once after commit; preserve attempt/outcome if SMTP is unavailable."""
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        db.rollback()
        return False
    if (
        not user.is_active
        or user.provider_portal_setup_pending
        or user.provider_portal_approval_pending
        or user.role.name != "provider"
    ):
        db.rollback()
        return False
    if user.provider_portal_approval_email_sent_at is not None:
        db.rollback()
        return True

    now = datetime.now(timezone.utc)
    latest = db.scalar(
        select(EmailDeliveryLog)
        .where(
            EmailDeliveryLog.recipient_email == user.email,
            EmailDeliveryLog.purpose == EmailPurpose.PROVIDER_APPROVAL.value,
        )
        .order_by(EmailDeliveryLog.created_at.desc(), EmailDeliveryLog.id.desc())
        .limit(1)
    )
    if latest is not None and latest.status == EmailDeliveryStatus.SUCCESS.value:
        user.provider_portal_approval_email_sent_at = latest.created_at
        db.commit()
        return True
    if (
        latest is not None
        and latest.status == EmailDeliveryStatus.PENDING.value
        and now - latest.created_at < timedelta(minutes=5)
    ):
        return False

    logs = EmailDeliveryRepository(db)
    try:
        attempt_id = logs.record_durable_attempt(
            recipient_email=user.email,
            purpose=EmailPurpose.PROVIDER_APPROVAL,
        )
    except Exception:
        db.rollback()
        return False

    try:
        login_url = get_settings().public_link("/provider/login")
        email_service.send_provider_approval_email(user.email, login_url)
    except Exception as exc:
        try:
            logs.complete_durable_attempt(
                attempt_id,
                status=EmailDeliveryStatus.FAILED,
                failure_message=safe_failure_message(exc),
            )
        except Exception:
            pass
        db.rollback()
        return False

    try:
        logs.complete_durable_attempt(
            attempt_id, status=EmailDeliveryStatus.SUCCESS
        )
        user.provider_portal_approval_email_sent_at = now
        db.commit()
    except Exception:
        db.rollback()
        return False
    return True