"""Durable contact-enquiry acceptance and independent email deliveries."""
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.repositories.contact_enquiry_repository import ContactEnquiryRepository
from app.repositories.email_delivery_repository import (
    EmailDeliveryRepository,
    safe_failure_message,
)
from app.schemas.contact import ContactMessageRequest
from app.services.email_service import EmailService


class ContactEnquiryService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._enquiries = ContactEnquiryRepository(db)
        self._email_logs = EmailDeliveryRepository(db)
        self._email = EmailService()

    def submit(
        self, body: ContactMessageRequest, *, notification_recipient: str | None
    ) -> None:
        """Accept durably, then independently acknowledge and notify the team."""
        self._enquiries.create(body)
        # Use validated request values, never expired ORM attributes that could
        # reopen the acceptance transaction while SMTP is running.
        self._attempt_delivery(
            recipient=str(body.email),
            purpose=EmailPurpose.CONTACT_CONFIRMATION,
            send=lambda: self._email.send_contact_confirmation_email(str(body.email)),
        )
        recipient = (notification_recipient or "").strip()
        if recipient:
            self._attempt_delivery(
                recipient=recipient,
                purpose=EmailPurpose.CONTACT_NOTIFICATION,
                send=lambda: self._email.send_contact_message(
                    recipient,
                    name=body.name,
                    email=str(body.email),
                    enquiry_type=body.enquiry_type,
                    phone=body.phone,
                    text=body.message,
                ),
            )

    def _attempt_delivery(
        self, *, recipient: str, purpose: EmailPurpose, send: Callable[[], None]
    ) -> None:
        """Require durable accounting for each handoff without risking acceptance."""
        try:
            attempt_id = self._email_logs.record_durable_attempt(
                recipient_email=recipient,
                purpose=purpose,
            )
        except Exception:
            # Do not hand off unaccounted mail; the other delivery still runs.
            return

        outcome = EmailDeliveryStatus.SUCCESS
        failure_message = None
        try:
            send()
        except Exception as exc:
            outcome = EmailDeliveryStatus.FAILED
            failure_message = safe_failure_message(exc)

        try:
            self._email_logs.complete_durable_attempt(
                attempt_id,
                status=outcome,
                failure_message=failure_message,
            )
        except Exception:
            # A pending row truthfully records an unknown final SMTP outcome.
            pass