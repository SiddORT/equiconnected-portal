"""Verified-member visiting-provider calendar and availability contracts."""
from datetime import date, datetime, timezone

import pytest

from app.core.security import create_access_token, hash_password
from app.models.enums import (
    DoctorAvailability,
    ProviderProfileUpdateStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.provider import DoctorVisit, Provider, ProviderProfileUpdate, ProviderSpecialization
from app.models.specialization import Specialization
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.repositories.user_repository import UserRepository

BASE = "/api/v1/member/providers"
CALENDAR_URL = f"{BASE}/visits/calendar"
AVAILABILITY_URL = f"{BASE}/visits/availability"


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _user(db, email: str, role_name: str, *, verified: bool):
    repo = UserRepository(db)
    role = repo.get_role_by_name(role_name) or repo.create_role(role_name)
    user = repo.create_user(
        email=email,
        password_hash=hash_password("MemberPassword1"),
        role=role,
        roles=[role],
    )
    if verified:
        user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return user


def _provider(
    db,
    name: str,
    *,
    provider_type=ProviderType.DOCTOR,
    status=ProviderStatus.ACTIVE,
    publication=PublicationStatus.PUBLISHED,
    availability=DoctorAvailability.VISITING,
):
    provider = Provider(
        provider_type=provider_type,
        name=name,
        visit_stability=VisitStability.NOT_STABLE_VISIT,
        status=status,
        publication_status=publication,
        doctor_availability=availability,
    )
    db.add(provider)
    db.flush()
    return provider


def _visit(db, provider, start: date, end: date, location=None):
    visit = DoctorVisit(
        provider_id=provider.id,
        start_date=start,
        end_date=end,
        location=location or {"city": "Toronto"},
    )
    db.add(visit)
    db.flush()
    return visit


class TestMemberVisitingCalendar:
    def test_both_routes_require_a_verified_member(self, client, db):
        for path in (CALENDAR_URL, AVAILABILITY_URL):
            assert client.get(path).status_code == 401

        unverified = _user(db, "unverified-calendar@example.com", "horse_owner", verified=False)
        visitor = _user(db, "visitor-calendar@example.com", "visitor", verified=True)
        for path in (CALENDAR_URL, AVAILABILITY_URL):
            assert client.get(path, headers=_auth(unverified)).status_code == 403
            assert client.get(path, headers=_auth(visitor)).status_code == 403

    @pytest.mark.parametrize(
        "month",
        ["2026-00", "2026-13", "2026-1", "abcd-01", "0000-01", "2026-02-01", ""],
    )
    def test_rejects_invalid_month(self, client, db, month):
        member = _user(db, "invalid-month@example.com", "horse_owner", verified=True)
        response = client.get(CALENDAR_URL, params={"month": month}, headers=_auth(member))
        assert response.status_code == 422

    def test_calendar_uses_persisted_published_visits_and_exposes_only_allow_list(
        self, client, db, monkeypatch
    ):
        member = _user(db, "calendar-member@example.com", "horse_owner", verified=True)
        monkeypatch.setattr("app.api.v1.member_providers.system_today", lambda _zone: date(2026, 9, 24))

        eligible = _provider(db, "Dr. Calendar")
        specialist = Specialization(name="Surgery")
        db.add(specialist)
        db.flush()
        db.add(ProviderSpecialization(provider_id=eligible.id, specialization_id=specialist.id))
        cross_month_trip = _visit(
            db,
            eligible,
            date(2026, 9, 30),
            date(2026, 10, 2),
            {
                "name": "Private site name",
                "city": "Calgary",
                "state_province": "Alberta",
                "country": "Canada",
                "address_line_1": "10 Private Street",
                "address_line_2": "Suite 2",
                "postal_code": "T2P 0A1",
                "latitude": 51.0447,
                "longitude": -114.0719,
            },
        )
        # Inclusive trip end equal to system Today remains eligible.
        today_trip = _visit(db, eligible, date(2026, 8, 30), date(2026, 9, 24))

        pending = _provider(db, "Pending proposed trip")
        db.add(
            ProviderProfileUpdate(
                provider_id=pending.id,
                proposed_profile={
                    "doctor_visits": [
                        {
                            "start_date": "2026-09-25",
                            "end_date": "2026-09-26",
                            "location": {"city": "Pending City"},
                        }
                    ]
                },
                base_profile={},
                review_status=ProviderProfileUpdateStatus.PENDING_REVIEW,
                submitted_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            )
        )

        excluded = [
            _provider(db, "Inactive", status=ProviderStatus.INACTIVE),
            _provider(db, "Unpublished", publication=PublicationStatus.UNPUBLISHED),
            _provider(db, "Ongoing", availability=DoctorAvailability.ONGOING),
            _provider(db, "Legacy", availability=None),
            _provider(db, "Clinic", provider_type=ProviderType.CLINIC),
        ]
        for provider in excluded:
            _visit(db, provider, date(2026, 9, 25), date(2026, 9, 26))
        _visit(db, eligible, date(2026, 9, 1), date(2026, 9, 23))  # ended before Today
        db.commit()

        headers = _auth(member)
        september_response = client.get(CALENDAR_URL, params={"month": "2026-09"}, headers=headers)
        october_response = client.get(CALENDAR_URL, params={"month": "2026-10"}, headers=headers)
        assert september_response.status_code == october_response.status_code == 200
        september = september_response.json()
        october = october_response.json()
        assert september["month"] == "2026-09"
        assert september["today"] == "2026-09-24"
        assert october["month"] == "2026-10"
        assert [visit["id"] for visit in september["visits"]] == [
            str(today_trip.id),
            str(cross_month_trip.id),
        ]
        assert len(september["visits"]) == 2
        assert len(october["visits"]) == 1
        cross_month = october["visits"][0]
        assert cross_month["provider_id"] == str(eligible.id)
        assert (cross_month["start_date"], cross_month["end_date"]) == ("2026-09-30", "2026-10-02")
        assert cross_month["specializations"] == ["Surgery"]
        assert cross_month["location"] == {
            "city": "Calgary",
            "state_province": "Alberta",
            "country": "Canada",
        }
        assert set(cross_month) == {
            "id",
            "provider_id",
            "provider_name",
            "start_date",
            "end_date",
            "specializations",
            "location",
        }
        assert set(cross_month["location"]) == {"city", "state_province", "country"}
        assert all(
            visit["provider_id"] == str(eligible.id)
            for visit in september["visits"] + october["visits"]
        )

    def test_availability_is_directory_wide_and_includes_future_only_trips(
        self, client, db, monkeypatch
    ):
        member = _user(db, "future-calendar@example.com", "horse_owner", verified=True)
        monkeypatch.setattr("app.api.v1.member_providers.system_today", lambda _zone: date(2026, 9, 24))
        future = _provider(db, "Future visitor")
        _visit(db, future, date(2026, 11, 1), date(2026, 11, 3))
        ended = _provider(db, "Ended visitor")
        _visit(db, ended, date(2026, 9, 1), date(2026, 9, 23))
        db.commit()

        headers = _auth(member)
        assert client.get(AVAILABILITY_URL, headers=headers).json() == {"has_visits": True}
        september = client.get(CALENDAR_URL, params={"month": "2026-09"}, headers=headers).json()
        november = client.get(CALENDAR_URL, params={"month": "2026-11"}, headers=headers).json()
        assert september["visits"] == []
        assert [visit["provider_name"] for visit in november["visits"]] == ["Future visitor"]

    def test_availability_excludes_ineligible_and_already_ended_trips(
        self, client, db, monkeypatch
    ):
        member = _user(db, "no-current-visits@example.com", "horse_owner", verified=True)
        monkeypatch.setattr("app.api.v1.member_providers.system_today", lambda _zone: date(2026, 9, 24))
        ineligible_providers = [
            _provider(db, "Inactive", status=ProviderStatus.INACTIVE),
            _provider(db, "Unpublished", publication=PublicationStatus.UNPUBLISHED),
            _provider(db, "Ongoing", availability=DoctorAvailability.ONGOING),
            _provider(db, "Legacy", availability=None),
            _provider(db, "Clinic", provider_type=ProviderType.CLINIC),
        ]
        for provider in ineligible_providers:
            _visit(db, provider, date(2026, 9, 25), date(2026, 9, 26))
        ended = _provider(db, "Ended visitor")
        _visit(db, ended, date(2026, 9, 1), date(2026, 9, 23))
        db.commit()

        assert client.get(AVAILABILITY_URL, headers=_auth(member)).json() == {
            "has_visits": False
        }

    def test_today_and_default_month_follow_configured_system_timezone(self, client, db, monkeypatch):
        member = _user(db, "timezone-calendar@example.com", "horse_owner", verified=True)
        SystemSettingsRepository(db).update(timezone="Pacific/Auckland")
        db.commit()
        from app.core.time_standards import system_today as actual_system_today

        fixed_now = datetime(2026, 8, 31, 13, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(
            "app.api.v1.member_providers.system_today",
            lambda timezone_name: actual_system_today(timezone_name, fixed_now),
        )
        active_on_local_today = _provider(db, "Auckland visitor")
        _visit(db, active_on_local_today, date(2026, 8, 31), date(2026, 9, 1))
        just_ended = _provider(db, "Ended in Auckland")
        _visit(db, just_ended, date(2026, 8, 30), date(2026, 8, 31))
        db.commit()

        response = client.get(CALENDAR_URL, headers=_auth(member))
        assert response.status_code == 200
        assert response.json()["month"] == "2026-09"
        assert response.json()["today"] == "2026-09-01"
        assert [visit["provider_name"] for visit in response.json()["visits"]] == [
            "Auckland visitor"
        ]