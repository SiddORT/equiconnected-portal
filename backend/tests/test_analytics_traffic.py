"""Privacy and authorization contracts for prospective traffic ingestion."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request

from app.core.security import create_access_token, hash_password
from app.core.rate_limit import (
    _analytics_traffic_attempts,
    check_analytics_traffic_rate_limit,
)
from app.models.analytics_traffic import (
    TrafficPageCategoryDaily,
    TrafficProviderProfileDaily,
    TrafficTrackingReceipt,
    TrafficVisitorDaily,
)
from app.models.enums import ProviderStatus, ProviderType, PublicationStatus, VisitStability
from app.models.provider import Provider
from app.repositories.user_repository import UserRepository
from app.services.analytics_traffic_service import record_successful_view
from tests.conftest import TestingSessionLocal


def _member(db):
    repo = UserRepository(db)
    role = repo.get_role_by_name("horse_owner") or repo.create_role("horse_owner")
    user = repo.create_user(
        email="traffic-member@example.com",
        password_hash=hash_password("MemberPassword1"),
        role=role,
        roles=[role],
    )
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _provider(db, *, status=ProviderStatus.ACTIVE, publication=PublicationStatus.PUBLISHED):
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name="Traffic Clinic",
        visit_stability=VisitStability.STABLE_VISIT,
        status=status,
        publication_status=publication,
    )
    db.add(provider)
    db.commit()
    return provider


def test_public_page_views_are_allowlisted_and_retry_idempotent(client, db):
    first_key = uuid4()
    payload = {
        "category": "home",
        "navigation_key": str(first_key),
        "first_eligible_view_today": True,
    }

    assert client.post("/api/v1/public/traffic/page-view", json=payload).status_code == 204
    assert client.post("/api/v1/public/traffic/page-view", json=payload).status_code == 204
    assert client.post(
        "/api/v1/public/traffic/page-view",
        json={**payload, "navigation_key": str(uuid4()), "first_eligible_view_today": False},
    ).status_code == 204

    category = db.query(TrafficPageCategoryDaily).filter_by(category="home").one()
    visitor_day = db.query(TrafficVisitorDaily).one()
    assert category.page_views == 2
    assert visitor_day.estimated_visitors == 1

    for unsafe_payload in (
        {**payload, "category": "/admin/providers"},
        {**payload, "category": "provider_profile", "provider_id": str(uuid4())},
        {**payload, "raw_url": "/signup?token=secret"},
    ):
        response = client.post(
            "/api/v1/public/traffic/page-view",
            json={**unsafe_payload, "navigation_key": str(uuid4())},
        )
        assert response.status_code == 422


def test_member_traffic_requires_verification_and_discoverable_profiles(client, db):
    member = _member(db)
    headers = _headers(member)
    visible = _provider(db)
    unpublished = _provider(db, publication=PublicationStatus.UNPUBLISHED)
    endpoint = "/api/v1/member/providers/traffic-view"

    directory_payload = {
        "category": "provider_directory",
        "navigation_key": str(uuid4()),
        "first_eligible_view_today": True,
    }
    assert client.post(endpoint, json=directory_payload).status_code == 401
    assert client.post(endpoint, headers=headers, json=directory_payload).status_code == 204

    profile_payload = {
        "category": "provider_profile",
        "navigation_key": str(uuid4()),
        "first_eligible_view_today": False,
        "provider_id": str(visible.id),
    }
    assert client.post(endpoint, headers=headers, json=profile_payload).status_code == 204
    hidden_payload = {**profile_payload, "navigation_key": str(uuid4()), "provider_id": str(unpublished.id)}
    assert client.post(endpoint, headers=headers, json=hidden_payload).status_code == 404

    assert db.query(TrafficProviderProfileDaily).filter_by(provider_id=visible.id).one().profile_views == 1
    assert db.query(TrafficProviderProfileDaily).filter_by(provider_id=unpublished.id).count() == 0
    assert db.query(TrafficPageCategoryDaily).filter_by(category="provider_directory").one().page_views == 1


def test_member_page_tracking_rejects_unverified_accounts(client, db):
    member = _member(db)
    member.email_verified_at = None
    db.commit()

    response = client.post(
        "/api/v1/member/providers/traffic-view",
        headers=_headers(member),
        json={
            "category": "provider_directory",
            "navigation_key": str(uuid4()),
            "first_eligible_view_today": False,
        },
    )
    assert response.status_code == 403


def test_concurrent_distinct_navigation_increments_are_atomic(db):
    visit_day = date(2026, 9, 21)

    def record(key):
        session = TestingSessionLocal()
        try:
            return record_successful_view(
                session,
                visit_date=visit_day,
                category="animation",
                navigation_key=key,
                first_eligible_view_today=True,
            )
        finally:
            session.close()

    keys = [uuid4() for _ in range(12)]
    with ThreadPoolExecutor(max_workers=6) as workers:
        accepted = list(workers.map(record, keys))

    assert all(accepted)
    assert db.query(TrafficPageCategoryDaily).filter_by(
        visit_date=visit_day, category="animation"
    ).one().page_views == len(keys)
    assert db.query(TrafficVisitorDaily).filter_by(
        visit_date=visit_day
    ).one().estimated_visitors == len(keys)


def test_concurrent_retries_with_same_key_increment_only_once(db):
    visit_day = date(2026, 9, 21)
    navigation_key = uuid4()

    def record(_):
        session = TestingSessionLocal()
        try:
            return record_successful_view(
                session,
                visit_date=visit_day,
                category="home",
                navigation_key=navigation_key,
                first_eligible_view_today=True,
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=6) as workers:
        accepted = list(workers.map(record, range(12)))

    assert sum(accepted) == 1
    assert db.query(TrafficPageCategoryDaily).filter_by(
        visit_date=visit_day, category="home"
    ).one().page_views == 1
    assert db.query(TrafficVisitorDaily).filter_by(
        visit_date=visit_day
    ).one().estimated_visitors == 1


def test_receipt_cleanup_removes_at_most_two_hundred_expired_rows(db):
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            TrafficTrackingReceipt(
                navigation_key=uuid4(),
                created_at=now - timedelta(hours=50),
                expires_at=now - timedelta(hours=49),
            )
            for _ in range(205)
        ]
    )
    db.commit()

    record_successful_view(
        db,
        visit_date=date(2026, 9, 21),
        category="terms",
        navigation_key=uuid4(),
        first_eligible_view_today=False,
    )

    expired_count = db.query(TrafficTrackingReceipt).filter(
        TrafficTrackingReceipt.expires_at < datetime.now(timezone.utc)
    ).count()
    assert expired_count == 5


def test_traffic_ingestion_rate_limit_is_sixty_per_minute():
    remote_ip = f"analytics-rate-test-{uuid4()}"
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/public/traffic/page-view",
            "raw_path": b"/api/v1/public/traffic/page-view",
            "query_string": b"",
            "headers": [],
            "client": (remote_ip, 12345),
            "server": ("testserver", 80),
        }
    )
    try:
        for _ in range(60):
            check_analytics_traffic_rate_limit(request)
        with pytest.raises(HTTPException) as error:
            check_analytics_traffic_rate_limit(request)
        assert error.value.status_code == 429
        assert error.value.headers["Retry-After"] == "60"
    finally:
        _analytics_traffic_attempts.pop(remote_ip, None)