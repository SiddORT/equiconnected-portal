"""Provider-owned insights, prospective contact tracking, and coverage semantics."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.security import create_access_token, hash_password
from app.core.time_standards import local_midnight_utc, resolve_timezone, system_today
from app.models.analytics_traffic import (
    TrafficProviderProfileDaily,
    TrafficTrackingMetadata,
)
from app.models.enums import (
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderReviewStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.messaging import ProviderConversation
from app.models.provider import (
    DirectProviderPortalAccess,
    Provider,
    ProviderReview,
)
from app.models.provider_favorite import ProviderFavorite
from app.models.provider_insights import (
    ProviderContactClickDaily,
    ProviderContactClickReceipt,
    ProviderContactClickTrackingMetadata,
    ProviderInsightsConversationMetadata,
)
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.system_settings import SystemSettings
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.provider_insights_service import (
    CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE,
    InvalidContactClickEventError,
    ProviderInsightsPeriodError,
    ProviderInsightsService,
    cleanup_expired_contact_click_receipts_once,
    purge_expired_contact_click_receipts,
    record_contact_click,
    resolve_insights_period,
)
from tests.conftest import TestingSessionLocal, engine


def _uuid7(moment: datetime) -> UUID:
    milliseconds = int(moment.timestamp() * 1000)
    # UUIDv7: 48-bit Unix milliseconds, version 7, random_a, RFC variant, random_b.
    value = (
        (milliseconds << 80)
        | (7 << 76)
        | (0x321 << 64)
        | (0b10 << 62)
        | 0x123456789ABCDEF
    )
    return UUID(int=value)


def _account(db, *, email: str, role_name: str = "provider", verified=True):
    users = UserRepository(db)
    role = users.get_role_by_name(role_name) or users.create_role(role_name)
    user = users.create_user(
        email=email,
        password_hash=hash_password("InsightsPassword9"),
        role=role,
        roles=[role],
    )
    if verified:
        user.email_verified_at = datetime.now(timezone.utc)
    db.flush()
    return user


def _provider(db, *, name="Insights Clinic", status=ProviderStatus.ACTIVE,
              publication=PublicationStatus.PUBLISHED):
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
        status=status,
        publication_status=publication,
    )
    db.add(provider)
    db.flush()
    return provider


def _direct_owner(db, provider, *, email="insights-owner@example.com"):
    owner = _account(db, email=email)
    db.add(
        DirectProviderPortalAccess(
            provider_id=provider.id,
            user_id=owner.id,
            recipient_email=email,
        )
    )
    db.commit()
    return owner


def _headers(user):
    return {
        "Authorization": f"Bearer {create_access_token(subject=user.id)}"
    }


def _settings(db, timezone_name="UTC"):
    db.add(SystemSettings(id=1, timezone=timezone_name))
    db.commit()


def _coverage_rows(db, started_at):
    db.add_all(
        [
            TrafficTrackingMetadata(id=1, tracking_started_at=started_at),
            ProviderContactClickTrackingMetadata(
                id=1, tracking_started_at=started_at
            ),
            ProviderInsightsConversationMetadata(
                id=1, tracking_started_at=started_at
            ),
        ]
    )
    db.commit()


def test_provider_insights_report_uses_owner_listing_and_moderation_snapshot(client, db):
    timezone_name = "America/Los_Angeles"
    _settings(db, timezone_name)
    provider = _provider(db, name="Authorized Insights Clinic")
    owner = _direct_owner(db, provider)
    other_owner = _account(db, email="replacement-owner@example.com")
    visitor_one = _account(db, email="saved-one@example.com", role_name="horse_owner")
    visitor_two = _account(db, email="saved-two@example.com", role_name="horse_owner")
    conversation_members = [
        visitor_one,
        visitor_two,
        _account(db, email="conversation-three@example.com", role_name="horse_owner"),
        _account(db, email="conversation-four@example.com", role_name="horse_owner"),
    ]
    today = system_today(timezone_name)
    first = today - timedelta(days=6)
    start_at = local_midnight_utc(today - timedelta(days=40), timezone_name)
    _coverage_rows(db, start_at)

    db.add_all(
        [
            TrafficProviderProfileDaily(
                visit_date=today - timedelta(days=7),
                provider_id=provider.id,
                profile_views=4,
            ),
            TrafficProviderProfileDaily(
                visit_date=today,
                provider_id=provider.id,
                profile_views=6,
            ),
            ProviderContactClickDaily(
                click_date=today - timedelta(days=7),
                provider_id=provider.id,
                action="phone",
                click_count=2,
            ),
            ProviderContactClickDaily(
                click_date=today,
                provider_id=provider.id,
                action="website",
                click_count=4,
            ),
            ProviderFavorite(provider_id=provider.id, member_id=visitor_one.id),
            ProviderFavorite(provider_id=provider.id, member_id=visitor_two.id),
        ]
    )
    db.flush()
    for index, (member, created) in enumerate(
        zip(
            conversation_members,
            [today - timedelta(days=7), today, today, today],
            strict=True,
        ),
        start=1,
    ):
        db.add(
            ProviderConversation(
                member_user_id=member.id,
                provider_id=provider.id,
                provider_user_id=owner.id if index < 4 else other_owner.id,
                contact_snapshot_ciphertext="must not be read",
                contact_consent_at=local_midnight_utc(created, timezone_name),
                created_at=local_midnight_utc(created, timezone_name),
            )
        )
    other_listing = _provider(db, name="Another Listing")
    db.add(
        ProviderConversation(
            member_user_id=visitor_one.id,
            provider_id=other_listing.id,
            provider_user_id=owner.id,
            contact_snapshot_ciphertext="must not be read",
            contact_consent_at=local_midnight_utc(today, timezone_name),
            created_at=local_midnight_utc(today, timezone_name),
        )
    )

    db.add_all(
        [
            ProviderReview(
                provider_id=provider.id,
                member_id=visitor_one.id,
                rating=5,
                comment="Visible published review",
                comment_visible=True,
                status=ProviderReviewStatus.PUBLISHED,
            ),
            ProviderReview(
                provider_id=provider.id,
                member_id=visitor_two.id,
                rating=3,
                comment="Hidden but eligible rating",
                comment_visible=False,
                status=ProviderReviewStatus.HIDDEN,
            ),
        ]
    )
    pending_writer = _account(
        db, email="pending-reviewer@example.com", role_name="horse_owner"
    )
    deleted_writer = _account(
        db, email="deleted-reviewer@example.com", role_name="horse_owner"
    )
    db.add_all(
        [
            ProviderReview(
                provider_id=provider.id,
                member_id=pending_writer.id,
                rating=5,
                comment="Pending rating",
                comment_visible=True,
                status=ProviderReviewStatus.PENDING,
            ),
            ProviderReview(
                provider_id=provider.id,
                member_id=deleted_writer.id,
                rating=5,
                comment="Deleted rating",
                comment_visible=True,
                status=ProviderReviewStatus.PUBLISHED,
                deleted_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/api/v1/provider/portal/insights?preset=last_7_days",
        headers=_headers(owner),
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider_name"] == "Authorized Insights Clinic"
    assert result["timezone"] == timezone_name
    assert result["today"] == today.isoformat()
    assert result["period"] == {
        "date_from": first.isoformat(),
        "date_to": today.isoformat(),
        "preset": "last_7_days",
    }
    assert result["metrics"]["profile_views"]["value"] == 6
    assert result["metrics"]["profile_views"]["comparison"] == {
        "change_percent": 50.0,
        "previous_value": 4,
        "reason": None,
    }
    assert result["metrics"]["contact_clicks"]["value"] == 4
    assert result["metrics"]["contact_clicks"]["comparison"]["change_percent"] == 100
    assert result["metrics"]["new_conversations"]["value"] == 2
    assert result["metrics"]["new_conversations"]["comparison"]["previous_value"] == 1
    assert result["contact_breakdown"] == {"phone": 0, "email": 0, "website": 4}
    assert result["snapshot"] == {
        "saved_members": 2,
        "rating_count": 2,
        "visible_review_count": 1,
        "average_rating": 4.0,
    }
    assert len(result["trends"]) == 7
    assert result["trends"][-1]["profile_views"] == 6
    assert result["trends"][-1]["contact_clicks"] == 4
    assert set(result["metrics"]["profile_views"]) == {
        "value", "definition", "coverage", "comparison"
    }
    assert "contact_snapshot" not in str(result)
    assert client.get(
        f"/api/v1/provider/portal/insights?provider_id={other_listing.id}",
        headers=_headers(owner),
    ).status_code == 422


def test_provider_insights_denies_missing_ambiguous_and_non_provider_links(client, db):
    first_provider = _provider(db, name="First listing")
    owner = _direct_owner(db, first_provider, email="owned@example.com")
    second_provider = _provider(db, name="Second listing")
    db.add(
        ProviderRegistrationApplication(
            user_id=owner.id,
            provider_id=second_provider.id,
            provider_type=ProviderType.CLINIC,
            provider_name=second_provider.name,
            visit_stability=VisitStability.STABLE_VISIT,
            postal_code="12345",
            review_status=ProviderApplicationStatus.APPROVED,
        )
    )
    unlinked = _account(db, email="unlinked-provider@example.com")
    member = _account(db, email="member-insights@example.com", role_name="horse_owner")
    db.commit()

    assert client.get("/api/v1/provider/portal/insights").status_code == 401
    assert client.get(
        "/api/v1/provider/portal/insights", headers=_headers(member)
    ).status_code == 403
    assert client.get(
        "/api/v1/provider/portal/insights", headers=_headers(unlinked)
    ).status_code == 403
    assert client.get(
        "/api/v1/provider/portal/insights", headers=_headers(owner)
    ).status_code == 403


@pytest.mark.parametrize("ownership", ["invitation", "registration", "direct"])
def test_insights_reuses_all_explicit_ownership_paths(client, db, ownership):
    provider = _provider(db, name=f"{ownership.title()}-owned listing")
    email = f"{ownership}-insights@example.com"
    owner = _account(db, email=email)
    if ownership == "direct":
        db.add(
            DirectProviderPortalAccess(
                provider_id=provider.id,
                user_id=owner.id,
                recipient_email=email,
            )
        )
    elif ownership == "registration":
        db.add(
            ProviderRegistrationApplication(
                user_id=owner.id,
                provider_id=provider.id,
                provider_type=provider.provider_type,
                provider_name=provider.name,
                visit_stability=provider.visit_stability,
                postal_code="12345",
                review_status=ProviderApplicationStatus.APPROVED,
            )
        )
    else:
        now = datetime.now(timezone.utc)
        db.add(
            ProviderInvitation(
                provider_id=provider.id,
                provider_type=provider.provider_type,
                recipient_email=email,
                token_hash=f"completed-insights-{uuid4().hex}",
                status=InvitationStatus.COMPLETED,
                expires_at=now + timedelta(days=1),
                sent_at=now,
                completed_at=now,
                portal_user_id=owner.id,
                created_by=owner.id,
            )
        )
    db.commit()

    response = client.get(
        "/api/v1/provider/portal/insights", headers=_headers(owner)
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["provider_name"] == provider.name
    assert report["metrics"]["profile_views"]["value"] is None
    assert report["metrics"]["profile_views"]["coverage"]["status"] == "unknown"
    assert report["metrics"]["profile_views"]["comparison"]["reason"] == "coverage_unknown"
    assert report["contact_breakdown"] == {
        "phone": None, "email": None, "website": None
    }


@pytest.mark.parametrize(
    ("preset", "date_from", "date_to", "message"),
    [
        ("custom", None, None, "both"),
        ("custom", date(2026, 1, 2), date(2026, 1, 1), "after"),
        ("last_7_days", date(2026, 1, 1), None, "only"),
    ],
)
def test_insights_period_rejects_invalid_combinations(
    preset, date_from, date_to, message
):
    with pytest.raises(ProviderInsightsPeriodError, match=message):
        resolve_insights_period(
            preset=preset,
            today=date(2026, 1, 30),
            date_from=date_from,
            date_to=date_to,
        )


def test_insights_custom_period_caps_days_and_rejects_future():
    today = date(2026, 1, 30)
    assert resolve_insights_period(
        preset="last_30_days",
        today=today,
        date_from=None,
        date_to=None,
    ) == (today - timedelta(days=29), today)
    assert resolve_insights_period(
        preset="this_month",
        today=today,
        date_from=None,
        date_to=None,
    ) == (date(2026, 1, 1), today)
    assert resolve_insights_period(
        preset="custom",
        today=today,
        date_from=today - timedelta(days=365),
        date_to=today,
    ) == (today - timedelta(days=365), today)
    with pytest.raises(ProviderInsightsPeriodError, match="366"):
        resolve_insights_period(
            preset="custom",
            today=today,
            date_from=today - timedelta(days=366),
            date_to=today,
        )
    with pytest.raises(ProviderInsightsPeriodError, match="Future"):
        resolve_insights_period(
            preset="custom",
            today=today,
            date_from=today,
            date_to=today + timedelta(days=1),
        )


def test_metric_comparison_omits_partial_unknown_and_zero_baseline_percentages():
    full_coverage = {"status": "full", "from": "2026-01-01", "note": ""}
    zero_baseline = ProviderInsightsService._metric(
        value=5,
        definition="test metric",
        coverage=full_coverage,
        previous_value=0,
        comparison_coverage=True,
    )
    assert zero_baseline["comparison"] == {
        "change_percent": None,
        "previous_value": 0,
        "reason": "zero_previous_value",
    }

    partial = ProviderInsightsService._metric(
        value=5,
        definition="test metric",
        coverage={"status": "partial", "from": "2026-01-01", "note": ""},
        previous_value=2,
        comparison_coverage=True,
    )
    assert partial["comparison"]["change_percent"] is None
    assert partial["comparison"]["reason"] == "partial_coverage"

    unknown = ProviderInsightsService._metric(
        value=None,
        definition="test metric",
        coverage={"status": "unknown", "from": None, "note": ""},
        previous_value=None,
        comparison_coverage=False,
    )
    assert unknown["comparison"]["change_percent"] is None
    assert unknown["comparison"]["reason"] == "coverage_unknown"


def test_partial_rollout_day_is_not_full_coverage_and_unknown_is_not_zero(db):
    timezone_name = "America/St_Johns"
    today = system_today(timezone_name)
    boundary_day = today - timedelta(days=3)
    noon_local = datetime.combine(
        boundary_day, time(12), tzinfo=resolve_timezone(timezone_name)
    )
    coverage = ProviderInsightsService._coverage(
        boundary_day, today, noon_local.astimezone(timezone.utc), timezone_name
    )
    assert coverage["status"] == "partial"
    assert coverage["from"] == boundary_day.isoformat()
    midnight_boundary = datetime.combine(
        boundary_day, time.min, tzinfo=resolve_timezone(timezone_name)
    )
    rollout_day = ProviderInsightsService._coverage(
        boundary_day,
        boundary_day,
        midnight_boundary.astimezone(timezone.utc),
        timezone_name,
    )
    assert rollout_day["status"] == "partial"
    before = ProviderInsightsService._coverage(
        boundary_day - timedelta(days=4),
        boundary_day - timedelta(days=1),
        noon_local.astimezone(timezone.utc),
        timezone_name,
    )
    assert before["status"] == "unavailable"
    unknown = ProviderInsightsService._coverage(
        boundary_day, today, None, timezone_name
    )
    assert unknown == {
        "status": "unknown",
        "from": None,
        "note": "A durable collection boundary is not available.",
    }


def test_conversation_rollout_boundary_excludes_earlier_same_day_rows(client, db):
    _settings(db, "UTC")
    provider = _provider(db, name="Conversation Boundary Clinic")
    owner = _direct_owner(db, provider)
    before_member = _account(db, email="before-boundary@example.com")
    after_member = _account(db, email="after-boundary@example.com")
    today = datetime.now(timezone.utc).date()
    boundary = datetime.combine(today, time(12), tzinfo=timezone.utc)
    db.add(
        ProviderInsightsConversationMetadata(
            id=1, tracking_started_at=boundary
        )
    )
    db.add_all(
        [
            ProviderConversation(
                member_user_id=before_member.id,
                provider_id=provider.id,
                provider_user_id=owner.id,
                contact_snapshot_ciphertext="private",
                contact_consent_at=boundary - timedelta(hours=1),
                created_at=boundary - timedelta(hours=1),
            ),
            ProviderConversation(
                member_user_id=after_member.id,
                provider_id=provider.id,
                provider_user_id=owner.id,
                contact_snapshot_ciphertext="private",
                contact_consent_at=boundary + timedelta(hours=1),
                created_at=boundary + timedelta(hours=1),
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/api/v1/provider/portal/insights"
        f"?preset=custom&date_from={today.isoformat()}&date_to={today.isoformat()}",
        headers=_headers(owner),
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["metrics"]["new_conversations"]["value"] == 1
    assert report["metrics"]["new_conversations"]["coverage"]["status"] == "partial"
    assert report["metrics"]["new_conversations"]["comparison"]["change_percent"] is None


def test_member_contact_click_is_verified_discoverable_strict_and_retry_safe(
    client, db
):
    member = _account(db, email="verified-clicker@example.com", role_name="horse_owner")
    provider = _provider(db, name="Tracked Clinic")
    stale = _provider(db, name="Withdrawn Clinic", publication=PublicationStatus.UNPUBLISHED)
    timestamp = datetime.now(timezone.utc)
    event_key = _uuid7(timestamp)
    path = f"/api/v1/member/providers/{provider.id}/contact-click"
    payload = {"action": "phone", "event_key": str(event_key)}
    db.add(
        ProviderContactClickTrackingMetadata(
            id=1,
            tracking_started_at=timestamp - timedelta(minutes=1),
        )
    )
    db.commit()

    assert client.post(path, headers=_headers(member), json=payload).status_code == 204
    assert client.post(path, headers=_headers(member), json=payload).status_code == 204
    second_key = _uuid7(timestamp + timedelta(milliseconds=1))
    assert client.post(
        path,
        headers=_headers(member),
        json={"action": "website", "event_key": str(second_key)},
    ).status_code == 204
    assert client.post(
        f"/api/v1/member/providers/{stale.id}/contact-click",
        headers=_headers(member),
        json={"action": "phone", "event_key": str(_uuid7(timestamp))},
    ).status_code == 404
    assert client.post(
        path,
        headers=_headers(member),
        json={"action": "sms", "event_key": str(_uuid7(timestamp))},
    ).status_code == 422
    assert client.post(
        path,
        headers=_headers(member),
        json={**payload, "unexpected": "not allowed"},
    ).status_code == 422
    assert client.post(path, json=payload).status_code == 401

    member.email_verified_at = None
    db.commit()
    assert client.post(path, headers=_headers(member), json=payload).status_code == 403
    db.refresh(member)
    member.email_verified_at = timestamp
    db.commit()

    totals = {
        row.action: row.click_count
        for row in db.query(ProviderContactClickDaily).filter_by(
            provider_id=provider.id
        )
    }
    assert totals == {"phone": 1, "website": 1}
    receipt = db.query(ProviderContactClickReceipt).filter_by(event_key=event_key).one()
    assert set(receipt.__table__.columns.keys()) == {
        "event_key", "created_at", "expires_at"
    }
    assert receipt.expires_at <= timestamp + timedelta(hours=48, minutes=5)

    stale_key = _uuid7(datetime.now(timezone.utc) - timedelta(hours=49))
    assert client.post(
        path,
        headers=_headers(member),
        json={"action": "phone", "event_key": str(stale_key)},
    ).status_code == 422


def test_contact_click_concurrent_same_uuidv7_counts_once(db):
    provider = _provider(db)
    provider_id = provider.id
    now = datetime.now(timezone.utc)
    db.add(
        ProviderContactClickTrackingMetadata(
            id=1,
            tracking_started_at=now - timedelta(minutes=1),
        )
    )
    db.commit()
    event_key = _uuid7(now)

    def record(_):
        session = TestingSessionLocal()
        try:
            return record_contact_click(
                session,
                provider_id=provider_id,
                action="email",
                event_key=event_key,
                timezone_name="UTC",
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=6) as workers:
        accepted = list(workers.map(record, range(12)))
    assert sum(accepted) == 1
    assert db.query(ProviderContactClickDaily).filter_by(
        provider_id=provider.id, action="email"
    ).one().click_count == 1


def test_contact_click_day_uses_uuid_event_time_in_system_timezone(db):
    provider = _provider(db)
    event_time = datetime(2026, 5, 2, 2, 30, tzinfo=timezone.utc)
    db.add(
        ProviderContactClickTrackingMetadata(
            id=1, tracking_started_at=event_time - timedelta(minutes=1)
        )
    )
    db.commit()
    assert record_contact_click(
        db,
        provider_id=provider.id,
        action="phone",
        event_key=_uuid7(event_time),
        timezone_name="America/Los_Angeles",
        now=event_time + timedelta(minutes=1),
    )
    aggregate = db.query(ProviderContactClickDaily).one()
    assert aggregate.click_date == date(2026, 5, 1)


def test_contact_receipt_purge_is_bounded_and_does_not_change_counts(
    db, monkeypatch
):
    provider = _provider(db)
    now = datetime.now(timezone.utc)
    click = ProviderContactClickDaily(
        click_date=now.date(),
        provider_id=provider.id,
        action="email",
        click_count=9,
        created_at=now,
        updated_at=now,
    )
    expired_receipts = [
        ProviderContactClickReceipt(
            event_key=uuid4(),
            created_at=now - timedelta(hours=50),
            expires_at=now - timedelta(seconds=offset + 1),
        )
        for offset in range(3)
    ]
    live_receipt = ProviderContactClickReceipt(
        event_key=uuid4(),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db.add_all([click, *expired_receipts, live_receipt])
    db.commit()

    assert purge_expired_contact_click_receipts(
        db, now=now, batch_size=2
    ) == 2
    assert db.query(ProviderContactClickReceipt).count() == 2
    assert db.query(ProviderContactClickDaily).one().click_count == 9
    db.rollback()
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    assert cleanup_expired_contact_click_receipts_once(batch_size=2) == 1
    assert db.query(ProviderContactClickReceipt).count() == 1
    assert db.query(ProviderContactClickDaily).one().click_count == 9
    with pytest.raises(ValueError, match="batch_size"):
        purge_expired_contact_click_receipts(
            db,
            now=now,
            batch_size=CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE + 1,
        )


@pytest.mark.asyncio
async def test_contact_receipt_cleanup_worker_runs_independently_and_cancels(
    db, monkeypatch,
):
    import app.services.provider_insights_service as insights_service
    from app.main import _cleanup_provider_contact_click_receipts

    provider = _provider(db)
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            ProviderContactClickDaily(
                click_date=now.date(),
                provider_id=provider.id,
                action="phone",
                click_count=11,
                created_at=now,
                updated_at=now,
            ),
            ProviderContactClickReceipt(
                event_key=uuid4(),
                created_at=now - timedelta(hours=50),
                expires_at=now - timedelta(seconds=1),
            ),
        ]
    )
    db.commit()

    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    called = Event()
    cleanups = []
    original_cleanup = insights_service.cleanup_expired_contact_click_receipts_once

    def cleanup_once(*, batch_size):
        cleanups.append(
            (
                batch_size,
                original_cleanup(batch_size=batch_size),
            )
        )
        called.set()

    monkeypatch.setattr(
        insights_service,
        "cleanup_expired_contact_click_receipts_once",
        cleanup_once,
    )
    monkeypatch.setattr(
        insights_service, "CONTACT_CLICK_RECEIPT_CLEANUP_INTERVAL_SECONDS", 3600
    )
    task = asyncio.create_task(_cleanup_provider_contact_click_receipts())
    try:
        assert await asyncio.to_thread(called.wait, 2)
        assert cleanups == [(CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE, 1)]
        db.rollback()
        assert db.query(ProviderContactClickReceipt).count() == 0
        assert db.query(ProviderContactClickDaily).one().click_count == 11
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_contact_click_event_key_rejects_non_v7_and_expired():
    moment = datetime.now(timezone.utc)
    with pytest.raises(InvalidContactClickEventError, match="UUIDv7"):
        record_contact_click(
            None,
            provider_id=uuid4(),
            action="phone",
            event_key=uuid4(),
            timezone_name="UTC",
            now=moment,
        )
    with pytest.raises(InvalidContactClickEventError, match="retry window"):
        record_contact_click(
            None,
            provider_id=uuid4(),
            action="phone",
            event_key=_uuid7(moment - timedelta(hours=48)),
            timezone_name="UTC",
            now=moment,
        )


def test_contact_duplicate_noop_rolls_back_request_transaction(db):
    provider = _provider(db)
    now = datetime.now(timezone.utc)
    db.add(
        ProviderContactClickTrackingMetadata(
            id=1, tracking_started_at=now - timedelta(minutes=1)
        )
    )
    db.commit()
    event_key = _uuid7(now)
    assert record_contact_click(
        db,
        provider_id=provider.id,
        action="phone",
        event_key=event_key,
        timezone_name="UTC",
        now=now,
    )
    assert not db.in_transaction()
    assert not record_contact_click(
        db,
        provider_id=provider.id,
        action="phone",
        event_key=event_key,
        timezone_name="UTC",
        now=now + timedelta(seconds=1),
    )
    assert not db.in_transaction()


def test_provider_insights_migration_roundtrip_and_canonical_head():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic/versions/d353c0353201_add_provider_performance_insights.py"
    )
    spec = spec_from_file_location("provider_insights_migration", migration_path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    tables = {
        "provider_contact_click_daily",
        "provider_contact_click_tracking_metadata",
        "provider_insights_conversation_metadata",
        "provider_contact_click_receipts",
    }
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            from alembic.migration import MigrationContext
            from alembic.operations import Operations
            from sqlalchemy import inspect

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
                assert tables.isdisjoint(inspect(connection).get_table_names())
                migration.upgrade()
                assert tables <= set(inspect(connection).get_table_names())
        finally:
            transaction.rollback()

    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["d353c0353201"]