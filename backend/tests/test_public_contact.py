"""Accepted public contacts independently acknowledge senders and notify the team."""

from types import SimpleNamespace

import pytest

from app.api.v1 import public
from app.core.rate_limit import _contact_attempts
from app.models.contact_enquiry import ContactEnquiry
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.repositories.contact_enquiry_repository import ContactEnquirySaveError
from app.repositories.email_delivery_repository import EmailDeliveryRepository
from app.services.email_service import EmailDeliveryError, EmailService
from tests.conftest import TestingSessionLocal


URL = "/api/v1/public/contact"
BODY = {
    "name": "A Horse Owner",
    "email": "owner@example.com",
    "enquiry_type": "general",
    "message": "I would like to know more about the platform.",
}


@pytest.fixture(autouse=True)
def clear_contact_attempts():
    _contact_attempts.clear()
    yield
    _contact_attempts.clear()


@pytest.fixture(autouse=True)
def stub_contact_email_sends(monkeypatch):
    """Never let a public-contact test hand a message to a real SMTP server."""
    monkeypatch.setattr(
        EmailService, "send_contact_confirmation_email", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        EmailService, "send_contact_message", lambda *_args, **_kwargs: None
    )


def test_contact_saves_full_submission_and_sends_to_configured_mailbox(
    client, db, monkeypatch
):
    calls = []
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))

    def send_confirmation(_self, recipient):
        calls.append(("confirmation", recipient, db.in_transaction()))

    def send_notification(_self, recipient, **kwargs):
        calls.append(("notification", recipient, kwargs, db.in_transaction()))

    monkeypatch.setattr(
        EmailService, "send_contact_confirmation_email", send_confirmation
    )
    monkeypatch.setattr(EmailService, "send_contact_message", send_notification)

    response = client.post(URL, json={**BODY, "phone": "+971 50 123 4567", "enquiry_type": "listing"})
    assert response.status_code == 202
    assert response.json() == {"message": "Your message was submitted."}
    assert calls == [(
        "confirmation",
        BODY["email"],
        False,
    ), (
        "notification",
        "team@example.com",
        {
            "name": "A Horse Owner",
            "email": "owner@example.com",
            "enquiry_type": "listing",
            "phone": "+971 50 123 4567",
            "text": BODY["message"],
        },
        False,
    )]
    enquiry = db.query(ContactEnquiry).one()
    assert enquiry.name == BODY["name"]
    assert enquiry.email == BODY["email"]
    assert enquiry.enquiry_type == "listing"
    assert enquiry.phone == "+971 50 123 4567"
    assert enquiry.message == BODY["message"]
    assert enquiry.submitted_at.tzinfo is not None
    deliveries = {entry.purpose: entry for entry in db.query(EmailDeliveryLog).all()}
    assert set(deliveries) == {"contact_confirmation", EmailPurpose.CONTACT_NOTIFICATION.value}
    assert all(
        entry.status == EmailDeliveryStatus.SUCCESS.value
        for entry in deliveries.values()
    )


@pytest.mark.parametrize("enquiry_type", ["general", "listing", "partnership", "other"])
def test_each_supported_enquiry_type_sends_both_emails(
    client, db, monkeypatch, enquiry_type
):
    sent = []
    monkeypatch.setattr(
        public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com")
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda _self, recipient: sent.append(("confirmation", recipient)),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda _self, recipient, **_kwargs: sent.append(("notification", recipient)),
    )

    response = client.post(URL, json={**BODY, "enquiry_type": enquiry_type})

    assert response.status_code == 202
    assert sent == [
        ("confirmation", BODY["email"]),
        ("notification", "team@example.com"),
    ]
    assert {
        entry.purpose: entry.status for entry in db.query(EmailDeliveryLog).all()
    } == {
        "contact_confirmation": EmailDeliveryStatus.SUCCESS.value,
        EmailPurpose.CONTACT_NOTIFICATION.value: EmailDeliveryStatus.SUCCESS.value,
    }


def test_contact_rejects_invalid_content(client, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    calls = []
    monkeypatch.setattr(
        EmailService, "send_contact_confirmation_email",
        lambda *_args, **_kwargs: calls.append("confirmation"),
    )
    monkeypatch.setattr(
        EmailService, "send_contact_message",
        lambda *_args, **_kwargs: calls.append("notification"),
    )
    for invalid in (
        {**BODY, "name": "   "},
        {**BODY, "email": "not-an-email"},
        {**BODY, "message": "     " * 3},
        {**BODY, "enquiry_type": "emergency"},
    ):
        _contact_attempts.clear()
        assert client.post(URL, json=invalid).status_code == 422
    assert calls == []


def test_contact_is_saved_when_notification_is_unconfigured(client, db, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL=""))
    sent = []
    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda _self, recipient: sent.append(recipient),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda *_args, **_kwargs: pytest.fail("Unconfigured team notification must not send"),
    )
    response = client.post(URL, json=BODY)
    assert response.status_code == 202
    enquiry = db.query(ContactEnquiry).one()
    assert enquiry.phone is None
    assert sent == [BODY["email"]]
    delivery = db.query(EmailDeliveryLog).one()
    assert delivery.purpose == "contact_confirmation"
    assert delivery.status == EmailDeliveryStatus.SUCCESS.value


