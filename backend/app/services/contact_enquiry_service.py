"""Durable contact-enquiry acceptance and optional notification delivery."""
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
        """Commit the enquiry before optionally attempting an email notification."""
        self._enquiries.create(body)
        recipient = (notification_recipient or "").strip()
        if not recipient:
            return

        # The enquiry repository has committed before this independent durable
        # email-attempt lifecycle begins; SMTP therefore runs without a DB txn.
        try:
            attempt_id = self._email_logs.record_durable_attempt(
                recipient_email=recipient,
                purpose=EmailPurpose.CONTACT_NOTIFICATION,
            )
        except Exception:
            # Notification delivery is optional once the enquiry is accepted.
            return

        outcome = EmailDeliveryStatus.SUCCESS
        failure_message = None
        try:
            self._email.send_contact_message(
                recipient,
                name=body.name,
                email=str(body.email),
                enquiry_type=body.enquiry_type,
                phone=body.phone,
                text=body.message,
            )
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