"""SMTP-backed invitation email delivery."""
import smtplib
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

from app.core.config import get_settings
from app.models.enums import ProviderType

_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "equiconnected-logo-gold.png"
_LOGO_CONTENT_ID = "equiconnected-logo"


class EmailDeliveryError(Exception):
    """Email could not be handed to the configured SMTP server."""


class EmailService:
    @staticmethod
    def _invitation_html(
        provider_type: ProviderType, invitation_url: str, expiry: str
    ) -> str:
        """Build a robust, table-based invitation email for major email clients."""
        provider_label = escape(provider_type.value.title())
        safe_url = escape(invitation_url, quote=True)
        return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Your EquiConnected invitation</title>
  </head>
  <body style="margin:0;padding:0;background-color:#090908;color:#f5efe4;font-family:Georgia,'Times New Roman',serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background-color:#090908;">
      <tr>
        <td align="center" style="padding:42px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:620px;background-color:#11100e;border:1px solid #4a3b25;border-radius:8px;">
            <tr>
              <td align="center" style="padding:48px 42px 18px;">
                <img src="cid:{_LOGO_CONTENT_ID}" width="66" height="66" alt="EquiConnected logo" style="display:block;width:66px;height:66px;margin:0 auto;border:0;outline:none;text-decoration:none;">
                <div style="margin-top:14px;font-family:Arial,sans-serif;font-size:11px;line-height:16px;letter-spacing:4px;color:#b9975b;">EQUICONNECTED</div>
                <div style="margin-top:5px;font-family:Arial,sans-serif;font-size:8px;line-height:12px;letter-spacing:2px;color:#82745b;">EXCEPTIONAL EQUINE CARE</div>
                <div style="width:52px;height:1px;margin:25px auto 0;background-color:#80633a;"></div>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:10px 42px 12px;">
                <h1 style="margin:0;color:#f5efe4;font-size:33px;font-weight:400;line-height:1.25;">Welcome to<br>EquiConnected.</h1>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:0 42px;">
                <p style="margin:0;color:#d2c8b7;font-family:Arial,sans-serif;font-size:15px;line-height:24px;">
                  You have been invited to complete a <strong style="color:#f5efe4;">{provider_label}</strong> profile.
                  Share the details that will help equine owners find trusted care when EquiConnected launches.
                </p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:30px 42px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td align="center" bgcolor="#a8844e" style="border-radius:4px;">
                      <a href="{safe_url}" target="_blank" style="display:inline-block;padding:14px 26px;color:#15110b;font-family:Arial,sans-serif;font-size:13px;font-weight:700;letter-spacing:.3px;text-decoration:none;">
                        Complete your profile
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:0 42px 34px;">
                <p style="margin:0;color:#9e927f;font-family:Arial,sans-serif;font-size:12px;line-height:19px;">
                  This secure invitation expires on {escape(expiry)}.<br>
                  If you were not expecting this email, you can safely ignore it.
                </p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:18px 24px 26px;border-top:1px solid #30281d;">
                <div style="font-family:Arial,sans-serif;font-size:9px;line-height:14px;letter-spacing:2px;color:#806f53;">LAUNCHING 2026&nbsp;&nbsp;·&nbsp;&nbsp;UAE</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

    def send_invitation_email(
        self, recipient: str, provider_type: ProviderType, invitation_url: str, expires_at: datetime
    ) -> None:
        settings = get_settings()
        if not settings.SMTP_HOST:
            raise EmailDeliveryError("SMTP_HOST is not configured; invitation email was not sent.")
        message = MIMEMultipart("related")
        message["Subject"] = "Complete your EquiConnected provider profile"
        message["From"] = settings.resolved_email_from
        message["To"] = recipient
        expiry = expires_at.strftime("%B %d, %Y at %H:%M UTC")
        plain = (
            "Welcome to EquiConnected.\n\n"
            f"You have been invited to complete a {provider_type.value.lower()} profile. "
            "Share the details that will help equine owners find trusted care when EquiConnected launches.\n\n"
            f"Complete your profile securely before {expiry}:\n{invitation_url}\n\n"
            "If you were not expecting this email, you can safely ignore it.\n"
        )
        html = self._invitation_html(provider_type, invitation_url, expiry)
        alternatives = MIMEMultipart("alternative")
        alternatives.attach(MIMEText(plain, "plain", "utf-8"))
        alternatives.attach(MIMEText(html, "html", "utf-8"))
        message.attach(alternatives)

        try:
            logo = MIMEImage(_LOGO_PATH.read_bytes(), _subtype="png")
        except OSError as exc:
            raise EmailDeliveryError("Unable to load the EquiConnected email logo.") from exc
        logo.add_header("Content-ID", f"<{_LOGO_CONTENT_ID}>")
        logo.add_header("Content-Disposition", "inline", filename="equiconnected-logo.png")
        message.attach(logo)
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                if settings.EMAIL_TLS:
                    smtp.starttls()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(settings.resolved_email_from, [recipient], message.as_string())
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("Unable to deliver invitation email.") from exc