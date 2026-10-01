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


def test_contact_confirmation_uses_branded_multipart_and_configured_sender(monkeypatch):
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
            resolved_email_from="EquiConnected <no-reply@example.test>",
        ),
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSMTP)

    email_service.EmailService().send_contact_confirmation_email("sender@example.test")

    assert len(_FakeSMTP.sent_messages) == 1
    message = message_from_string(_FakeSMTP.sent_messages[0])
    assert message["Subject"] == "Your EquiConnected enquiry confirmation"
    assert message["To"] == "sender@example.test"
    assert message["From"] == "EquiConnected <no-reply@example.test>"
    assert message["Reply-To"] is None
    assert message.get_content_type() == "multipart/related"
    parts = list(message.walk())
    assert any(part.get_content_type() == "multipart/alternative" for part in parts)
    plain = next(part for part in parts if part.get_content_type() == "text/plain")
    html = next(part for part in parts if part.get_content_type() == "text/html")
    plain_body = plain.get_payload(decode=True).decode("utf-8")
    html_body = html.get_payload(decode=True).decode("utf-8")
    copy = "Your enquiry has been submitted. We will get back to you soon."
    assert copy in plain_body and copy in html_body
    assert "Thank you" in plain_body and "Thank you" in html_body
    assert "cid:equiconnected-logo" in html_body
    assert "background-color:#090908" in html_body
    assert "Visit EquiConnected" in html_body
    logo = next(part for part in parts if part.get_content_type() == "image/png")
    assert logo["Content-ID"] == "<equiconnected-logo>"
    assert logo.get_content_disposition() == "inline"
    # This API intentionally accepts only the recipient, so no name, phone,
    # enquiry category or private message can enter either confirmation body.
    assert "sender@example.test" not in plain_body + html_body


@pytest.mark.parametrize(
    ("method", "recipient", "kwargs", "expected_link", "expected_identity"),
    [
        (
            "send_member_message_acknowledgement",
            "member@example.test",
            {
                "provider_name": "Dr. Example <Care>",
                "thread_url": "https://app.example.test/member/messages/thread-id",
            },
            "https://app.example.test/member/messages/thread-id",
            "Dr. Example",
        ),
        (
            "send_provider_message_notification",
            "provider@example.test",
            {
                "thread_url": "https://app.example.test/provider/messages/thread-id",
            },
            "https://app.example.test/provider/messages/thread-id",
            "A member",
        ),
        (
            "send_member_reply_notification",
            "member@example.test",
            {
                "provider_name": "Dr. Example",
                "thread_url": "https://app.example.test/member/messages/thread-id",
            },
            "https://app.example.test/member/messages/thread-id",
            "Dr. Example",
        ),
    ],
)
def test_messaging_emails_are_branded_minimal_content_notifications(
    monkeypatch, method, recipient, kwargs, expected_link, expected_identity
):
    from app.services.email_service import EmailService

    sent = []
    monkeypatch.setattr(
        EmailService,
        "_deliver",
        staticmethod(lambda message, _recipient: sent.append(message.as_string())),
    )
    getattr(EmailService(), method)(recipient, **kwargs)

    message = message_from_string(sent[0])
    assert message["To"] == recipient
    parts = list(message.walk())
    plain = next(part for part in parts if part.get_content_type() == "text/plain")
    html = next(part for part in parts if part.get_content_type() == "text/html")
    plain_body = plain.get_payload(decode=True).decode("utf-8")
    html_body = html.get_payload(decode=True).decode("utf-8")

    assert expected_link in plain_body
    assert expected_link in html_body
    assert expected_identity in plain_body
    assert "cid:equiconnected-logo" in html_body
    if method != "send_member_message_acknowledgement":
        assert "private message" in (plain_body + html_body).lower()
    assert all(
        secret not in plain_body + html_body
        for secret in (
            "private body text",
            "member-phone",
            "member-contact@example.test",
        )
    )
    if method == "send_member_message_acknowledgement":
        assert "Dr. Example &lt;Care&gt;" in html_body