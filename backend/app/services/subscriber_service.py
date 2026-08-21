"""Subscriber persistence and confirmation delivery orchestration."""
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose, SubscriberRegistrationType
from app.models.subscriber import Subscriber
from app.repositories.email_delivery_repository import EmailDeliveryRepository, safe_failure_message
from app.repositories.subscriber_repository import SubscriberRepository
from app.services.email_service import EmailService


class SubscriberService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._subscribers = SubscriberRepository(db)
        self._email_logs = EmailDeliveryRepository(db)
        self._email = EmailService()

    def register(
        self, *, email: str, registration_type: SubscriberRegistrationType
    ) -> bool:
        """Persist a subscriber and return whether confirmation delivery succeeded."""
        subscriber, _created = self._subscribers.create_or_get(
            email=email, registration_type=registration_type
        )
        # Hold the subscriber row lock through the SMTP handoff. This is a
        # deliberately narrow per-email serialization point: it prevents two
        # racing public requests from both deciding they should send the first
        # confirmation, while keeping unrelated subscriber submissions free.
        locked_subscriber = self._db.scalar(
            select(Subscriber)
            .where(Subscriber.id == subscriber.id)
            .with_for_update()
        )
        if locked_subscriber is None:
            raise RuntimeError("Subscriber disappeared before confirmation delivery.")
        try:
            latest = self._db.scalar(
                select(EmailDeliveryLog)
                .where(
                    EmailDeliveryLog.recipient_email == locked_subscriber.email,
                    EmailDeliveryLog.purpose == EmailPurpose.SUBSCRIBER_CONFIRMATION.value,
                )
                .order_by(desc(EmailDeliveryLog.created_at), desc(EmailDeliveryLog.id))
                .limit(1)
            )
            if latest is not None and latest.status == EmailDeliveryStatus.SUCCESS.value:
                return True

            # A pending attempt means the last process did not finalize its
            # SMTP outcome. Because this lock excludes a live parallel
            # submission, a new request can safely record a fresh, auditable
            # retry instead of leaving confirmation delivery stranded.
            attempt_id = self._email_logs.record_durable_attempt(
                recipient_email=locked_subscriber.email,
                purpose=EmailPurpose.SUBSCRIBER_CONFIRMATION,
            )
            try:
                self._email.send_subscriber_confirmation_email(locked_subscriber.email)
            except Exception as exc:
                try:
                    self._email_logs.complete_durable_attempt(
                        attempt_id,
                        status=EmailDeliveryStatus.FAILED,
                        failure_message=safe_failure_message(exc),
                    )
                except Exception:
                    # The already-committed pending attempt is the honest
                    # outcome if status persistence itself is unavailable.
                    pass
                return False

            try:
                self._email_logs.complete_durable_attempt(
                    attempt_id,
                    status=EmailDeliveryStatus.SUCCESS,
                )
            except Exception:
                # The SMTP server accepted the message, but the pending record
                # is intentionally retained for a later, auditable retry.
                return False
            return True
        finally:
            # This transaction only owns the row lock; delivery logs commit in
            # independent sessions so their outcome survives this rollback.
            self._db.rollback()