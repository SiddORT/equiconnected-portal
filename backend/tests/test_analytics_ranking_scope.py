"""Stable pagination, filter scope and join-fanout regressions."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.core.time_standards import system_today
from app.models.analytics_traffic import TrafficPageCategoryDaily, TrafficTrackingMetadata
from app.models.enums import ProviderStatus, ProviderType, PublicationStatus, VisitStability
from app.models.provider import Provider, ProviderLocation
from app.repositories.system_settings_repository import SystemSettingsRepository


def test_zero_view_ranking_is_stable_and_geography_does_not_duplicate_rows(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    settings = SystemSettingsRepository(db).get_or_create()
    settings.timezone = "UTC"
    today = system_today("UTC")
    first = today - timedelta(days=6)
    db.add(TrafficTrackingMetadata(
        id=1, tracking_started_at=datetime.combine(first, datetime.min.time(), timezone.utc)
    ))
    providers = [
        Provider(
            name=name, provider_type=ProviderType.CLINIC,
            visit_stability=VisitStability.STABLE_VISIT,
            status=ProviderStatus.ACTIVE, publication_status=PublicationStatus.PUBLISHED,
        )
        for name in ("Alpha", "Beta", "Gamma")
    ]
    db.add_all(providers)
    db.flush()
    db.add_all([
        ProviderLocation(provider_id=provider.id, address_line_1="Test",
                         country="Testland", city="Example", is_primary=index == 0)
        for provider in providers for index in range(2)
    ])
    db.add(TrafficPageCategoryDaily(visit_date=today, category="home", page_views=9))
    db.commit()
    base = "/api/v1/admin/analytics"
    params = {"preset": "last_7_days", "country": "Testland", "city": "Example",
              "page_size": 2, "sort": "profile_views", "sort_direction": "desc"}
    result = client.get(f"{base}/provider-ranking", params=params, headers=headers)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["meta"]["total"] == 3
    assert [row["name"] for row in payload["data"]] == ["Alpha", "Beta"]
    assert all(row["profile_views"] == 0 for row in payload["data"])
    second = client.get(f"{base}/provider-ranking",
                        params={**params, "page": 2}, headers=headers).json()
    assert [row["name"] for row in second["data"]] == ["Gamma"]
    clamped = client.get(f"{base}/provider-ranking",
                         params={**params, "page": 999}, headers=headers).json()
    assert clamped["meta"]["page"] == 2
    assert [row["name"] for row in clamped["data"]] == ["Gamma"]
    # A nonexistent provider filter cannot narrow the site's home page traffic.
    traffic = client.get(
        f"{base}/series",
        params={"preset": "last_7_days", "metric": "website_page_views",
                "provider_search": "No matching listing"},
        headers=headers,
    )
    assert traffic.status_code == 200, traffic.text
    assert sum(point["value"] for point in traffic.json()["data"]) == 9
    assert db.scalar(select(TrafficPageCategoryDaily.page_views)) == 9
    summary = client.get(f"{base}/summary", params={"preset": "last_7_days"},
                         headers=headers).json()
    latest = next(metric for metric in summary["sections"]["traffic"]["metrics"]
                  if metric["key"] == "latest_daily_visitor_estimate")
    assert latest["value"] == 0
    assert latest["date"] == today.isoformat()