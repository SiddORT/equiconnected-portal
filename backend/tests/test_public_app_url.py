"""Public email destinations; no mail is sent by these tests."""
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.invitation_service import InvitationService


def settings(url: str, environment: str = "development") -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql://test@localhost/test",
        SECRET_KEY="test-only",
        PUBLIC_APP_URL=url,
        ENVIRONMENT=environment,
    )


def test_development_preview_links(monkeypatch):
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)
    config = settings("https://preview.replit.dev/")
    monkeypatch.setattr("app.services.invitation_service.get_settings", lambda: config)
    invitation = object.__new__(InvitationService)
    assert invitation._url("sample") == "https://preview.replit.dev/provider/invitations/sample"
    assert invitation._portal_setup_url("sample") == (
        "https://preview.replit.dev/provider/setup-password?token=sample"
    )
    verification = config.public_link("/verify-email?token=sample")
    assert urlsplit(verification).path == "/verify-email"
    assert parse_qs(urlsplit(verification).query) == {"token": ["sample"]}
    assert verification.startswith("https://preview.replit.dev/")


@pytest.mark.parametrize("url", [
    "http://localhost:5000",
    "https://127.0.0.1:5000",
    "https://[::1]:5000",
    "https://0.0.0.0:5000",
    "http://preview.replit.dev",
])
def test_deployment_rejects_unsafe_link_destinations(monkeypatch, url):
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    with pytest.raises(ValidationError, match="PUBLIC_APP_URL"):
        settings(url)


def test_production_requires_public_https_even_without_deployment_flag(monkeypatch):
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)
    with pytest.raises(ValidationError, match="PUBLIC_APP_URL"):
        settings("http://localhost:5000", "production")
    assert settings("https://live.example.com", "production").public_link(
        "/verify-email?token=sample"
    ) == "https://live.example.com/verify-email?token=sample"


@pytest.mark.parametrize("url", [
    "https://live.example.com/other",
    "https://live.example.com?query=1",
    "https://user:pass@live.example.com",
    "javascript:alert(1)",
])
def test_public_url_must_be_an_origin(url):
    with pytest.raises(ValidationError, match="PUBLIC_APP_URL"):
        settings(url)