"""Public contact sends only to the configured team inbox."""

from types import SimpleNamespace

import pytest

from app.api.v1 import public
from app.core.rate_limit import _contact_attempts
from app.models.contact_enquiry import ContactEnquiry
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.repositories.contact_enquiry_repository import ContactEnquirySaveError
from app.services.email_service import EmailDeliveryError, EmailService


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


def test_contact_saves_full_submission_and_sends_to_configured_mailbox(
    client, db, monkeypatch
):
    calls = []
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    monkeypatch.setattr(
        EmailService, "send_contact_message",
        lambda _self, recipient, **kwargs: (
            calls.append((recipient, kwargs)),
            calls.append(("in_transaction", db.in_transaction())),
        ),
    )

    response = client.post(URL, json={**BODY, "phone": "+971 50 123 4567", "enquiry_type": "listing"})
    assert response.status_code == 202
    assert response.json() == {"message": "Your message was submitted."}
    assert calls == [(
        "team@example.com",
        {
            "name": "A Horse Owner",
            "email": "owner@example.com",
            "enquiry_type": "listing",
            "phone": "+971 50 123 4567",
            "text": BODY["message"],
        },
    ), ("in_transaction", False)]
    enquiry = db.query(ContactEnquiry).one()
    assert enquiry.name == BODY["name"]
    assert enquiry.email == BODY["email"]
    assert enquiry.enquiry_type == "listing"
    assert enquiry.phone == "+971 50 123 4567"
    assert enquiry.message == BODY["message"]
    assert enquiry.submitted_at.tzinfo is not None
    notification = db.query(EmailDeliveryLog).one()
    assert notification.purpose == EmailPurpose.CONTACT_NOTIFICATION.value
    assert notification.status == EmailDeliveryStatus.SUCCESS.value


def test_contact_rejects_invalid_content(client, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    monkeypatch.setattr(
        EmailService, "send_contact_message",
        lambda *_args, **_kwargs: pytest.fail("Invalid content must not send mail"),
    )
    for invalid in (
        {**BODY, "name": "   "},
        {**BODY, "email": "not-an-email"},
        {**BODY, "message": "     " * 3},
        {**BODY, "enquiry_type": "emergency"},
    ):
        _contact_attempts.clear()
        assert client.post(URL, json=invalid).status_code == 422


def test_contact_is_saved_when_notification_is_unconfigured(client, db, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL=""))
    response = client.post(URL, json=BODY)
    assert response.status_code == 202
    enquiry = db.query(ContactEnquiry).one()
    assert enquiry.phone is None
    assert db.query(EmailDeliveryLog).count() == 0


def test_repeated_sender_submissions_and_long_multiline_content_are_retained(
    client, db, monkeypatch
):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL=""))
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


def test_contact_is_saved_when_notification_delivery_fails(client, db, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))

    def fail_delivery(*_args, **_kwargs):
        raise EmailDeliveryError("SMTP password secret detail")

    monkeypatch.setattr(EmailService, "send_contact_message", fail_delivery)
    accepted = client.post(URL, json=BODY)
    assert accepted.status_code == 202
    assert db.query(ContactEnquiry).count() == 1
    delivery = db.query(EmailDeliveryLog).one()
    assert delivery.status == EmailDeliveryStatus.FAILED.value
    assert delivery.failure_message == "Unable to deliver email."
    assert "secret detail" not in accepted.text


def test_contact_save_failure_returns_safe_retryable_error(client, db, monkeypatch):
    from app.repositories.contact_enquiry_repository import ContactEnquiryRepository

    def fail_save(*_args, **_kwargs):
        raise ContactEnquirySaveError

    monkeypatch.setattr(ContactEnquiryRepository, "create", fail_save)
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    monkeypatch.setattr(
        EmailService,
        "send_contact_message",
        lambda *_args, **_kwargs: pytest.fail("Do not notify when persistence fails"),
    )
    response = client.post(URL, json=BODY)
    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "contact_save_failed",
        "message": "We could not save your message. Please try again later.",
    }
    assert db.query(ContactEnquiry).count() == 0
    assert db.query(EmailDeliveryLog).count() == 0


def test_contact_rate_limits_anonymous_sends(client, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    monkeypatch.setattr(EmailService, "send_contact_message", lambda *_args, **_kwargs: None)
    for _ in range(3):
        assert client.post(URL, json=BODY).status_code == 202
    assert client.post(URL, json=BODY).status_code == 429