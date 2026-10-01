"""Provider-owned published-profile update review lifecycle."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import time
from threading import Event, Thread
from uuid import uuid4

from PIL import Image
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.models.doctor import DoctorProfile
from app.models.audit_log import AuditLog
from app.models.enums import (
    DoctorAvailability,
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderProfileUpdateStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.provider import (
    Provider,
    DoctorVisit,
    ProviderEmail,
    ProviderLocation,
    ProviderPhoto,
    ProviderPhone,
    ProviderProfileUpdate,
)
from app.models.provider_registration import ProviderRegistrationApplication
from app.repositories.user_repository import UserRepository
from app.repositories.provider_profile_update_repository import (
    ProviderProfileUpdateRepository,
)
from app.repositories.provider_repository import ProviderRepository
import app.services.provider_portal_service as provider_portal_service
from app.services.provider_profile_update_service import (
    ProviderProfileUpdateConflictError,
    ProviderProfileUpdateService,
    _legacy_phone_contact,
    editable_profile_from_provider,
)
from app.services.provider_portal_service import _UPLOADS_DIR


def _login(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _one_pixel_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def _portal_provider(
    db,
    admin,
    *,
    email: str,
    name: str,
    publication_status: PublicationStatus,
    status: ProviderStatus = ProviderStatus.ACTIVE,
    registered_account: bool = False,
    years_experience: int | None = None,
    visit_stability: VisitStability = VisitStability.STABLE_VISIT,
):
    users = UserRepository(db)
    role = users.get_role_by_name("provider") or users.create_role("provider", "Provider portal")
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name=name,
        visit_stability=visit_stability,
        status=status,
        publication_status=publication_status,
        description="Approved description",
        years_experience=years_experience,
    )
    db.add(provider)
    db.flush()
    db.add(
        ProviderLocation(
            provider_id=provider.id,
            address_line_1="1 Approved Way",
            city="Dubai",
            is_primary=True,
        )
    )
    account = users.create_user(
        email=email,
        password_hash=hash_password("ProviderPass9"),
        role=role,
        roles=[role],
    )
    account.email_verified_at = datetime.now(timezone.utc)
    if registered_account:
        db.add(
            ProviderRegistrationApplication(
                user_id=account.id,
                provider_id=provider.id,
                provider_type=ProviderType.CLINIC,
                provider_name=name,
                visit_stability=VisitStability.STABLE_VISIT,
                postal_code="12345",
                review_status=ProviderApplicationStatus.APPROVED,
            )
        )
    else:
        db.add(
            ProviderInvitation(
                provider_id=provider.id,
                provider_type=ProviderType.CLINIC,
                recipient_email=email,
                token_hash=f"{email}-completed",
                status=InvitationStatus.COMPLETED,
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                sent_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                portal_user_id=account.id,
                created_by=admin.id,
            )
        )
    db.commit()
    return provider, account


def _portal_doctor(
    db,
    admin,
    *,
    email: str,
    publication_status: PublicationStatus,
    doctor_availability: DoctorAvailability | None = None,
):
    users = UserRepository(db)
    role = users.get_role_by_name("provider") or users.create_role(
        "provider", "Provider portal"
    )
    provider = Provider(
        provider_type=ProviderType.DOCTOR,
        name="Dr. Portal Notes",
        visit_stability=VisitStability.STABLE_VISIT,
        doctor_availability=doctor_availability,
        status=ProviderStatus.ACTIVE,
        publication_status=publication_status,
    )
    db.add(provider)
    db.flush()
    provider.doctor_profile = DoctorProfile(
        provider_id=provider.id,
        experience_description="Original experience notes",
    )
    account = users.create_user(
        email=email,
        password_hash=hash_password("ProviderPass9"),
        role=role,
        roles=[role],
    )
    account.email_verified_at = datetime.now(timezone.utc)
    db.add(
        ProviderInvitation(
            provider_id=provider.id,
            provider_type=ProviderType.DOCTOR,
            recipient_email=email,
            token_hash=f"{email}-completed",
            status=InvitationStatus.COMPLETED,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            sent_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            portal_user_id=account.id,
            created_by=admin.id,
        )
    )
    db.commit()
    return provider, account


def _visit_addition(start: date, end: date, city: str = "Pune") -> dict:
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "location": {
            "address_line_1": "12 Arena Road",
            "city": city,
            "country": "India",
        },
    }


def test_visiting_doctor_owner_history_draft_and_delayed_approval(
    client, db, seeded_admin
):
    admin, admin_password = seeded_admin
    provider, account = _portal_doctor(
        db,
        admin,
        email="visiting-owner@example.com",
        publication_status=PublicationStatus.PUBLISHED,
        doctor_availability=DoctorAvailability.VISITING,
    )
    historical = DoctorVisit(
        provider_id=provider.id,
        location={
            "address_line_1": "Old Road",
            "city": "Mumbai",
            "country": "India",
        },
        start_date=date.today() - timedelta(days=20),
        end_date=date.today() - timedelta(days=18),
    )
    db.add(historical)
    db.commit()
    owner_token = _login(client, account.email, "ProviderPass9")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    initial = client.get("/api/v1/provider/portal/profile", headers=owner_headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["doctor_availability"] == "VISITING"
    assert initial.json()["can_schedule_visits"] is True
    assert [item["id"] for item in initial.json()["doctor_visits"]] == [
        str(historical.id)
    ]
    assert initial.json()["doctor_visits"][0]["location"]["city"] == "Mumbai"
    assert initial.json()["editable_profile"]["visit_additions"] == []

    proposed_date = date.today() + timedelta(days=20)
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=owner_headers,
        json={"visit_additions": [_visit_addition(proposed_date, proposed_date + timedelta(days=1))]},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["can_schedule_visits"] is True
    assert len(submitted.json()["doctor_visits"]) == 1
    assert submitted.json()["editable_profile"]["visit_additions"][0]["start_date"] == (
        proposed_date.isoformat()
    )
    assert "id" not in submitted.json()["editable_profile"]["visit_additions"][0]
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 1

    users = UserRepository(db)
    member_role = users.get_role_by_name("horse_owner") or users.create_role(
        "horse_owner"
    )
    member = users.create_user(
        email="visit-directory-member@example.com",
        password_hash=hash_password("MemberPass9"),
        role=member_role,
        roles=[member_role],
    )
    member.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    member_token = _login(client, member.email, "MemberPass9")
    public_detail = client.get(
        f"/api/v1/member/providers/{provider.id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert public_detail.status_code == 200, public_detail.text
    assert len(public_detail.json()["doctor_visits"]) == 1
    assert public_detail.json()["doctor_visits"][0]["location"]["city"] == "Mumbai"
    assert public_detail.json()["doctor_visits"][0]["start_date"] == (
        historical.start_date.isoformat()
    )

    update = db.query(ProviderProfileUpdate).filter_by(provider_id=provider.id).one()
    # Simulate a timely draft whose review is delayed beyond its start date.
    late_start = date.today() - timedelta(days=1)
    proposed_snapshot = dict(update.proposed_profile)
    proposed_snapshot["visit_additions"] = [
        _visit_addition(late_start, late_start + timedelta(days=1))
    ]
    update.proposed_profile = proposed_snapshot
    db.commit()

    unrelated = client.patch(
        "/api/v1/provider/portal/profile",
        headers=owner_headers,
        json={"description": "An unrelated profile edit."},
    )
    assert unrelated.status_code == 200, unrelated.text
    assert unrelated.json()["editable_profile"]["visit_additions"][0]["start_date"] == (
        late_start.isoformat()
    )
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 1

    admin_token = _login(client, admin.email, admin_password)
    approved = client.post(
        f"/api/v1/admin/provider-profile-updates/{update.id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200, approved.text
    visits = db.query(DoctorVisit).filter_by(provider_id=provider.id).order_by(
        DoctorVisit.start_date
    ).all()
    assert len(visits) == 2
    saved_history = next(item for item in visits if item.id == historical.id)
    assert saved_history.location["city"] == "Mumbai"
    assert saved_history.start_date == date.today() - timedelta(days=20)
    assert visits[-1].start_date == late_start
    assert client.post(
        f"/api/v1/admin/provider-profile-updates/{update.id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).status_code == 409
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 2


def test_visiting_doctor_rejects_invalid_or_overlapping_additions(client, db, seeded_admin):
    admin, _ = seeded_admin
    provider, account = _portal_doctor(
        db,
        admin,
        email="visiting-validation@example.com",
        publication_status=PublicationStatus.PUBLISHED,
        doctor_availability=DoctorAvailability.VISITING,
    )
    recorded_start = date.today() + timedelta(days=20)
    recorded = DoctorVisit(
        provider_id=provider.id,
        location={"address_line_1": "Scheduled Road", "city": "Pune"},
        start_date=recorded_start,
        end_date=recorded_start + timedelta(days=1),
    )
    db.add(recorded)
    db.commit()
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}
    base = "/api/v1/provider/portal/profile"

    requests = [
        ({"visit_additions": None}, "visit_additions"),
        (
            {"visit_additions": [_visit_addition(date.today() - timedelta(days=1), date.today())]},
            "today or later",
        ),
        (
            {"visit_additions": [_visit_addition(date.today() + timedelta(days=3), date.today() + timedelta(days=2))]},
            "on or after",
        ),
        (
            {
                "visit_additions": [
                    {
                        **_visit_addition(date.today() + timedelta(days=3), date.today() + timedelta(days=4)),
                        "id": str(uuid4()),
                    }
                ]
            },
            "Extra inputs",
        ),
        (
            {
                "visit_additions": [
                    _visit_addition(recorded_start + timedelta(days=1), recorded_start + timedelta(days=2))
                ]
            },
            "overlap",
        ),
        (
            {
                "visit_additions": [
                    _visit_addition(date.today() + timedelta(days=3), date.today() + timedelta(days=4)),
                    _visit_addition(date.today() + timedelta(days=4), date.today() + timedelta(days=5)),
                ]
            },
            "overlap",
        ),
        (
            {
                "visit_additions": [
                    {
                        "start_date": (date.today() + timedelta(days=3)).isoformat(),
                        "end_date": (date.today() + timedelta(days=3)).isoformat(),
                        "location": {"address_line_1": "   ", "city": "Pune"},
                    }
                ]
            },
            "String should have at least 1 character",
        ),
    ]
    for payload, message in requests:
        response = client.patch(base, headers=headers, json=payload)
        assert response.status_code == 422, response.text
        assert message.lower() in response.text.lower()
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 1
    assert db.query(ProviderProfileUpdate).filter_by(provider_id=provider.id).count() == 0


def test_unpublished_visit_additions_apply_once_and_published_draft_transition_clears(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    provider, account = _portal_doctor(
        db,
        admin,
        email="unpublished-visiting-owner@example.com",
        publication_status=PublicationStatus.UNPUBLISHED,
        doctor_availability=DoctorAvailability.VISITING,
    )
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}
    visit_date = date.today()
    direct = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"visit_additions": [_visit_addition(visit_date, visit_date)]},
    )
    assert direct.status_code == 200, direct.text
    assert direct.json()["profile_update"] is None
    assert direct.json()["editable_profile"]["visit_additions"] == []
    assert len(direct.json()["doctor_visits"]) == 1
    assert direct.json()["doctor_visits"][0]["start_date"] == visit_date.isoformat()
    assert client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"name": "Unpublished Doctor"},
    ).status_code == 200
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 1

    published, published_account = _portal_doctor(
        db,
        admin,
        email="transition-visiting-owner@example.com",
        publication_status=PublicationStatus.PUBLISHED,
        doctor_availability=DoctorAvailability.VISITING,
    )
    published_token = _login(client, published_account.email, "ProviderPass9")
    published_headers = {"Authorization": f"Bearer {published_token}"}
    future = date.today() + timedelta(days=12)
    pending = client.patch(
        "/api/v1/provider/portal/profile",
        headers=published_headers,
        json={"visit_additions": [_visit_addition(future, future)]},
    )
    assert pending.status_code == 200, pending.text
    update = db.query(ProviderProfileUpdate).filter_by(provider_id=published.id).one()
    published.publication_status = PublicationStatus.UNPUBLISHED
    db.commit()
    saved = client.patch(
        "/api/v1/provider/portal/profile",
        headers=published_headers,
        json={"description": "Now unpublished."},
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["doctor_visits"]) == 1
    assert saved.json()["editable_profile"]["visit_additions"] == []
    assert update.proposed_profile["visit_additions"] == []
    assert client.patch(
        "/api/v1/provider/portal/profile",
        headers=published_headers,
        json={"name": "Unpublished After Review"},
    ).status_code == 200
    assert db.query(DoctorVisit).filter_by(provider_id=published.id).count() == 1


def test_only_visiting_doctor_owners_can_propose_visits(client, db, seeded_admin):
    admin, _ = seeded_admin
    non_visiting_doctor, doctor_account = _portal_doctor(
        db,
        admin,
        email="ongoing-owner@example.com",
        publication_status=PublicationStatus.UNPUBLISHED,
        doctor_availability=DoctorAvailability.ONGOING,
    )
    clinic, clinic_account = _portal_provider(
        db,
        admin,
        email="clinic-owner-visits@example.com",
        name="No Visit Clinic",
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    legacy_doctor, legacy_account = _portal_doctor(
        db,
        admin,
        email="legacy-doctor-owner@example.com",
        publication_status=PublicationStatus.UNPUBLISHED,
    )

    for provider, account in (
        (non_visiting_doctor, doctor_account),
        (clinic, clinic_account),
        (legacy_doctor, legacy_account),
    ):
        token = _login(client, account.email, "ProviderPass9")
        headers = {"Authorization": f"Bearer {token}"}
        profile = client.get("/api/v1/provider/portal/profile", headers=headers)
        assert profile.status_code == 200, profile.text
        assert profile.json()["can_schedule_visits"] is False
        assert profile.json()["doctor_availability"] == (
            "ONGOING" if provider.id == non_visiting_doctor.id else None
        )
        response = client.patch(
            "/api/v1/provider/portal/profile",
            headers=headers,
            json={
                "visit_additions": [
                    _visit_addition(
                        date.today() + timedelta(days=5),
                        date.today() + timedelta(days=5),
                    )
                ]
            },
        )
        assert response.status_code == 422, response.text
        assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 0


def test_visit_addition_rejection_revision_and_discard_stay_private(
    client, db, seeded_admin
):
    admin, admin_password = seeded_admin
    provider, account = _portal_doctor(
        db,
        admin,
        email="revise-visits-owner@example.com",
        publication_status=PublicationStatus.PUBLISHED,
        doctor_availability=DoctorAvailability.VISITING,
    )
    owner_token = _login(client, account.email, "ProviderPass9")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    first_start = date.today() + timedelta(days=8)
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=owner_headers,
        json={"visit_additions": [_visit_addition(first_start, first_start)]},
    )
    assert submitted.status_code == 200, submitted.text
    update_id = submitted.json()["profile_update"]["id"]

    admin_token = _login(client, admin.email, admin_password)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    rejected = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Please adjust the proposed dates."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["proposed_profile"]["visit_additions"][0]["start_date"] == (
        first_start.isoformat()
    )
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 0

    revised_start = date.today() + timedelta(days=14)
    revised = client.patch(
        "/api/v1/provider/portal/profile",
        headers=owner_headers,
        json={"visit_additions": [_visit_addition(revised_start, revised_start, "Jaipur")]},
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["profile_update"]["id"] == update_id
    assert revised.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
    assert revised.json()["editable_profile"]["visit_additions"][0]["location"]["city"] == (
        "Jaipur"
    )
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 0

    cleared = client.patch(
        "/api/v1/provider/portal/profile",
        headers=owner_headers,
        json={"visit_additions": []},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["editable_profile"]["visit_additions"] == []
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 0
    discarded = client.post(
        "/api/v1/provider/portal/profile-update/discard",
        headers=owner_headers,
    )
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["profile_update"] is None


def test_approval_rechecks_fresh_admin_visits_and_appends_nothing_on_conflict(
    client, db, seeded_admin
):
    admin, admin_password = seeded_admin
    provider, account = _portal_doctor(
        db,
        admin,
        email="admin-conflict-visits-owner@example.com",
        publication_status=PublicationStatus.PUBLISHED,
        doctor_availability=DoctorAvailability.VISITING,
    )
    owner_token = _login(client, account.email, "ProviderPass9")
    start = date.today() + timedelta(days=18)
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"visit_additions": [_visit_addition(start, start + timedelta(days=1))]},
    )
    assert submitted.status_code == 200, submitted.text
    update_id = submitted.json()["profile_update"]["id"]

    admin_token = _login(client, admin.email, admin_password)
    admin_visit = client.post(
        f"/api/v1/admin/providers/{provider.id}/visits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_visit_addition(start + timedelta(days=1), start + timedelta(days=2), "Delhi"),
    )
    assert admin_visit.status_code == 201, admin_visit.text
    assert len(admin_visit.json()["doctor_visits"]) == 1

    approval = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approval.status_code == 409, approval.text
    assert approval.json()["detail"]["code"] == "provider_profile_update_conflict"
    visits = db.query(DoctorVisit).filter_by(provider_id=provider.id).all()
    assert len(visits) == 1
    assert visits[0].location["city"] == "Delhi"
    db.refresh(provider)
    assert provider.name == "Dr. Portal Notes"


def test_approval_waiting_on_admin_root_lock_rechecks_post_commit_schedule(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    provider, account = _portal_doctor(
        db,
        admin,
        email="concurrent-visit-owner@example.com",
        publication_status=PublicationStatus.PUBLISHED,
        doctor_availability=DoctorAvailability.VISITING,
    )
    start = date.today() + timedelta(days=24)
    owner_token = _login(client, account.email, "ProviderPass9")
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"visit_additions": [_visit_addition(start, start + timedelta(days=1))]},
    )
    assert submitted.status_code == 200, submitted.text
    update_id = submitted.json()["profile_update"]["id"]

    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        pytest.skip("This locking assertion requires PostgreSQL row locks.")
    admin_session = Session(bind=bind)
    admin_repo = ProviderRepository(admin_session)
    try:
        # The administrator has already read an empty/stale visit collection.
        stale_provider = admin_repo.get_by_id(provider.id)
        assert stale_provider is not None
        assert stale_provider.doctor_visits == []
        assert admin_repo.lock_provider(provider.id) is not None
        admin_pid = admin_session.scalar(text("SELECT pg_backend_pid()"))
        admin_repo.add_visit(
            provider.id,
            {
                "location": {
                    "address_line_1": "Concurrent Admin Road",
                    "city": "Delhi",
                    "country": "India",
                },
                "start_date": start + timedelta(days=1),
                "end_date": start + timedelta(days=2),
            },
        )

        approval_started = Event()
        approval_finished = Event()
        outcome: dict[str, object] = {}

        def approve_in_independent_session():
            session = Session(bind=bind)
            try:
                repository = ProviderRepository(session)
                stale = repository.get_by_id(provider.id)
                assert stale is not None and stale.doctor_visits == []
                approval_pid = session.scalar(text("SELECT pg_backend_pid()"))
                outcome["approval_pid"] = approval_pid
                approval_started.set()
                service = ProviderProfileUpdateService(
                    ProviderProfileUpdateRepository(session), repository
                )
                service.approve(update_id, admin.id)
                outcome["result"] = "approved"
            except Exception as exc:  # surfaced to the main test thread below
                outcome["result"] = exc
            finally:
                approval_finished.set()
                session.close()

        worker = Thread(target=approve_in_independent_session)
        worker.start()
        assert approval_started.wait(timeout=5)
        approval_pid = outcome["approval_pid"]
        deadline = time.monotonic() + 10
        is_blocked_by_admin = False
        with Session(bind=bind) as monitor:
            while time.monotonic() < deadline:
                is_blocked_by_admin = bool(
                    monitor.scalar(
                        text(
                            "SELECT :admin_pid = ANY(pg_blocking_pids(:approval_pid))"
                        ),
                        {"admin_pid": admin_pid, "approval_pid": approval_pid},
                    )
                )
                if is_blocked_by_admin:
                    break
                time.sleep(0.05)
        assert is_blocked_by_admin, "Approval never waited for the administrator's provider lock."

        admin_session.commit()
        worker.join(timeout=10)
        assert not worker.is_alive()
        assert approval_finished.is_set()
        assert isinstance(outcome["result"], ProviderProfileUpdateConflictError)
    finally:
        admin_session.rollback()
        admin_session.close()

    db.expire_all()
    visits = db.query(DoctorVisit).filter_by(provider_id=provider.id).all()
    assert len(visits) == 1
    assert visits[0].location["city"] == "Delhi"
    db.refresh(provider)
    assert provider.name == "Dr. Portal Notes"


def test_unpublished_provider_saves_directly_without_a_review_request(client, db, seeded_admin):
    admin, _ = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="draft-owner@example.com",
        name="Draft Clinic",
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    token = _login(client, account.email, "ProviderPass9")
    response = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated Draft Clinic"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["profile_update"] is None
    db.refresh(provider)
    assert provider.name == "Updated Draft Clinic"
    assert db.query(ProviderProfileUpdate).count() == 0


def test_unpublished_non_doctor_can_directly_edit_and_read_years_experience(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="clinic-years-owner@example.com",
        name="Years Clinic",
        publication_status=PublicationStatus.UNPUBLISHED,
        years_experience=7,
    )
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["years_experience"] == 7
    assert initial.json()["editable_profile"]["years_experience"] == 7

    updated = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"years_experience": 0},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["years_experience"] == 0
    assert updated.json()["editable_profile"]["years_experience"] == 0
    db.refresh(provider)
    assert provider.years_experience == 0
    assert provider.doctor_profile is None

    # An omitted field in a subsequent patch must retain the canonical value.
    renamed = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"name": "Years Clinic Renamed"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["editable_profile"]["years_experience"] == 0
    db.refresh(provider)
    assert provider.years_experience == 0


def test_published_non_doctor_years_experience_uses_review_and_applies_on_approval(
    client, db, seeded_admin
):
    admin, admin_password = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="published-years-owner@example.com",
        name="Published Years Clinic",
        publication_status=PublicationStatus.PUBLISHED,
        years_experience=8,
    )
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}

    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"years_experience": 0},
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["years_experience"] == 8
    assert body["editable_profile"]["years_experience"] == 0
    assert body["profile_update"]["review_status"] == "PENDING_REVIEW"
    update_id = body["profile_update"]["id"]
    db.refresh(provider)
    assert provider.years_experience == 8

    admin_token = _login(client, admin.email, admin_password)
    approved = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200, approved.text
    db.refresh(provider)
    assert provider.years_experience == 0
    assert approved.json()["proposed_profile"]["years_experience"] == 0


@pytest.mark.parametrize(
    "publication_status",
    [PublicationStatus.UNPUBLISHED, PublicationStatus.PUBLISHED],
)
def test_doctor_experience_notes_edit_clear_reload_and_approval(
    client, db, seeded_admin, publication_status
):
    admin, admin_password = seeded_admin
    provider, account = _portal_doctor(
        db,
        admin,
        email=f"doctor-notes-{publication_status.value.lower()}@example.com",
        publication_status=publication_status,
    )
    provider_token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {provider_token}"}
    initial = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["editable_profile"]["experience_description"] == (
        "Original experience notes"
    )

    changed = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"experience_description": "Updated experience notes"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["editable_profile"]["experience_description"] == (
        "Updated experience notes"
    )
    if publication_status == PublicationStatus.PUBLISHED:
        assert changed.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
        assert changed.json()["doctor_profile"]["experience_description"] == (
            "Original experience notes"
        )
        update_id = changed.json()["profile_update"]["id"]
        updated = client.get("/api/v1/provider/portal/profile", headers=headers)
        assert updated.json()["editable_profile"]["experience_description"] == (
            "Updated experience notes"
        )

        admin_token = _login(client, admin.email, admin_password)
        approved = client.post(
            f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert approved.status_code == 200, approved.text
        db.refresh(provider)
        assert provider.doctor_profile.experience_description == "Updated experience notes"
    else:
        assert changed.json()["profile_update"] is None
        updated = client.get("/api/v1/provider/portal/profile", headers=headers)
        assert updated.json()["editable_profile"]["experience_description"] == (
            "Updated experience notes"
        )
        db.refresh(provider)
        assert provider.doctor_profile.experience_description == "Updated experience notes"

    cleared = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"experience_description": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["editable_profile"]["experience_description"] is None
    if publication_status == PublicationStatus.PUBLISHED:
        assert cleared.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
        update_id = cleared.json()["profile_update"]["id"]
        reloaded = client.get("/api/v1/provider/portal/profile", headers=headers)
        assert reloaded.json()["editable_profile"]["experience_description"] is None

        admin_token = _login(client, admin.email, admin_password)
        approved_clear = client.post(
            f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert approved_clear.status_code == 200, approved_clear.text
    else:
        assert cleared.json()["profile_update"] is None
        reloaded = client.get("/api/v1/provider/portal/profile", headers=headers)
        assert reloaded.json()["editable_profile"]["experience_description"] is None
    db.refresh(provider)
    assert provider.doctor_profile.experience_description is None


def test_non_doctor_cannot_edit_doctor_experience_notes(client, db, seeded_admin):
    admin, _ = seeded_admin
    _provider, account = _portal_provider(
        db,
        admin,
        email="clinic-notes-owner@example.com",
        name="Clinic Notes",
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    token = _login(client, account.email, "ProviderPass9")
    response = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"experience_description": "Not a doctor"},
    )
    assert response.status_code == 422


def test_published_profile_update_isolated_then_rejected_and_resubmitted(client, db, seeded_admin):
    admin, admin_password = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="published-owner@example.com",
        name="Approved Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={
            "name": "Proposed Clinic",
            "locations": [{
                "address_line_1": "2 Proposed Way",
                "city": "Abu Dhabi",
                "is_primary": True,
            }],
        },
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["name"] == "Approved Clinic"
    assert body["editable_profile"]["name"] == "Proposed Clinic"
    assert body["profile_update"]["review_status"] == "PENDING_REVIEW"
    update_id = body["profile_update"]["id"]
    db.refresh(provider)
    assert provider.name == "Approved Clinic"
    assert provider.locations[0].city == "Dubai"
    assert db.query(ProviderProfileUpdate).count() == 1

    refreshed = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"description": "A refreshed proposal in the same review request."},
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["profile_update"]["id"] == update_id
    assert db.query(ProviderProfileUpdate).count() == 1

    # A second provider never sees or modifies the first provider's draft.
    other, other_account = _portal_provider(
        db,
        admin,
        email="other-owner@example.com",
        name="Other Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    other_token = _login(client, other_account.email, "ProviderPass9")
    other_profile = client.get(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_profile.status_code == 200
    assert other_profile.json()["id"] == str(other.id)


    assert other_profile.json()["profile_update"] is None
    assert client.get(
        "/api/v1/admin/provider-profile-updates",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 403

    admin_token = _login(client, admin.email, admin_password)
    rejected = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"rejection_reason": "Please add the clinic license address."},
    )
    assert rejected.status_code == 200, rejected.text
    portal_after_rejection = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert portal_after_rejection.json()["profile_update"]["review_status"] == "REJECTED"
    assert portal_after_rejection.json()["profile_update"]["rejection_reason"]
    assert portal_after_rejection.json()["editable_profile"]["name"] == "Proposed Clinic"

    resubmitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"name": "Revised Proposed Clinic"},
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["profile_update"]["id"] == update_id
    assert resubmitted.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
    assert resubmitted.json()["profile_update"]["rejection_reason"] is None
    db.refresh(provider)
    assert provider.name == "Approved Clinic"


def test_published_provider_photo_upload_stays_inside_the_review_request(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="published-photo-owner@example.com",
        name="Published Photo Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}
    uploaded = client.post(
        "/api/v1/provider/portal/profile/photos/upload",
        headers=headers,
        files={"file": ("clinic.png", _one_pixel_png(), "image/png")},
        data={"alt_text": "Clinic exterior", "caption": "Arrival entrance"},
    )
    assert uploaded.status_code == 201, uploaded.text
    photo = uploaded.json()

    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={
            "photos": [{
                **photo,
                "display_order": 0,
                "is_thumbnail": True,
            }],
        },
    )

    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["profile_update"]["review_status"] == "PENDING_REVIEW"
    assert body["editable_profile"]["photos"][0]["storage_reference"] == photo["storage_reference"]
    db.refresh(provider)
    assert provider.photos == []
    (_UPLOADS_DIR / photo["storage_reference"].removeprefix("/uploads/")).unlink()


def test_provider_photo_review_round_trip_reject_discard_resubmit_and_approve(
    client, db, seeded_admin, monkeypatch, tmp_path
):
    admin, admin_password = seeded_admin
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(provider_portal_service, "_UPLOADS_DIR", upload_root)
    provider, account = _portal_provider(
        db,
        admin,
        email="photo-review-owner@example.com",
        name="Photo Review Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    approved_photo = ProviderPhoto(
        provider_id=provider.id,
        storage_reference=f"/uploads/providers/{provider.id}/photos/approved.png",
        alt_text="Approved clinic entrance",
        caption="Approved entrance",
        display_order=0,
        is_thumbnail=True,
    )
    db.add(approved_photo)
    db.commit()
    provider_token = _login(client, account.email, "ProviderPass9")
    provider_headers = {"Authorization": f"Bearer {provider_token}"}
    admin_token = _login(client, admin.email, admin_password)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    users = UserRepository(db)
    member_role = users.get_role_by_name("horse_owner") or users.create_role("horse_owner")
    member = users.create_user(
        email="photo-review-member@example.com",
        password_hash=hash_password("MemberPass9"),
        role=member_role,
        roles=[member_role],
    )
    member.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    member_headers = {
        "Authorization": f"Bearer {_login(client, member.email, 'MemberPass9')}"
    }

    def assert_lifecycle():
        db.refresh(provider)
        db.refresh(account)
        assert provider.status == ProviderStatus.ACTIVE
        assert provider.publication_status == PublicationStatus.PUBLISHED
        assert account.is_active is True

    def assert_member_listing(name, expected_photos, expected_thumbnail):
        listing = client.get(
            "/api/v1/member/providers",
            headers=member_headers,
            params={"name": "Photo Review"},
        )
        assert listing.status_code == 200, listing.text
        matching = [
            item for item in listing.json()["data"] if item["id"] == str(provider.id)
        ]
        assert len(matching) == 1
        assert matching[0]["name"] == name
        assert matching[0]["thumbnail_url"] == expected_thumbnail

        detail = client.get(
            f"/api/v1/member/providers/{provider.id}", headers=member_headers
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["name"] == name
        assert detail.json()["thumbnail_url"] == expected_thumbnail
        assert [photo["url"] for photo in detail.json()["photos"]] == expected_photos

    initial_gallery = client.get(
        f"/api/v1/admin/providers/{provider.id}", headers=admin_headers
    )
    assert initial_gallery.status_code == 200, initial_gallery.text
    assert initial_gallery.json()["thumbnail_url"] == approved_photo.storage_reference
    assert_member_listing(
        "Photo Review Clinic",
        [approved_photo.storage_reference],
        approved_photo.storage_reference,
    )
    assert_lifecycle()

    uploaded = client.post(
        "/api/v1/provider/portal/profile/photos/upload",
        headers=provider_headers,
        files={"file": ("proposed.png", _one_pixel_png(), "image/png")},
        data={"alt_text": "New treatment room", "caption": "Treatment room"},
    )
    assert uploaded.status_code == 201, uploaded.text
    proposed_photo = uploaded.json()
    upload_path = upload_root / proposed_photo["storage_reference"].removeprefix(
        "/uploads/"
    )
    assert upload_path.is_file()
    with Image.open(upload_path) as image:
        image.verify()
    assert_lifecycle()
    db.refresh(provider)
    assert [
        (photo.storage_reference, photo.is_thumbnail) for photo in provider.photos
    ] == [(approved_photo.storage_reference, True)]

    photo_proposal = [
        {
            "storage_reference": approved_photo.storage_reference,
            "alt_text": approved_photo.alt_text,
            "caption": approved_photo.caption,
            "display_order": 0,
            "is_thumbnail": False,
        },
        {
            **proposed_photo,
            "display_order": 1,
            "is_thumbnail": True,
        },
    ]
    saved = client.patch(
        "/api/v1/provider/portal/profile",
        headers=provider_headers,
        json={"name": "Photo Review Clinic Revised", "photos": photo_proposal},
    )
    assert saved.status_code == 200, saved.text
    saved_body = saved.json()
    update_id = saved_body["profile_update"]["id"]
    assert saved_body["profile_update"]["review_status"] == "PENDING_REVIEW"
    assert saved_body["name"] == "Photo Review Clinic"
    assert saved_body["editable_profile"]["name"] == "Photo Review Clinic Revised"
    assert [photo["storage_reference"] for photo in saved_body["photos"]] == [
        approved_photo.storage_reference
    ]
    assert [
        photo["storage_reference"]
        for photo in saved_body["editable_profile"]["photos"]
    ] == [
        approved_photo.storage_reference,
        proposed_photo["storage_reference"],
    ]
    assert_member_listing(
        "Photo Review Clinic",
        [approved_photo.storage_reference],
        approved_photo.storage_reference,
    )
    assert_lifecycle()

    reloaded = client.get(
        "/api/v1/provider/portal/profile", headers=provider_headers
    )
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["editable_profile"]["photos"][1]["alt_text"] == (
        "New treatment room"
    )
    assert reloaded.json()["editable_profile"]["photos"][1]["is_thumbnail"] is True
    assert reloaded.json()["editable_profile"]["name"] == "Photo Review Clinic Revised"
    assert_member_listing(
        "Photo Review Clinic",
        [approved_photo.storage_reference],
        approved_photo.storage_reference,
    )
    assert_lifecycle()

    comparison = client.get(
        f"/api/v1/admin/provider-profile-updates/{update_id}",
        headers=admin_headers,
    )
    assert comparison.status_code == 200, comparison.text
    compared_photos = comparison.json()["proposed_profile"]["photos"]
    assert [photo["storage_reference"] for photo in compared_photos] == [
        approved_photo.storage_reference,
        proposed_photo["storage_reference"],
    ]
    assert compared_photos[1]["is_thumbnail"] is True

    rejected = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Please confirm this new treatment-room photo."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["review_status"] == "REJECTED"
    assert_lifecycle()
    after_rejection = client.get(
        f"/api/v1/admin/providers/{provider.id}", headers=admin_headers
    )
    assert after_rejection.status_code == 200, after_rejection.text
    assert after_rejection.json()["thumbnail_url"] == approved_photo.storage_reference
    assert [
        (photo["storage_reference"], photo["is_thumbnail"])
        for photo in after_rejection.json()["photos"]
    ] == [(approved_photo.storage_reference, True)]
    rejected_draft = client.get(
        "/api/v1/provider/portal/profile", headers=provider_headers
    )
    assert rejected_draft.json()["profile_update"]["review_status"] == "REJECTED"
    assert rejected_draft.json()["editable_profile"]["photos"][1][
        "storage_reference"
    ] == proposed_photo["storage_reference"]
    assert rejected_draft.json()["editable_profile"]["name"] == (
        "Photo Review Clinic Revised"
    )
    assert_member_listing(
        "Photo Review Clinic",
        [approved_photo.storage_reference],
        approved_photo.storage_reference,
    )
    assert_lifecycle()

    discarded = client.post(
        "/api/v1/provider/portal/profile-update/discard",
        headers=provider_headers,
    )
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["profile_update"] is None
    assert [
        photo["storage_reference"]
        for photo in discarded.json()["editable_profile"]["photos"]
    ] == [approved_photo.storage_reference]
    assert discarded.json()["editable_profile"]["name"] == "Photo Review Clinic"
    assert_member_listing(
        "Photo Review Clinic",
        [approved_photo.storage_reference],
        approved_photo.storage_reference,
    )
    assert_lifecycle()

    resubmitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=provider_headers,
        json={"name": "Photo Review Clinic Revised", "photos": photo_proposal},
    )
    assert resubmitted.status_code == 200, resubmitted.text
    resubmitted_id = resubmitted.json()["profile_update"]["id"]
    assert resubmitted.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
    assert_member_listing(
        "Photo Review Clinic",
        [approved_photo.storage_reference],
        approved_photo.storage_reference,
    )
    assert_lifecycle()
    approved = client.post(
        f"/api/v1/admin/provider-profile-updates/{resubmitted_id}/approve",
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_status"] == "APPROVED"
    assert_lifecycle()
    gallery = client.get(
        f"/api/v1/admin/providers/{provider.id}", headers=admin_headers
    )
    assert gallery.status_code == 200, gallery.text
    gallery_body = gallery.json()
    assert gallery_body["thumbnail_url"] == proposed_photo["storage_reference"]
    assert gallery_body["name"] == "Photo Review Clinic Revised"
    assert [
        (
            photo["storage_reference"],
            photo["alt_text"],
            photo["caption"],
            photo["is_thumbnail"],
        )
        for photo in gallery_body["photos"]
    ] == [
        (
            approved_photo.storage_reference,
            "Approved clinic entrance",
            "Approved entrance",
            False,
        ),
        (
            proposed_photo["storage_reference"],
            "New treatment room",
            "Treatment room",
            True,
        ),
    ]
    assert_member_listing(
        "Photo Review Clinic Revised",
        [
            approved_photo.storage_reference,
            proposed_photo["storage_reference"],
        ],
        proposed_photo["storage_reference"],
    )
    assert_lifecycle()


@pytest.mark.parametrize(
    ("provider_status", "publication_status"),
    [
        (provider_status, publication_status)
        for provider_status in (ProviderStatus.ACTIVE, ProviderStatus.INACTIVE)
        for publication_status in (
            PublicationStatus.UNPUBLISHED,
            PublicationStatus.PUBLISHED,
        )
    ],
)
def test_photo_save_preserves_provider_and_account_lifecycle(
    client,
    db,
    seeded_admin,
    monkeypatch,
    tmp_path,
    provider_status,
    publication_status,
):
    admin, admin_password = seeded_admin
    monkeypatch.setattr(provider_portal_service, "_UPLOADS_DIR", tmp_path / "uploads")
    provider, account = _portal_provider(
        db,
        admin,
        email=(
            f"photo-lifecycle-{provider_status.value.lower()}-"
            f"{publication_status.value.lower()}@example.com"
        ),
        name="Lifecycle Clinic",
        publication_status=publication_status,
        status=provider_status,
    )
    provider_token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {provider_token}"}
    admin_headers = {
        "Authorization": f"Bearer {_login(client, admin.email, admin_password)}"
    }

    def assert_lifecycle():
        db.refresh(provider)
        db.refresh(account)
        assert provider.status == provider_status
        assert provider.publication_status == publication_status
        assert account.is_active is True

    uploaded = client.post(
        "/api/v1/provider/portal/profile/photos/upload",
        headers=headers,
        files={"file": ("lifecycle.png", _one_pixel_png(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert_lifecycle()
    photo = {
        **uploaded.json(),
        "display_order": 0,
        "is_thumbnail": True,
    }

    saved = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"name": "Lifecycle Clinic Revised", "photos": [photo]},
    )
    assert saved.status_code == 200, saved.text
    assert_lifecycle()
    if publication_status == PublicationStatus.PUBLISHED:
        assert saved.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
        assert saved.json()["name"] == "Lifecycle Clinic"
        assert saved.json()["editable_profile"]["name"] == "Lifecycle Clinic Revised"
        assert provider.photos == []
        update_id = saved.json()["profile_update"]["id"]

        rejected = client.post(
            f"/api/v1/admin/provider-profile-updates/{update_id}/reject",
            headers=admin_headers,
            json={"rejection_reason": "Please revise the provider photo."},
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["review_status"] == "REJECTED"
        assert_lifecycle()
        assert provider.name == "Lifecycle Clinic"
        assert provider.photos == []
        rejected_draft = client.get("/api/v1/provider/portal/profile", headers=headers)
        assert rejected_draft.status_code == 200, rejected_draft.text
        assert rejected_draft.json()["editable_profile"]["name"] == (
            "Lifecycle Clinic Revised"
        )
        assert rejected_draft.json()["editable_profile"]["photos"][0][
            "storage_reference"
        ] == photo["storage_reference"]
        assert_lifecycle()

        discarded = client.post(
            "/api/v1/provider/portal/profile-update/discard", headers=headers
        )
        assert discarded.status_code == 200, discarded.text
        assert discarded.json()["profile_update"] is None
        assert discarded.json()["editable_profile"]["name"] == "Lifecycle Clinic"
        assert discarded.json()["editable_profile"]["photos"] == []
        assert_lifecycle()

        resubmitted = client.patch(
            "/api/v1/provider/portal/profile",
            headers=headers,
            json={"name": "Lifecycle Clinic Revised", "photos": [photo]},
        )
        assert resubmitted.status_code == 200, resubmitted.text
        assert resubmitted.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
        assert resubmitted.json()["profile_update"]["id"] != update_id
        assert resubmitted.json()["editable_profile"]["photos"][0][
            "storage_reference"
        ] == photo["storage_reference"]
        assert_lifecycle()
        approved = client.post(
            f"/api/v1/admin/provider-profile-updates/{resubmitted.json()['profile_update']['id']}/approve",
            headers=admin_headers,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["review_status"] == "APPROVED"
        assert_lifecycle()
        assert provider.name == "Lifecycle Clinic Revised"
        assert len(provider.photos) == 1
        assert provider.photos[0].storage_reference == photo["storage_reference"]
        assert provider.photos[0].is_thumbnail is True
    else:
        assert saved.json()["profile_update"] is None
        assert saved.json()["name"] == "Lifecycle Clinic Revised"
        assert len(provider.photos) == 1
        assert provider.name == "Lifecycle Clinic Revised"
        assert provider.photos[0].storage_reference == photo["storage_reference"]
        assert provider.photos[0].is_thumbnail is True

    reloaded = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["editable_profile"]["photos"][0][
        "storage_reference"
    ] == photo["storage_reference"]
    assert reloaded.json()["editable_profile"]["name"] == "Lifecycle Clinic Revised"
    assert_lifecycle()


def test_disabled_provider_account_cannot_upload_or_save_photos(
    client, db, seeded_admin, tmp_path, monkeypatch
):
    admin, _ = seeded_admin
    monkeypatch.setattr(provider_portal_service, "_UPLOADS_DIR", tmp_path / "uploads")
    provider, account = _portal_provider(
        db,
        admin,
        email="disabled-photo-owner@example.com",
        name="Disabled Photo Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}
    uploaded = client.post(
        "/api/v1/provider/portal/profile/photos/upload",
        headers=headers,
        files={"file": ("disabled-draft.png", _one_pixel_png(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    pending = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={
            "name": "Disabled Photo Clinic Proposal",
            "photos": [{
                **uploaded.json(),
                "display_order": 0,
                "is_thumbnail": True,
            }],
        },
    )
    assert pending.status_code == 200, pending.text
    update_id = pending.json()["profile_update"]["id"]
    assert pending.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
    account.is_active = False
    db.commit()

    upload = client.post(
        "/api/v1/provider/portal/profile/photos/upload",
        headers=headers,
        files={"file": ("disabled.png", _one_pixel_png(), "image/png")},
    )
    assert upload.status_code == 403, upload.text
    assert upload.json()["detail"]["code"] == "account_disabled"
    save = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"photos": []},
    )
    assert save.status_code == 403, save.text
    discard = client.post(
        "/api/v1/provider/portal/profile-update/discard",
        headers=headers,
    )
    assert discard.status_code == 403, discard.text
    db.refresh(account)
    db.refresh(provider)
    assert account.is_active is False
    assert provider.photos == []
    assert provider.status == ProviderStatus.ACTIVE
    assert provider.publication_status == PublicationStatus.PUBLISHED
    assert provider.name == "Disabled Photo Clinic"
    assert db.get(ProviderProfileUpdate, update_id).review_status == (
        ProviderProfileUpdateStatus.PENDING_REVIEW
    )


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_admin_can_decide_photo_review_without_reactivating_disabled_owner(
    client, db, seeded_admin, monkeypatch, tmp_path, decision
):
    admin, admin_password = seeded_admin
    monkeypatch.setattr(provider_portal_service, "_UPLOADS_DIR", tmp_path / "uploads")
    provider, account = _portal_provider(
        db,
        admin,
        email=f"disabled-decision-{decision}@example.com",
        name="Disabled Decision Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    provider_headers = {
        "Authorization": f"Bearer {_login(client, account.email, 'ProviderPass9')}"
    }
    uploaded = client.post(
        "/api/v1/provider/portal/profile/photos/upload",
        headers=provider_headers,
        files={"file": ("decision.png", _one_pixel_png(), "image/png")},
        data={"alt_text": "Proposed room", "caption": "Proposed room"},
    )
    assert uploaded.status_code == 201, uploaded.text
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=provider_headers,
        json={
            "name": "Disabled Decision Clinic Revised",
            "photos": [{
                **uploaded.json(),
                "display_order": 0,
                "is_thumbnail": True,
            }],
        },
    )
    assert submitted.status_code == 200, submitted.text
    update_id = submitted.json()["profile_update"]["id"]
    db.refresh(provider)
    db.refresh(account)
    assert provider.name == "Disabled Decision Clinic"
    assert provider.photos == []
    assert provider.status == ProviderStatus.ACTIVE
    assert provider.publication_status == PublicationStatus.PUBLISHED
    assert account.is_active is True

    account.is_active = False
    db.commit()
    admin_headers = {
        "Authorization": f"Bearer {_login(client, admin.email, admin_password)}"
    }
    if decision == "approve":
        response = client.post(
            f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
            headers=admin_headers,
        )
        expected_status = ProviderProfileUpdateStatus.APPROVED
    else:
        response = client.post(
            f"/api/v1/admin/provider-profile-updates/{update_id}/reject",
            headers=admin_headers,
            json={"rejection_reason": "Photo requires a change."},
        )
        expected_status = ProviderProfileUpdateStatus.REJECTED

    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == expected_status.value
    db.refresh(provider)
    db.refresh(account)
    assert account.is_active is False
    assert provider.status == ProviderStatus.ACTIVE
    assert provider.publication_status == PublicationStatus.PUBLISHED
    if decision == "approve":
        assert provider.name == "Disabled Decision Clinic Revised"
        assert len(provider.photos) == 1
        assert provider.photos[0].alt_text == "Proposed room"
        assert provider.photos[0].is_thumbnail is True
    else:
        assert provider.name == "Disabled Decision Clinic"
        assert provider.photos == []


def test_approved_registered_provider_submits_published_changes_for_review(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="registered-published-owner@example.com",
        name="Registered Published Clinic",
        publication_status=PublicationStatus.PUBLISHED,
        registered_account=True,
    )
    token = _login(client, account.email, "ProviderPass9")
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Registered Provider Proposal"},
    )

    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
    assert submitted.json()["editable_profile"]["name"] == "Registered Provider Proposal"
    db.refresh(provider)
    assert provider.name == "Registered Published Clinic"


def test_admin_approval_atomically_applies_snapshot_and_records_audit(client, db, seeded_admin):
    admin, admin_password = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="approval-owner@example.com",
        name="Current Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    provider_token = _login(client, account.email, "ProviderPass9")
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {provider_token}"},
        json={
            "name": "Approved Updated Clinic",
            "description": "New approved description",
            "locations": [{
                "address_line_1": "88 New Road",
                "city": "Sharjah",
                "is_primary": True,
            }],
            "phones": [{"country_code": "+971", "number": "500000000", "is_primary": True}],
        },
    )
    assert submitted.status_code == 200, submitted.text
    update_id = submitted.json()["profile_update"]["id"]
    admin_token = _login(client, admin.email, admin_password)
    listed = client.get(
        "/api/v1/admin/provider-profile-updates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert listed.status_code == 200
    assert listed.json()["data"][0]["proposed_profile"]["name"] == "Approved Updated Clinic"
    assert listed.json()["data"][0]["current_profile"]["name"] == "Current Clinic"

    approved = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_status"] == "APPROVED"
    db.refresh(provider)
    assert provider.name == "Approved Updated Clinic"
    assert provider.description == "New approved description"
    assert [(row.address_line_1, row.city) for row in provider.locations] == [
        ("88 New Road", "Sharjah")
    ]
    assert provider.phones[0].number == "500000000"
    update = db.get(ProviderProfileUpdate, update_id)
    assert update.review_status == ProviderProfileUpdateStatus.APPROVED
    assert db.query(AuditLog).filter(AuditLog.action == "provider_profile_update.approved").count() == 1
    cannot_discard = client.post(
        "/api/v1/provider/portal/profile-update/discard",
        headers={"Authorization": f"Bearer {provider_token}"},
    )
    assert cannot_discard.status_code == 409
    assert db.get(ProviderProfileUpdate, update_id) is not None


def test_approval_refuses_stale_snapshot_after_live_profile_changes(client, db, seeded_admin):
    admin, admin_password = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="conflict-owner@example.com",
        name="Current Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    provider_token = _login(client, account.email, "ProviderPass9")
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {provider_token}"},
        json={"name": "Provider proposal"},
    )
    assert submitted.status_code == 200, submitted.text

    # Simulate an administrator correcting the approved listing before review.
    provider.name = "Administrator correction"
    db.commit()
    admin_token = _login(client, admin.email, admin_password)
    approval = client.post(
        f"/api/v1/admin/provider-profile-updates/{submitted.json()['profile_update']['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approval.status_code == 409, approval.text
    assert approval.json()["detail"]["code"] == "provider_profile_update_conflict"
    db.refresh(provider)
    assert provider.name == "Administrator correction"

    # The provider can intentionally discard the stale draft, receive the
    # corrected approved source, and make a fresh proposal.
    rejected = client.post(
        f"/api/v1/admin/provider-profile-updates/{submitted.json()['profile_update']['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"rejection_reason": "Please rebase this proposal on the correction."},
    )
    assert rejected.status_code == 200, rejected.text
    discarded = client.post(
        "/api/v1/provider/portal/profile-update/discard",
        headers={"Authorization": f"Bearer {provider_token}"},
    )
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["profile_update"] is None
    assert discarded.json()["editable_profile"]["name"] == "Administrator correction"
    resubmitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {provider_token}"},
        json={"name": "Rebased provider proposal"},
    )
    assert resubmitted.status_code == 200, resubmitted.text
    approved = client.post(
        f"/api/v1/admin/provider-profile-updates/{resubmitted.json()['profile_update']['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200, approved.text
    db.refresh(provider)
    assert provider.name == "Rebased provider proposal"


def test_profile_snapshot_ordering_is_stable_for_equal_prefix_related_records(db, seeded_admin):
    admin, _ = seeded_admin
    provider, _ = _portal_provider(
        db,
        admin,
        email="ordering-owner@example.com",
        name="Ordering Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    db.add_all([
        ProviderLocation(
            provider_id=provider.id,
            address_line_1="Shared address",
            city="Dubai",
            state_province="Dubai",
            country="AE",
            postal_code="11111",
        ),
        ProviderLocation(
            provider_id=provider.id,
            address_line_1="Shared address",
            city="Dubai",
            state_province="Abu Dhabi",
            country="AE",
            postal_code="22222",
        ),
    ])
    db.commit()
    db.refresh(provider)
    first = editable_profile_from_provider(provider).model_dump(mode="json")
    provider.locations = list(reversed(provider.locations))
    second = editable_profile_from_provider(provider).model_dump(mode="json")
    assert first == second


def test_portal_service_values_round_trip_through_rejection_resubmission_and_approval(
    client, db, seeded_admin
):
    admin, admin_password = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="services-owner@example.com",
        name="Services Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    provider.maximum_working_radius_km = 12.5
    provider.emergency_services_available = False
    db.commit()
    provider_token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {provider_token}"}

    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={
            "maximum_working_radius_km": 35,
            "emergency_services_available": True,
            "emergency_contact_number": "+971 50 123 4567",
        },
    )
    assert submitted.status_code == 200, submitted.text
    proposed = submitted.json()["editable_profile"]
    assert proposed["maximum_working_radius_km"] == 35
    assert proposed["emergency_services_available"] is True
    assert proposed["emergency_contact_number"] == "+971 50 123 4567"
    update_id = submitted.json()["profile_update"]["id"]
    db.refresh(provider)
    assert float(provider.maximum_working_radius_km) == 12.5
    assert provider.emergency_services_available is False

    admin_token = _login(client, admin.email, admin_password)
    rejected = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"rejection_reason": "Please confirm the emergency line."},
    )
    assert rejected.status_code == 200, rejected.text
    after_rejection = client.get(
        "/api/v1/provider/portal/profile", headers=headers
    ).json()["editable_profile"]
    assert after_rejection["maximum_working_radius_km"] == 35
    assert after_rejection["emergency_contact_number"] == "+971 50 123 4567"

    resubmitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"name": "Services Clinic Resubmitted"},
    )
    assert resubmitted.status_code == 200, resubmitted.text
    assert resubmitted.json()["profile_update"]["review_status"] == "PENDING_REVIEW"
    assert resubmitted.json()["editable_profile"]["maximum_working_radius_km"] == 35
    assert resubmitted.json()["editable_profile"]["emergency_services_available"] is True

    approved = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200, approved.text
    db.refresh(provider)
    assert float(provider.maximum_working_radius_km) == 35
    assert provider.emergency_services_available is True
    assert provider.emergency_contact_number == "+971 50 123 4567"


def test_old_pending_snapshot_without_service_fields_preserves_live_services(
    client, db, seeded_admin
):
    admin, admin_password = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="old-snapshot-owner@example.com",
        name="Snapshot Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    provider.maximum_working_radius_km = 27.5
    provider.emergency_services_available = True
    provider.emergency_contact_number = "+971 50 111 2222"
    provider.email = "legacy-public@example.com"
    provider.phone = "+971501112222"
    db.commit()
    token = _login(client, account.email, "ProviderPass9")
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Snapshot Clinic Proposal"},
    )
    assert submitted.status_code == 200, submitted.text

    update_id = submitted.json()["profile_update"]["id"]
    update = db.get(ProviderProfileUpdate, update_id)
    for key in (
        "maximum_working_radius_km",
        "emergency_services_available",
        "emergency_contact_number",
    ):
        update.proposed_profile.pop(key, None)
        update.base_profile.pop(key, None)
    for snapshot in (update.proposed_profile, update.base_profile):
        snapshot["emails"] = []
        snapshot["phones"] = []
    db.commit()

    portal = client.get(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert portal.status_code == 200, portal.text
    assert portal.json()["editable_profile"]["maximum_working_radius_km"] == 27.5
    assert portal.json()["editable_profile"]["emergency_services_available"] is True
    assert (
        portal.json()["editable_profile"]["emergency_contact_number"]
        == "+971 50 111 2222"
    )
    assert portal.json()["editable_profile"]["emails"] == [
        {"email": "legacy-public@example.com", "is_primary": True}
    ]
    assert portal.json()["editable_profile"]["phones"] == [
        {
            "country_code": "+971",
            "number": "501112222",
            "is_primary": True,
        }
    ]
    admin_token = _login(client, admin.email, admin_password)
    admin_update = client.get(
        f"/api/v1/admin/provider-profile-updates/{update_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_update.status_code == 200, admin_update.text
    assert admin_update.json()["proposed_profile"]["maximum_working_radius_km"] == 27.5

    approved = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200, approved.text
    db.refresh(provider)
    assert float(provider.maximum_working_radius_km) == 27.5
    assert provider.emergency_services_available is True
    assert provider.emergency_contact_number == "+971 50 111 2222"


def test_old_base_contact_fallback_still_detects_live_contact_changes(
    client, db, seeded_admin
):
    admin, admin_password = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="old-contact-base-owner@example.com",
        name="Old Contact Base Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    provider.email = "before@example.com"
    provider.phone = "+971501234567"
    db.commit()
    provider_token = _login(client, account.email, "ProviderPass9")
    submitted = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {provider_token}"},
        json={"name": "Old Contact Base Proposal"},
    )
    assert submitted.status_code == 200, submitted.text

    update_id = submitted.json()["profile_update"]["id"]
    update = db.get(ProviderProfileUpdate, update_id)
    update.base_profile["emails"] = []
    update.base_profile["phones"] = []
    for key in (
        "maximum_working_radius_km",
        "emergency_services_available",
        "emergency_contact_number",
    ):
        update.base_profile.pop(key, None)
    provider.email = "after@example.com"
    provider.phone = "+442079460123"
    db.commit()

    admin_token = _login(client, admin.email, admin_password)
    conflict = client.post(
        f"/api/v1/admin/provider-profile-updates/{update_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "provider_profile_update_conflict"


def test_portal_service_validation_grandfathers_unchanged_missing_values(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="legacy-services-owner@example.com",
        name="Legacy Services Clinic",
        publication_status=PublicationStatus.UNPUBLISHED,
        visit_stability=VisitStability.NOT_STABLE_VISIT,
    )
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}

    unchanged_legacy_profile = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"name": "Legacy Services Clinic Updated"},
    )
    assert unchanged_legacy_profile.status_code == 200, unchanged_legacy_profile.text

    missing_radius = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"visit_stability": "STABLE_VISIT"},
    )
    assert missing_radius.status_code == 422
    valid_radius = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={
            "visit_stability": "STABLE_VISIT",
            "maximum_working_radius_km": 14,
        },
    )
    assert valid_radius.status_code == 200, valid_radius.text

    missing_emergency_number = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"emergency_services_available": True},
    )
    assert missing_emergency_number.status_code == 422
    invalid_emergency_number = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={
            "emergency_services_available": True,
            "emergency_contact_number": "not a phone",
        },
    )
    assert invalid_emergency_number.status_code == 422
    valid_emergency = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={
            "emergency_services_available": True,
            "emergency_contact_number": "+971 50 123 4567",
        },
    )
    assert valid_emergency.status_code == 200, valid_emergency.text


def test_portal_contacts_fall_back_to_scalars_and_explicit_empty_lists_clear_them(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="contact-owner@example.com",
        name="Contact Clinic",
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    provider.email = "public@example.com"
    provider.phone = "+971 50 123 4567"
    account.mobile_number = "+44 20 7946 0123"
    db.commit()
    token = _login(client, account.email, "ProviderPass9")
    headers = {"Authorization": f"Bearer {token}"}

    fallback = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert fallback.status_code == 200, fallback.text
    editable = fallback.json()["editable_profile"]
    assert editable["emails"] == [
        {"email": "public@example.com", "is_primary": True}
    ]
    assert editable["phones"] == [
        {
            "country_code": "+971",
            "number": "50 123 4567",
            "is_primary": True,
        }
    ]

    db.add(
        ProviderEmail(
            provider_id=provider.id,
            email="structured@example.com",
            is_primary=True,
        )
    )
    db.add(
        ProviderPhone(
            provider_id=provider.id,
            country_code="+44",
            number="2079460123",
            is_primary=True,
        )
    )
    db.commit()
    structured = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert structured.json()["editable_profile"]["emails"] == [
        {"email": "structured@example.com", "is_primary": True}
    ]
    assert structured.json()["editable_profile"]["phones"] == [
        {
            "country_code": "+44",
            "number": "2079460123",
            "is_primary": True,
        }
    ]

    cleared = client.patch(
        "/api/v1/provider/portal/profile",
        headers=headers,
        json={"emails": [], "phones": []},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["editable_profile"]["emails"] == []
    assert cleared.json()["editable_profile"]["phones"] == []
    db.refresh(provider)
    db.refresh(account)
    assert provider.email is None
    assert provider.phone is None
    assert account.email == "contact-owner@example.com"
    assert account.mobile_number == "+44 20 7946 0123"

    reloaded = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert reloaded.json()["editable_profile"]["emails"] == []
    assert reloaded.json()["editable_profile"]["phones"] == []


@pytest.mark.parametrize(
    ("compact_number", "country_code", "local_number"),
    [
        ("+971501234567", "+971", "501234567"),
        ("+442079460123", "+44", "2079460123"),
    ],
)
def test_compact_legacy_international_phones_restore_supported_dial_codes(
    compact_number, country_code, local_number
):
    assert _legacy_phone_contact(compact_number) == {
        "country_code": country_code,
        "number": local_number,
        "is_primary": True,
    }


def test_published_contact_clear_is_not_repopulated_in_the_pending_snapshot(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    provider, account = _portal_provider(
        db,
        admin,
        email="published-contact-owner@example.com",
        name="Published Contact Clinic",
        publication_status=PublicationStatus.PUBLISHED,
    )
    provider.email = "public@example.com"
    provider.phone = "+971 50 123 4567"
    db.commit()
    token = _login(client, account.email, "ProviderPass9")

    cleared = client.patch(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"emails": [], "phones": []},
    )
    assert cleared.status_code == 200, cleared.text
    editable = cleared.json()["editable_profile"]
    assert editable["emails"] == []
    assert editable["phones"] == []
    assert editable["email"] is None
    assert editable["phone"] is None
    assert cleared.json()["profile_update"]["review_status"] == "PENDING_REVIEW"

    reloaded = client.get(
        "/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reloaded.json()["editable_profile"]["emails"] == []
    assert reloaded.json()["editable_profile"]["phones"] == []