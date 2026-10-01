"""Admin analytics report, scope, privacy, and export contract coverage."""
import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.security import create_access_token
from app.core.time_standards import system_today
from app.models.contact_enquiry import ContactEnquiry
from app.models.enums import (
    InvitationStatus,
    MemberFeedbackStatus,
    ProviderApplicationStatus,
    ProviderReviewStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.member_feedback import MemberFeedback
from app.models.provider import Provider, ProviderLocation, ProviderReview
from app.models.provider_favorite import ProviderFavorite
from app.models.provider_review_action import ProviderReviewAction
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.subscriber import Subscriber
from app.models.analytics_traffic import (
    TrafficPageCategoryDaily,
    TrafficProviderProfileDaily,
    TrafficTrackingMetadata,
    TrafficVisitorDaily,
)
from app.models.user import UserRole
from app.repositories.user_repository import UserRepository

BASE = "/api/v1/admin/analytics"


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _create_member(db, *, email: str, role_names=("horse_owner",), created_at=None):
    users = UserRepository(db)
    roles = [
        users.get_role_by_name(name) or users.create_role(name, name)
        for name in role_names
    ]
    member = users.create_user(
        email=email,
        password_hash="not-used-in-analytics",
        role=roles[0],
        roles=roles,
    )
    if created_at is not None:
        member.created_at = created_at
    return member


def _provider(db, *, name="Analytics Clinic", status=ProviderStatus.ACTIVE):
    item = Provider(
        provider_type=ProviderType.CLINIC,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
        status=status,
        publication_status=PublicationStatus.PUBLISHED,
    )
    db.add(item)
    db.flush()
    return item


class TestAnalyticsAuthorizationAndFilters:
    def test_reports_require_admin(self, client, db, seeded_admin):
        assert client.get(f"{BASE}/summary").status_code == 401
        admin, _ = seeded_admin
        assert client.get(f"{BASE}/summary", headers=_auth(admin)).status_code == 200

        repository = UserRepository(db)
        visitor_role = repository.get_role_by_name("visitor") or repository.create_role("visitor")
        visitor = repository.create_user(
            "analytics-visitor@example.com",
            "not-used-in-analytics",
            visitor_role,
        )
        db.commit()
        assert client.get(f"{BASE}/summary", headers=_auth(visitor)).status_code == 403
        assert client.get(
            f"{BASE}/export",
            params={"dataset": "breakdowns", "domain": "subscribers"},
            headers=_auth(visitor),
        ).status_code == 403

    def test_custom_range_validation_returns_422_not_server_error(
        self, client, seeded_admin
    ):
        admin, _ = seeded_admin
        headers = _auth(admin)
        missing_end = client.get(
            f"{BASE}/summary",
            params={"preset": "custom", "date_from": "2026-01-01"},
            headers=headers,
        )
        assert missing_end.status_code == 422
        reversed_range = client.get(
            f"{BASE}/summary",
            params={
                "preset": "custom",
                "date_from": "2026-01-02",
                "date_to": "2026-01-01",
            },
            headers=headers,
        )
        assert reversed_range.status_code == 422
        non_custom_dates = client.get(
            f"{BASE}/summary",
            params={
                "preset": "last_7_days",
                "date_from": "2026-01-01",
                "date_to": "2026-01-02",
            },
            headers=headers,
        )
        assert non_custom_dates.status_code == 422


class TestAnalyticsReportConsistency:
    def test_enquiry_summary_series_and_breakdown_share_selected_period(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        today = system_today("UTC")
        first = today - timedelta(days=1)
        db.add_all(
            [
                ContactEnquiry(
                    name="Private Contact",
                    email="private-contact@example.com",
                    enquiry_type="general",
                    message="Do not export this message.",
                    submitted_at=datetime.combine(first, datetime.min.time(), timezone.utc),
                ),
                ContactEnquiry(
                    name="Private Contact Two",
                    email="private-two@example.com",
                    enquiry_type="listing",
                    message="Do not export this either.",
                    submitted_at=datetime.combine(today, datetime.min.time(), timezone.utc),
                ),
            ]
        )
        db.commit()
        params = {
            "preset": "custom",
            "date_from": first.isoformat(),
            "date_to": today.isoformat(),
        }
        headers = _auth(admin)

        summary = client.get(f"{BASE}/summary", params=params, headers=headers)
        series = client.get(
            f"{BASE}/series",
            params={**params, "metric": "contact_enquiries"},
            headers=headers,
        )
        breakdown = client.get(
            f"{BASE}/breakdowns",
            params={**params, "domain": "enquiries"},
            headers=headers,
        )
        assert summary.status_code == series.status_code == breakdown.status_code == 200
        metric = next(
            item
            for item in summary.json()["sections"]["engagement"]["metrics"]
            if item["key"] == "contact_enquiries"
        )
        assert metric["value"] == 2
        assert sum(point["value"] for point in series.json()["data"]) == 2
        assert sum(breakdown.json()["groups"]["enquiry_type"].values()) == 2
        assert metric["comparison"]["available"] is False
        assert metric["comparison"]["unavailable_reason"] == "coverage_unknown"

    def test_member_cohort_counts_dual_roles_once_and_excludes_admin(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        today = system_today("UTC")
        member = _create_member(
            db,
            email="dual-role@example.com",
            role_names=("horse_owner", "stable_manager"),
            created_at=datetime.combine(today, datetime.min.time(), timezone.utc),
        )
        member.email_verified_at = datetime.now(timezone.utc)
        member.last_name = "Member"
        db.add(
            UserRole(
                user_id=admin.id,
                role_id=UserRepository(db).get_role_by_name("horse_owner").id,
            )
        )
        db.commit()

        result = client.get(
            f"{BASE}/breakdowns",
            params={
                "domain": "registrations",
                "preset": "custom",
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
            headers=_auth(admin),
        )
        assert result.status_code == 200, result.text
        cohort = result.json()["groups"]["selected_cohort"]
        assert cohort["total"] == 1
        assert cohort["roles"] == {"both": 1}
        assert cohort["role_assignments"] == {
            "horse_owner": 1,
            "stable_manager": 1,
        }
        summary = client.get(
            f"{BASE}/summary",
            params={
                "preset": "custom",
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
            headers=_auth(admin),
        )
        series = client.get(
            f"{BASE}/series",
            params={
                "preset": "custom",
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
                "metric": "public_member_registrations",
            },
            headers=_auth(admin),
        )
        assert summary.status_code == series.status_code == 200
        registration = next(
            item
            for item in summary.json()["sections"]["registrations"]["metrics"]
            if item["key"] == "public_member_registrations"
        )
        assert registration["value"] == 1
        assert sum(point["value"] for point in series.json()["data"]) == 1

    def test_subscriber_counts_series_and_category_breakdown_are_consistent(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        today = system_today("UTC")
        yesterday = today - timedelta(days=1)
        db.add_all(
            [
                Subscriber(
                    email="owner-subscriber@example.com",
                    registration_type="HORSE_OWNER",
                    submitted_at=datetime.combine(
                        yesterday, datetime.min.time(), timezone.utc
                    ),
                ),
                Subscriber(
                    email="clinic-subscriber@example.com",
                    registration_type="CLINIC",
                    submitted_at=datetime.combine(
                        today, datetime.min.time(), timezone.utc
                    ),
                ),
            ]
        )
        db.commit()
        params = {
            "preset": "custom",
            "date_from": yesterday.isoformat(),
            "date_to": today.isoformat(),
        }
        headers = _auth(admin)
        summary = client.get(f"{BASE}/summary", params=params, headers=headers)
        series = client.get(
            f"{BASE}/series",
            params={**params, "metric": "new_subscribers"},
            headers=headers,
        )
        breakdown = client.get(
            f"{BASE}/breakdowns",
            params={**params, "domain": "subscribers"},
            headers=headers,
        )
        assert summary.status_code == series.status_code == breakdown.status_code == 200
        metric = next(
            item
            for item in summary.json()["sections"]["engagement"]["metrics"]
            if item["key"] == "new_subscribers"
        )
        assert metric["value"] == 2
        assert sum(point["value"] for point in series.json()["data"]) == 2
        assert breakdown.json()["groups"]["subscriber_type"] == {
            "CLINIC": 1,
            "HORSE_OWNER": 1,
        }

    def test_application_decisions_and_invitation_status_compatibility(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        today = system_today("UTC")
        yesterday = today - timedelta(days=1)
        today_stamp = datetime.combine(today, datetime.min.time(), timezone.utc)
        yesterday_stamp = datetime.combine(yesterday, datetime.min.time(), timezone.utc)
        applications = []
        for index, status in enumerate(
            (ProviderApplicationStatus.APPROVED, ProviderApplicationStatus.REJECTED)
        ):
            member = _create_member(
                db, email=f"provider-app-user-{index}@example.com"
            )
            applications.append(
                ProviderRegistrationApplication(
                    user_id=member.id,
                    provider_type=ProviderType.CLINIC,
                    provider_name=f"Application {index}",
                    visit_stability=VisitStability.STABLE_VISIT,
                    postal_code="78701",
                    review_status=status,
                    created_at=yesterday_stamp,
                    reviewed_at=today_stamp,
                    reviewed_by_user_id=admin.id,
                )
            )
        db.add_all(applications)
        db.flush()
        invitations = []
        statuses = (
            InvitationStatus.COMPLETED,
            InvitationStatus.CANCELLED,
            InvitationStatus.EXPIRED,
        )
        for index, status in enumerate(statuses):
            invitations.append(
                ProviderInvitation(
                    provider_type=ProviderType.CLINIC,
                    recipient_email=f"recipient-{index}@example.com",
                    token_hash=f"{index + 1:064x}",
                    status=status,
                    expires_at=today_stamp + timedelta(days=14),
                    sent_at=today_stamp,
                    created_by=admin.id,
                    created_at=yesterday_stamp,
                )
            )
        db.add_all(invitations)
        db.commit()

        headers = _auth(admin)
        params = {
            "preset": "custom",
            "date_from": yesterday.isoformat(),
            "date_to": today.isoformat(),
        }
        summary = client.get(f"{BASE}/summary", params=params, headers=headers)
        applications_report = client.get(
            f"{BASE}/breakdowns",
            params={**params, "domain": "applications"},
            headers=headers,
        )
        invitation_report = client.get(
            f"{BASE}/breakdowns",
            params={**params, "domain": "invitations"},
            headers=headers,
        )
        decision_series = client.get(
            f"{BASE}/series",
            params={**params, "metric": "provider_application_decisions"},
            headers=headers,
        )
        sent_series = client.get(
            f"{BASE}/series",
            params={**params, "metric": "provider_invitations_sent"},
            headers=headers,
        )
        assert all(
            response.status_code == 200
            for response in (
                summary,
                applications_report,
                invitation_report,
                decision_series,
                sent_series,
            )
        )
        metrics = summary.json()["sections"]["applications"]["metrics"]
        values = {item["key"]: item["value"] for item in metrics}
        assert values["provider_applications"] == 2
        assert values["provider_application_decisions"] == 2
        assert values["provider_invitations_created"] == 3
        assert values["provider_invitations_sent"] == 3
        assert sum(point["value"] for point in decision_series.json()["data"]) == 2
        assert sum(point["value"] for point in sent_series.json()["data"]) == 3
        assert applications_report.json()["groups"]["submitted_cohort_current_status"] == {
            "APPROVED": 1,
            "REJECTED": 1,
        }
        assert invitation_report.json()["groups"]["created_cohort_current_status"] == {
            "CANCELLED": 1,
            "COMPLETED": 1,
            "EXPIRED": 1,
        }
        legacy = summary.json()["sections"]["applications"][
            "legacy_compatible_invitation_totals"
        ]
        assert legacy["accepted"] == 1
        assert legacy["cancelled_or_expired"] == 2
        assert "not claims of recipient rejection" in legacy["note"]

    def test_traffic_coverage_and_equal_period_comparison(self, client, db, seeded_admin):
        admin, _ = seeded_admin
        today = system_today("UTC")
        yesterday = today - timedelta(days=1)
        today_stamp = datetime.combine(today, datetime.min.time(), timezone.utc)
        provider = _provider(db)
        db.add(
            TrafficTrackingMetadata(
                id=1,
                tracking_started_at=datetime.combine(
                    yesterday, datetime.min.time(), timezone.utc
                ),
            )
        )
        db.add_all(
            [
                TrafficPageCategoryDaily(
                    visit_date=yesterday, category="home", page_views=3
                ),
                TrafficPageCategoryDaily(
                    visit_date=today, category="home", page_views=5
                ),
                TrafficPageCategoryDaily(
                    visit_date=yesterday,
                    category="provider_directory",
                    page_views=2,
                ),
                TrafficPageCategoryDaily(
                    visit_date=today, category="provider_directory", page_views=4
                ),
                TrafficVisitorDaily(visit_date=yesterday, estimated_visitors=10),
                TrafficVisitorDaily(visit_date=today, estimated_visitors=15),
                TrafficProviderProfileDaily(
                    visit_date=yesterday, provider_id=provider.id, profile_views=1
                ),
                TrafficProviderProfileDaily(
                    visit_date=today, provider_id=provider.id, profile_views=3
                ),
            ]
        )
        db.commit()
        summary = client.get(
            f"{BASE}/summary",
            params={
                "preset": "custom",
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
            headers=_auth(admin),
        )
        assert summary.status_code == 200, summary.text
        traffic = summary.json()["sections"]["traffic"]
        metrics = {item["key"]: item for item in traffic["metrics"]}
        assert metrics["website_page_views"]["value"] == 9
        assert metrics["website_page_views"]["comparison"]["change_percent"] == 80.0
        assert metrics["estimated_visitor_days"]["value"] == 15
        assert metrics["estimated_visitor_days"]["comparison"]["change_percent"] == 50.0
        assert metrics["directory_views"]["value"] == 4
        assert metrics["provider_profile_views"]["value"] == 3
        assert traffic["coverage"] == {
            "tracked_since": yesterday.isoformat(),
            "available": True,
            "partial": False,
        }

        partial = client.get(
            f"{BASE}/series",
            params={
                "preset": "custom",
                "date_from": (yesterday - timedelta(days=1)).isoformat(),
                "date_to": today.isoformat(),
                "metric": "website_page_views",
            },
            headers=_auth(admin),
        )
        assert partial.status_code == 200
        assert partial.json()["partial_coverage"] is True
        assert [point["bucket"] for point in partial.json()["data"]] == [
            yesterday.isoformat(),
            today.isoformat(),
        ]

    def test_local_calendar_bounds_respect_daylight_saving_time(self, db):
        from app.models.system_settings import SystemSettings
        from app.repositories.admin_analytics_repository import AdminAnalyticsRepository
        from app.services.admin_analytics_service import AdminAnalyticsService
        from app.schemas.admin_analytics import AnalyticsFilters, AnalyticsPreset

        settings = SystemSettings(timezone="America/Los_Angeles")
        db.add(settings)
        db.commit()
        service = AdminAnalyticsService(AdminAnalyticsRepository(db))
        envelope = service._envelope(
            AnalyticsFilters(
                preset=AnalyticsPreset.CUSTOM,
                date_from=date(2026, 3, 8),
                date_to=date(2026, 3, 8),
            )
        )
        assert envelope["_start"] == datetime(2026, 3, 8, 8, tzinfo=timezone.utc)
        assert envelope["_end"] == datetime(2026, 3, 9, 7, tzinfo=timezone.utc)

    def test_provider_ranking_paginates_deterministically_without_location_fanout(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        today = system_today("UTC")
        alpha = _provider(db, name="Alpha Clinic")
        beta = _provider(db, name="Beta Clinic")
        db.add_all(
            [
                ProviderLocation(
                    provider_id=alpha.id,
                    address_line_1="Main Street 1",
                    city="Austin",
                    country="United States",
                    is_primary=True,
                ),
                ProviderLocation(
                    provider_id=alpha.id,
                    address_line_1="Main Street 2",
                    city="Austin",
                    country="United States",
                    is_primary=False,
                ),
                ProviderLocation(
                    provider_id=beta.id,
                    address_line_1="Main Street 3",
                    city="Austin",
                    country="United States",
                    is_primary=True,
                ),
            ]
        )
        db.commit()
        params = {
            "preset": "custom",
            "date_from": today.isoformat(),
            "date_to": today.isoformat(),
            "city": "austin",
            "country": "United States",
            "sort": "name",
            "sort_direction": "asc",
            "page_size": 1,
        }
        headers = _auth(admin)
        first = client.get(f"{BASE}/provider-ranking", params=params, headers=headers)
        second = client.get(
            f"{BASE}/provider-ranking",
            params={**params, "page": 2},
            headers=headers,
        )
        assert first.status_code == second.status_code == 200
        assert first.json()["meta"]["total"] == 2
        assert first.json()["meta"]["total_pages"] == 2
        assert first.json()["data"][0]["name"] == "Alpha Clinic"
        assert second.json()["data"][0]["name"] == "Beta Clinic"
        assert first.json()["data"][0]["profile_views"] is None
        filtered = client.get(
            f"{BASE}/provider-ranking",
            params={**params, "provider_search": "Beta"},
            headers=headers,
        )
        assert filtered.status_code == 200
        assert filtered.json()["meta"]["total"] == 1
        assert filtered.json()["data"][0]["name"] == "Beta Clinic"

    def test_review_and_feedback_eligibility_and_withdrawal_rules(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        today = system_today("UTC")
        stamp = datetime.combine(today, datetime.min.time(), timezone.utc)
        provider = _provider(db)
        reviews = []
        for index, (review_status, rating, deleted_at) in enumerate(
            [
                (ProviderReviewStatus.PUBLISHED, 4, None),
                (ProviderReviewStatus.HIDDEN, 5, None),
                (ProviderReviewStatus.PENDING, 1, None),
                (ProviderReviewStatus.REJECTED, 2, None),
                (ProviderReviewStatus.PUBLISHED, 3, stamp),
            ]
        ):
            member = _create_member(
                db,
                email=f"review-member-{index}@example.com",
            )
            reviews.append(
                ProviderReview(
                    provider_id=provider.id,
                    member_id=member.id,
                    rating=rating,
                    comment="Private content",
                    comment_visible=True,
                    status=review_status,
                    version=1,
                    created_at=stamp,
                    updated_at=stamp,
                    deleted_at=deleted_at,
                )
            )
        db.add_all(reviews)
        db.flush()
        db.add(
            ProviderReviewAction(
                review_id=reviews[0].id,
                actor_name="Member",
                actor_email="private@example.com",
                actor_type="member",
                action="member_edited",
                version=2,
                content_snapshot={"comment": "must not be exported"},
                created_at=stamp,
            )
        )
        db.add_all(
            [
                MemberFeedback(
                    submitter_name="Private Person",
                    submitter_email="private-feedback@example.com",
                    category="Website / App",
                    subject="Private",
                    rating=4,
                    message="Private feedback body",
                    status=MemberFeedbackStatus.PENDING,
                    submitted_at=stamp,
                    created_at=stamp,
                    updated_at=stamp,
                ),
                MemberFeedback(
                    submitter_name="Private Person Two",
                    submitter_email="private-feedback-two@example.com",
                    category="Suggestion",
                    rating=5,
                    message="Withdrawn feedback body",
                    status=MemberFeedbackStatus.PENDING,
                    submitted_at=stamp,
                    withdrawn_at=stamp,
                    created_at=stamp,
                    updated_at=stamp,
                ),
            ]
        )
        db.commit()

        headers = _auth(admin)
        report = client.get(
            f"{BASE}/breakdowns",
            params={
                "domain": "reviews",
                "preset": "custom",
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
            headers=headers,
        )
        feedback = client.get(f"{BASE}/breakdowns", params={"domain": "feedback"}, headers=headers)
        assert report.status_code == feedback.status_code == 200
        groups = report.json()["groups"]
        assert groups["eligible_ratings"] == {"average": 4.5, "count": 2}
        assert groups["star_distribution"] == {"1": 0, "2": 0, "3": 0, "4": 1, "5": 1}
        assert groups["submitted_cohort_retained_deleted_history"]["count"] == 1
        assert groups["period_actions"]["member_edited"] == 1
        feedback_groups = feedback.json()["groups"]
        assert feedback_groups["ratings"] == {
            "average": 4.0,
            "count": 1,
            "distribution": {"1": 0, "2": 0, "3": 0, "4": 1, "5": 0},
        }
        assert feedback_groups["current_withdrawn"]["count"] == 1
        assert "Private feedback body" not in feedback.text
        assert "private-feedback@example.com" not in feedback.text


class TestAnalyticsExports:
    def test_breakdown_export_is_rectangular_and_includes_scope_metadata(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        today = system_today("UTC")
        db.add(
            Subscriber(
                email="must-not-export@example.com",
                registration_type="HORSE_OWNER",
                submitted_at=datetime.combine(today, datetime.min.time(), timezone.utc),
            )
        )
        db.commit()
        response = client.get(
            f"{BASE}/export",
            params={
                "dataset": "breakdowns",
                "domain": "subscribers",
                "preset": "custom",
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
            headers=_auth(admin),
        )
        assert response.status_code == 200, response.text
        records = list(csv.reader(io.StringIO(response.text)))
        assert ["# timezone", "UTC", ""] in records
        assert any(record[0] == "# date_from" for record in records)
        assert any(record[0] == "# definitions" for record in records)
        header_index = records.index(["section", "metric", "value"])
        assert all(len(record) == 3 for record in records[:header_index + 1])
        assert all(len(record) == 3 for record in records[header_index:])
        assert "must-not-export@example.com" not in response.text

    def test_provider_ranking_export_is_consistent_and_formula_safe(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        today = system_today("UTC")
        _provider(db, name="=HYPERLINK(\"https://example.invalid\")")
        db.add(
            ProviderLocation(
                provider_id=db.query(Provider).one().id,
                address_line_1="One Stable Way",
                city="Austin",
                country="United States",
                latitude=Decimal("30.000000"),
                longitude=Decimal("-97.000000"),
                is_primary=True,
            )
        )
        db.commit()
        headers = _auth(admin)
        table = client.get(
            f"{BASE}/provider-ranking",
            params={"preset": "custom", "date_from": today.isoformat(), "date_to": today.isoformat()},
            headers=headers,
        )
        exported = client.get(
            f"{BASE}/export",
            params={
                "dataset": "provider-ranking",
                "preset": "custom",
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
            headers=headers,
        )
        assert table.status_code == exported.status_code == 200
        row = table.json()["data"][0]
        assert row["name"].startswith("=")
        records = list(csv.reader(io.StringIO(exported.text)))
        header = [
            "provider_id",
            "provider_name",
            "provider_type",
            "provider_status",
            "publication_status",
            "profile_views",
            "review_submissions",
            "average_rating",
            "rating_count",
            "saved_count",
        ]
        header_index = records.index(header)
        export_row = records[header_index + 1]
        assert export_row[0] == str(row["provider_id"])
        assert export_row[1].startswith("'=")
        assert all(len(record) == len(header) for record in records)