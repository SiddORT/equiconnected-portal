"""Focused MIME and presentation checks for EquiConnected transactional emails."""
from datetime import datetime
from email import message_from_string
from types import SimpleNamespace
import pytest

from app.services import email_service


class _FakeSMTP:
    sent_messages: list[str] = []

    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        pass

    def login(self, *_args):
        pass

    def sendmail(self, *_args):
        self.sent_messages.append(_args[-1])


class _RefusingSMTP(_FakeSMTP):
    def sendmail(self, *_args):
        return {"recipient@example.test": (550, b"Rejected")}


def test_verification_email_uses_branded_shell_and_inline_logo(monkeypatch):
    """Verification email keeps the invitation visual system with relevant copy."""
    _FakeSMTP.sent_messages = []
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            SMTP_HOST="smtp.example.test",
            SMTP_PORT=587,
            SMTP_USER="",
            SMTP_PASSWORD="",
            EMAIL_TLS=True,
            resolved_email_from="no-reply@example.test",
        ),
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSMTP)

    email_service.EmailService().send_verification_email(
        "recipient@example.test",
        "https://example.test/verify/secure-token",
        datetime(2026, 8, 28, 10, 37),
    )

    assert len(_FakeSMTP.sent_messages) == 1
    message = message_from_string(_FakeSMTP.sent_messages[0])
    assert message["Subject"] == "Verify your EquiConnected email"

    parts = list(message.walk())
    plain = next(part for part in parts if part.get_content_type() == "text/plain")
    html = next(part for part in parts if part.get_content_type() == "text/html")
    logo = next(part for part in parts if part.get_content_type() == "image/png")

    plain_body = plain.get_payload(decode=True).decode("utf-8")
    html_body = html.get_payload(decode=True).decode("utf-8")
    assert "Verify your email securely before" in plain_body
    assert "https://example.test/verify/secure-token" in plain_body
    assert "Verify your email" in html_body
    assert "activate your account" in html_body
    assert "cid:equiconnected-logo" in html_body
    assert logo.get("Content-ID") == "<equiconnected-logo>"
    assert logo.get_content_disposition() == "inline"


def test_email_delivery_rejects_a_recipient_refused_by_smtp(monkeypatch):
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            SMTP_HOST="smtp.example.test",
            SMTP_PORT=587,
            SMTP_USER="",
            SMTP_PASSWORD="",
            EMAIL_TLS=True,
            resolved_email_from="no-reply@example.test",
        ),
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP", _RefusingSMTP)

    with pytest.raises(email_service.EmailDeliveryError, match="SMTP server rejected"):
        email_service.EmailService().send_verification_email(
            "recipient@example.test",
            "https://example.test/verify/secure-token",
            datetime(2026, 8, 28, 10, 37),
        )


@pytest.mark.parametrize("failure,category", [
    (email_service.smtplib.SMTPAuthenticationError(535, b"secret response"), "SMTP authentication failed."),
    (email_service.smtplib.SMTPSenderRefused(550, b"secret response", "sender@example.test"), "SMTP sender rejected."),
    (email_service.smtplib.SMTPNotSupportedError("secret response"), "SMTP TLS negotiation failed."),
])
def test_smtp_failure_categories_do_not_expose_server_response(monkeypatch, failure, category):
    from app.repositories.email_delivery_repository import safe_failure_message
    from types import SimpleNamespace
    monkeypatch.setattr(email_service, "get_settings", lambda: SimpleNamespace(
        SMTP_HOST="smtp.example.test", SMTP_PORT=587, SMTP_USER="user",
        SMTP_PASSWORD="password", EMAIL_TLS=True, resolved_email_from="sender@example.test",
    ))
    class FailingSMTP(_FakeSMTP):
        def starttls(self):
            if isinstance(failure, email_service.smtplib.SMTPNotSupportedError):
                raise failure
        def login(self, *_args):
            if isinstance(failure, email_service.smtplib.SMTPAuthenticationError):
                raise failure
        def sendmail(self, *_args):
            raise failure
    monkeypatch.setattr(email_service.smtplib, "SMTP", FailingSMTP)
    with pytest.raises(email_service.EmailDeliveryError) as caught:
        email_service.EmailService().send_verification_email(
            "recipient@example.test", "https://example.test/verify/token",
            datetime(2026, 8, 28, 10, 37),
        )
    assert safe_failure_message(caught.value) == category
    assert "secret response" not in str(caught.value)


def test_subscriber_confirmation_uses_branded_shell_and_reach_out_copy(monkeypatch):
    _FakeSMTP.sent_messages = []
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            SMTP_HOST="smtp.example.test",
            SMTP_PORT=587,
            SMTP_USER="",
            SMTP_PASSWORD="",
            EMAIL_TLS=True,
            resolved_email_from="no-reply@example.test",
        ),
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSMTP)

    email_service.EmailService().send_subscriber_confirmation_email(
        "subscriber@example.test"
    )

    message = message_from_string(_FakeSMTP.sent_messages[0])
    assert message["Subject"] == "Thanks for registering with EquiConnected"
    plain = next(part for part in message.walk() if part.get_content_type() == "text/plain")
    html = next(part for part in message.walk() if part.get_content_type() == "text/html")
    assert "team will be in touch soon" in plain.get_payload(decode=True).decode("utf-8")
    assert "team will be in touch soon" in html.get_payload(decode=True).decode("utf-8")
    assert "cid:equiconnected-logo" in html.get_payload(decode=True).decode("utf-8")