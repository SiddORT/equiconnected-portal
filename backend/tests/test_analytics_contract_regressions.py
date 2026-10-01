"""Cross-panel tests using actual HTTP payloads rather than mocked contracts."""
import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

from app.core.time_standards import system_today
from app.models.enums import ProviderReviewStatus
from app.models.provider import ProviderReview
from app.models.public_visit import PublicVisitDaily
from app.repositories.system_settings_repository import SystemSettingsRepository
from tests.test_admin_analytics_reporting import BASE, _auth, _create_member, _provider


def test_registration_summary_uses_selected_cohort(client, db, seeded_admin):
    SystemSettingsRepository(db).get_or_create().timezone = "UTC"
    today = system_today("UTC")
    now = datetime.combine(today, datetime.min.time(), timezone.utc)
    old = _create_member(db, email="old@example.com", created_at=now - timedelta(days=60))
    old.email_verified_at = now
    new = _create_member(db, email="new@example.com", created_at=now)
    new.email_verified_at = now
    db.commit()
    params = {"preset": "today"}
    summary = client.get(f"{BASE}/summary", params=params, headers=_auth(seeded_admin[0])).json()
    section = summary["sections"]["registrations"]
    assert section["cohort_current_state"]["total"] == 1
    assert section["cohort_current_state"]["verified"]["true"] == 1
    assert next(x for x in section["metrics"] if x["key"] == "verified_registrations")["value"] == 1
    breakdown = client.get(f"{BASE}/breakdowns", params={**params, "domain": "registrations"},
                           headers=_auth(seeded_admin[0])).json()
    assert breakdown["groups"]["selected_cohort"] == section["cohort_current_state"]


@pytest.mark.parametrize("grouping", ["daily", "weekly", "monthly"])
def test_legacy_series_grouping_preserves_all_daily_counts(client, db, seeded_admin, grouping):
    SystemSettingsRepository(db).get_or_create().timezone = "UTC"
    today = system_today("UTC")
    first = today - timedelta(days=40)
    db.add_all(PublicVisitDaily(visit_date=first + timedelta(days=i), visit_count=i + 1)
               for i in range(41))
    db.commit()
    params = {"preset": "custom", "date_from": first.isoformat(), "date_to": today.isoformat(),
              "group_by": grouping, "metric": "legacy_homepage_visits"}
    result = client.get(f"{BASE}/series", params=params, headers=_auth(seeded_admin[0]))
    assert result.status_code == 200, result.text
    assert sum(row["value"] for row in result.json()["data"]) == sum(range(1, 42))
    exported = client.get(f"{BASE}/export", params={**params, "dataset": "series"},
                          headers=_auth(seeded_admin[0]))
    assert exported.status_code == 200, exported.text
    rows = list(csv.reader(io.StringIO(exported.text)))
    header_index = next(i for i, row in enumerate(rows) if row[0] == "bucket")
    value_index = rows[header_index].index("value")
    assert sum(int(row[value_index]) for row in rows[header_index + 1:]) == sum(range(1, 42))


def test_provider_name_filter_consistent_across_review_reports(client, db, seeded_admin):
    SystemSettingsRepository(db).get_or_create().timezone = "UTC"
    member = _create_member(db, email="reviews@example.com")
    selected, other = _provider(db, name="Selected Clinic"), _provider(db, name="Other Clinic")
    db.add_all(ProviderReview(provider_id=provider.id, member_id=member.id, rating=rating,
                              status=ProviderReviewStatus.PUBLISHED)
               for provider, rating in [(selected, 5), (other, 1)])
    db.commit()
    params = {"preset": "today", "provider_search": "Selected"}
    headers = _auth(seeded_admin[0])
    summary = client.get(f"{BASE}/summary", params=params, headers=headers).json()
    metrics = {x["key"]: x["value"] for x in summary["sections"]["reviews"]["metrics"]}
    assert metrics["provider_review_submissions"] == 1
    assert metrics["eligible_review_rating_count"] == 1
    assert metrics["eligible_review_rating_average"] == 5
    series = client.get(f"{BASE}/series", params={**params, "metric": "provider_review_submissions"},
                        headers=headers).json()
    assert sum(x["value"] for x in series["data"]) == 1
    breakdown = client.get(f"{BASE}/breakdowns", params={**params, "domain": "reviews"},
                           headers=headers).json()
    assert breakdown["groups"]["active_moderation_status"] == {"PUBLISHED": 1}
    assert breakdown["groups"]["eligible_ratings"] == {"average": 5, "count": 1}
    for sort, expected in [("name", ["Other Clinic", "Selected Clinic"]),
                           ("average_rating", ["Selected Clinic", "Other Clinic"])]:
        rank_params = {"preset": "today", "sort": sort,
                       "sort_direction": "asc" if sort == "name" else "desc"}
        ranking = client.get(f"{BASE}/provider-ranking", params=rank_params, headers=headers)
        assert ranking.status_code == 200, ranking.text
        assert [row["name"] for row in ranking.json()["data"]] == expected
        exported = client.get(f"{BASE}/export",
                              params={**rank_params, "dataset": "provider-ranking"},
                              headers=headers)
        rows = list(csv.reader(io.StringIO(exported.text)))
        header_index = next(i for i, row in enumerate(rows) if row[0] == "provider_id")
        name_index = rows[header_index].index("provider_name")
        assert [row[name_index] for row in rows[header_index + 1:]] == expected
    filtered = client.get(
        f"{BASE}/breakdowns",
        params={"domain": "reviews", "preset": "today", "rating": 5},
        headers=headers,
    ).json()
    assert filtered["groups"]["eligible_ratings"] == {"average": 5, "count": 1}
    leader = filtered["groups"]["top_reviewed_providers"][0]
    assert leader["name"] == "Selected Clinic"
    assert leader["rating_count"] == 1