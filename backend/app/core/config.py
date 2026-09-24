"""
Application configuration — all values come from environment variables.
Never hard-code secrets or credentials here.
"""
import ipaddress
import os
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "EquiConnected Portal"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str  # Required — must come from environment

    # ── Auth / JWT ───────────────────────────────────────────────────────────
    SECRET_KEY: str  # Required — used to sign JWTs
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5000", "http://127.0.0.1:5000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Cookie ───────────────────────────────────────────────────────────────
    COOKIE_SECURE: bool = False  # Set True in production (HTTPS)
    COOKIE_SAMESITE: str = "lax"

    # ── Email / invitations ───────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    EMAIL_FROM: str = "no-reply@equiconnected.local"
    EMAIL_TLS: bool = True
    PUBLIC_APP_URL: str = "http://localhost:5000"
    INVITATION_EXPIRE_DAYS: int = 7
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    PROVIDER_PORTAL_SETUP_EXPIRE_HOURS: int = 24
    # Uses an external provider; deployments can override this URL template.
    # Nominatim accepts the country name supplied by the shared location picker.
    POSTAL_LOOKUP_URL: str = (
        "https://nominatim.openstreetmap.org/search"
        "?postalcode={postal_code}&country={country}"
        "&format=jsonv2&addressdetails=1&limit=1"
    )
    POSTAL_LOOKUP_TIMEOUT_SECONDS: float = 3.0

    @model_validator(mode="after")
    def check_public_app_url(self) -> "Settings":
        """Do not allow emailed links to point at a local server in a deployment."""
        url = urlsplit(self.PUBLIC_APP_URL)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            raise ValueError("PUBLIC_APP_URL must be a frontend HTTP(S) origin without a path or credentials")
        try:
            _ = url.port  # Reject malformed port values.
        except ValueError as exc:
            raise ValueError("PUBLIC_APP_URL has an invalid port") from exc

        deployed = os.getenv("REPLIT_DEPLOYMENT") == "1"
        if deployed or self.ENVIRONMENT in ("staging", "production"):
            host = url.hostname.lower()
            try:
                local_ip = ipaddress.ip_address(host).is_loopback or ipaddress.ip_address(host).is_unspecified
            except ValueError:
                local_ip = False
            if url.scheme != "https" or host == "localhost" or host.endswith(".localhost") or local_ip:
                raise ValueError("PUBLIC_APP_URL must be a public HTTPS frontend URL in deployed environments")
        return self

    def public_link(self, path: str) -> str:
        """Build a frontend link from the validated public origin."""
        return f"{self.PUBLIC_APP_URL.rstrip('/')}/{path.lstrip('/')}"

    @property
    def resolved_email_from(self) -> str:
        """Prefer the SMTP-specific sender secret, with legacy fallback support."""
        return self.SMTP_FROM_EMAIL or self.EMAIL_FROM

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — import and call this everywhere."""
    return Settings()
