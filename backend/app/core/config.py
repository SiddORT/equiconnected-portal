"""
Application configuration — all values come from environment variables.
Never hard-code secrets or credentials here.
"""
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
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