def test_repeated_sender_submissions_and_long_multiline_content_are_retained(
    client, db, monkeypatch
):
    sent = []
    monkeypatch.setattr(
        public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com")
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda _self, recipient: sent.append(("confirmation", recipient)),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda _self, recipient, **_kwargs: sent.append(("notification", recipient)),
    )
    long_message = (
        "Opening sentence.\n"
        + ("Full content on this line. " * 129)
        + "Final line."
    )
    body = {
        **BODY,
        "phone": "+971 50 123 4567",
        "message": long_message,
    }
    first = client.post(URL, json=body)
    second = client.post(URL, json=body)
    assert first.status_code == second.status_code == 202
    rows = (
        db.query(ContactEnquiry)
        .filter_by(email=BODY["email"])
        .order_by(ContactEnquiry.submitted_at, ContactEnquiry.id)
        .all()
    )
    assert len(rows) == 2
    assert [row.message for row in rows] == [long_message, long_message]
    assert all(row.phone == body["phone"] for row in rows)
    assert sent == [
        ("confirmation", BODY["email"]),
        ("notification", "team@example.com"),
        ("confirmation", BODY["email"]),
        ("notification", "team@example.com"),
    ]
    assert db.query(EmailDeliveryLog).count() == 4


def test_contact_is_saved_when_notification_delivery_fails(client, db, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))

    def fail_delivery(*_args, **_kwargs):
        raise EmailDeliveryError("SMTP password secret detail")

    monkeypatch.setattr(EmailService, "send_contact_message", fail_delivery)
    accepted = client.post(URL, json=BODY)
    assert accepted.status_code == 202
    assert db.query(ContactEnquiry).count() == 1
    delivery = (
        db.query(EmailDeliveryLog)
        .filter_by(purpose=EmailPurpose.CONTACT_NOTIFICATION.value)
        .one()
    )
    assert delivery.status == EmailDeliveryStatus.FAILED.value
    assert delivery.failure_message == "Unable to deliver email."
    assert "secret detail" not in accepted.text
    confirmation = (
        db.query(EmailDeliveryLog).filter_by(purpose="contact_confirmation").one()
    )
    assert confirmation.status == EmailDeliveryStatus.SUCCESS.value


@pytest.mark.parametrize(
    ("failed_channel", "expected_statuses"),
    [
        (
            "confirmation",
            {
                "contact_confirmation": EmailDeliveryStatus.FAILED.value,
                EmailPurpose.CONTACT_NOTIFICATION.value: EmailDeliveryStatus.SUCCESS.value,
            },
        ),
        (
            "notification",
            {
                "contact_confirmation": EmailDeliveryStatus.SUCCESS.value,
                EmailPurpose.CONTACT_NOTIFICATION.value: EmailDeliveryStatus.FAILED.value,
            },
        ),
    ],
)
def test_smtp_failure_on_either_channel_is_independent_and_safe(
    client, db, monkeypatch, failed_channel, expected_statuses
):
    calls = []
    monkeypatch.setattr(
        public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com")
    )

    def attempt(channel):
        calls.append(channel)
        if channel == failed_channel:
            raise EmailDeliveryError("SMTP password super-secret")

    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda _self, _recipient: attempt("confirmation"),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda _self, _recipient, **_kwargs: attempt("notification"),
    )

    response = client.post(URL, json=BODY)

    assert response.status_code == 202
    assert "super-secret" not in response.text
    assert calls == ["confirmation", "notification"]
    deliveries = {row.purpose: row for row in db.query(EmailDeliveryLog).all()}
    assert {purpose: row.status for purpose, row in deliveries.items()} == expected_statuses
    failed = deliveries[
        "contact_confirmation"
        if failed_channel == "confirmation"
        else EmailPurpose.CONTACT_NOTIFICATION.value
    ]
    assert failed.failure_message == "Unable to deliver email."


@pytest.mark.parametrize(
    ("failed_accounting_channel", "expected_sends", "expected_logged_purpose"),
    [
        ("confirmation", ["notification"], EmailPurpose.CONTACT_NOTIFICATION.value),
        ("notification", ["confirmation"], "contact_confirmation"),
    ],
)
def test_initial_accounting_failure_skips_only_its_own_send(
    client,
    db,
    monkeypatch,
    failed_accounting_channel,
    expected_sends,
    expected_logged_purpose,
):
    sends = []
    monkeypatch.setattr(
        public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com")
    )
    original_record = EmailDeliveryRepository.record_durable_attempt

    def record_or_fail(self, *, recipient_email, purpose):
        purpose_value = purpose.value if hasattr(purpose, "value") else purpose
        if purpose_value == (
            "contact_confirmation"
            if failed_accounting_channel == "confirmation"
            else EmailPurpose.CONTACT_NOTIFICATION.value
        ):
            raise RuntimeError("accounting backend secret")
        return original_record(
            self, recipient_email=recipient_email, purpose=purpose
        )

    monkeypatch.setattr(
        EmailDeliveryRepository, "record_durable_attempt", record_or_fail
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda *_args: sends.append("confirmation"),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda *_args, **_kwargs: sends.append("notification"),
    )

    response = client.post(URL, json=BODY)

    assert response.status_code == 202
    assert "accounting backend secret" not in response.text
    assert sends == expected_sends
    rows = db.query(EmailDeliveryLog).all()
    assert len(rows) == 1
    assert rows[0].purpose == expected_logged_purpose
    assert rows[0].status == EmailDeliveryStatus.SUCCESS.value


