"""SMTP-backed invitation email delivery."""
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings
from app.models.enums import ProviderType


class EmailDeliveryError(Exception):
    """Email could not be handed to the configured SMTP server."""


class EmailService:
    def send_invitation_email(
        self, recipient: str, provider_type: ProviderType, invitation_url: str, expires_at: datetime
    ) -> None:
        settings = get_settings()
        if not settings.SMTP_HOST:
            raise EmailDeliveryError("SMTP_HOST is not configured; invitation email was not sent.")
        message = MIMEMultipart("alternative")
        message["Subject"] = "Complete your EquiConnected provider profile"
        message["From"] = settings.EMAIL_FROM
        message["To"] = recipient
        expiry = expires_at.strftime("%B %d, %Y at %H:%M UTC")
        plain = (
            f"You have been invited to complete a {provider_type.value.lower()} profile on EquiConnected.\n"
            f"Use this secure link before {expiry}: {invitation_url}\n"
        )
        html = (
            "<html><body><h2 style='color:#176B87'>EquiConnected</h2>"
            f"<p>You have been invited to complete a <strong>{provider_type.value.title()}</strong> profile.</p>"
            f"<p><a href='{invitation_url}'>Complete your profile</a></p>"
            f"<p>This invitation expires {expiry}.</p></body></html>"
        )
        message.attach(MIMEText(plain, "plain", "utf-8"))
        message.attach(MIMEText(html, "html", "utf-8"))
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                if settings.EMAIL_TLS:
                    smtp.starttls()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(settings.EMAIL_FROM, [recipient], message.as_string())
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("Unable to deliver invitation email.") from exc