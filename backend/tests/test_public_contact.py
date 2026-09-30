"""Public contact sends only to the configured team inbox."""

from types import SimpleNamespace

import pytest

from app.api.v1 import public
from app.core.rate_limit import _contact_attempts
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


def test_contact_sends_to_configured_mailbox(client, monkeypatch):
    calls = []
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    monkeypatch.setattr(
        EmailService, "send_contact_message",
        lambda _self, recipient, **kwargs: calls.append((recipient, kwargs)),
    )

    response = client.post(URL, json={**BODY, "phone": "+971 50 123 4567", "enquiry_type": "listing"})
    assert response.status_code == 202
    assert calls == [(
        "team@example.com",
        {
            "name": "A Horse Owner",
            "email": "owner@example.com",
            "enquiry_type": "listing",
            "phone": "+971 50 123 4567",
            "text": BODY["message"],
        },
    )]


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


def test_contact_reports_missing_recipient_and_delivery_failure(client, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL=""))
    unavailable = client.post(URL, json=BODY)
    assert unavailable.status_code == 503

    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))

    def fail_delivery(*_args, **_kwargs):
        raise EmailDeliveryError("SMTP password secret detail")

    monkeypatch.setattr(EmailService, "send_contact_message", fail_delivery)
    failed = client.post(URL, json=BODY)
    assert failed.status_code == 502
    assert "secret detail" not in failed.text


def test_contact_rate_limits_anonymous_sends(client, monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com"))
    monkeypatch.setattr(EmailService, "send_contact_message", lambda *_args, **_kwargs: None)
    for _ in range(3):
        assert client.post(URL, json=BODY).status_code == 202
    assert client.post(URL, json=BODY).status_code == 429