@pytest.mark.parametrize(
    ("failed_accounting_channel", "pending_purpose"),
    [
        ("confirmation", "contact_confirmation"),
        ("notification", EmailPurpose.CONTACT_NOTIFICATION.value),
    ],
)
def test_final_accounting_failure_leaves_only_that_attempt_pending(
    client, db, monkeypatch, failed_accounting_channel, pending_purpose
):
    sends = []
    monkeypatch.setattr(
        public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com")
    )
    original_record = EmailDeliveryRepository.record_durable_attempt
    original_complete = EmailDeliveryRepository.complete_durable_attempt
    purpose_by_id = {}

    def record_and_remember(self, *, recipient_email, purpose):
        attempt_id = original_record(
            self, recipient_email=recipient_email, purpose=purpose
        )
        purpose_by_id[attempt_id] = purpose.value if hasattr(purpose, "value") else purpose
        return attempt_id

    def complete_or_fail(self, attempt_id, **kwargs):
        if purpose_by_id[attempt_id] == pending_purpose:
            raise RuntimeError("accounting backend secret")
        return original_complete(self, attempt_id, **kwargs)

    monkeypatch.setattr(
        EmailDeliveryRepository, "record_durable_attempt", record_and_remember
    )
    monkeypatch.setattr(
        EmailDeliveryRepository, "complete_durable_attempt", complete_or_fail
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda *_args: sends.append("confirmation"),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda *_args, **_kwargs: sends.append("notification"),
    )

    response = client.post(URL, json=BODY)

    assert response.status_code == 202
    assert "accounting backend secret" not in response.text
    assert sends == ["confirmation", "notification"]
    statuses = {
        row.purpose: row.status for row in db.query(EmailDeliveryLog).all()
    }
    assert statuses == {
        "contact_confirmation": (
            EmailDeliveryStatus.PENDING.value
            if pending_purpose == "contact_confirmation"
            else EmailDeliveryStatus.SUCCESS.value
        ),
        EmailPurpose.CONTACT_NOTIFICATION.value: (
            EmailDeliveryStatus.PENDING.value
            if pending_purpose == EmailPurpose.CONTACT_NOTIFICATION.value
            else EmailDeliveryStatus.SUCCESS.value
        ),
    }


def test_each_smtp_send_has_a_durable_pending_attempt_and_no_caller_transaction(
    client, db, monkeypatch
):
    observations = []
    monkeypatch.setattr(
        public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com")
    )

    def inspect_attempt(channel, recipient):
        assert db.in_transaction() is False
        with TestingSessionLocal() as independent_db:
            pending = (
                independent_db.query(EmailDeliveryLog)
                .filter_by(recipient_email=recipient, status=EmailDeliveryStatus.PENDING.value)
                .all()
            )
            expected_purpose = (
                "contact_confirmation"
                if channel == "confirmation"
                else EmailPurpose.CONTACT_NOTIFICATION.value
            )
            assert [row.purpose for row in pending] == [expected_purpose]
        observations.append(channel)

    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda _self, recipient: inspect_attempt("confirmation", recipient),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda _self, recipient, **_kwargs: inspect_attempt("notification", recipient),
    )

    response = client.post(URL, json=BODY)

    assert response.status_code == 202
    assert observations == ["confirmation", "notification"]


def test_contact_save_failure_returns_safe_retryable_error(client, db, monkeypatch):
    from app.repositories.contact_enquiry_repository import ContactEnquiryRepository

    def fail_save(*_args, **_kwargs):
        raise ContactEnquirySaveError

    monkeypatch.setattr(ContactEnquiryRepository, "create", fail_save)
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    calls = []
    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda *_args, **_kwargs: calls.append("confirmation"),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda *_args, **_kwargs: calls.append("notification"),
    )
    response = client.post(URL, json=BODY)
    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "contact_save_failed",
        "message": "We could not save your message. Please try again later.",
    }
    assert db.query(ContactEnquiry).count() == 0
    assert db.query(EmailDeliveryLog).count() == 0
    assert calls == []


def test_contact_rate_limits_anonymous_sends(client, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    sends = []
    monkeypatch.setattr(
        EmailService,
        "send_contact_confirmation_email",
        lambda *_args: sends.append("confirmation"),
    )
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda *_args, **_kwargs: sends.append("notification"),
    )
    for _ in range(3):
        assert client.post(URL, json=BODY).status_code == 202
    sent_before_limited_request = len(sends)
    assert client.post(URL, json=BODY).status_code == 429
    assert len(sends) == sent_before_limited_request == 6