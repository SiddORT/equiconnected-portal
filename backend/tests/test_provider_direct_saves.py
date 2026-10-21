"""Direct owner writes and historical draft compatibility, isolated from live data."""
from datetime import date, datetime, timedelta, timezone
from threading import Event, Thread

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.enums import (
    ProviderApplicationStatus, ProviderProfileUpdateStatus, PublicationStatus,
)
from app.models.invitation import ProviderInvitation
from app.models.provider import DirectProviderPortalAccess, DoctorVisit, ProviderProfileUpdate
from app.repositories.provider_repository import ProviderRepository
from app.repositories.provider_profile_update_repository import ProviderProfileUpdateRepository
from app.services.provider_portal_service import ProviderPortalService
from app.services.provider_profile_update_service import (
    ProviderProfileUpdateService, ProviderProfileUpdateDecisionError,
)
from app.repositories.review_repository import ReviewRepository
from tests.test_provider_profile_updates import (
    _portal_provider, _portal_doctor, _legacy_draft, _login, _visit_addition,
)


def _headers(client, account, password="ProviderPass9"):
    return {"Authorization": f"Bearer {_login(client, account.email, password)}"}


@pytest.mark.parametrize("journey", ["registration", "invitation", "direct"])
@pytest.mark.parametrize("published", [False, True])
def test_owner_save_then_admin_detail_list_and_reload(client, db, seeded_admin, journey, published):
    admin, password = seeded_admin
    provider, account = _portal_provider(
        db, admin, email="direct-save@example.com", name="Original synthetic clinic",
        publication_status=PublicationStatus.PUBLISHED if published else PublicationStatus.UNPUBLISHED,
        registered_account=journey == "registration",
    )
    if journey == "direct":
        db.query(ProviderInvitation).filter_by(provider_id=provider.id).delete()
        db.add(DirectProviderPortalAccess(
            provider_id=provider.id, user_id=account.id, recipient_email=account.email,
        ))
        db.commit()
    owner = _headers(client, account)
    original_status, original_publication, user_id = provider.status, provider.publication_status, account.id
    saved = client.patch("/api/v1/provider/portal/profile", headers=owner, json={
        "name": "Saved synthetic clinic", "description": "Saved description", "years_experience": 0,
        "website": "https://synthetic.example.com",
        "emails": [{"email": "care@synthetic.example.com", "is_primary": True}],
        "phones": [{"country_code": "+971", "number": "501234567", "is_primary": True}],
        "locations": [{"address_line_1": "Synthetic Road", "city": "Dubai", "is_primary": True}],
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["name"] == "Saved synthetic clinic"
    assert saved.json()["profile_update"] is None
    assert db.query(ProviderProfileUpdate).count() == 0
    reloaded = client.get("/api/v1/provider/portal/profile", headers=owner).json()
    assert reloaded["editable_profile"] == saved.json()["editable_profile"]
    administrator = _headers(client, admin, password)
    detail = client.get(f"/api/v1/admin/providers/{provider.id}", headers=administrator)
    assert detail.status_code == 200, detail.text
    data = detail.json()
    assert data["name"] == "Saved synthetic clinic"
    assert data["description"] == "Saved description"
    assert data["email"] == "care@synthetic.example.com"
    assert data["phone"] == "+971 501234567"
    assert data["locations"][0]["address_line_1"] == "Synthetic Road"
    listed = client.get("/api/v1/admin/providers?search=Saved%20synthetic", headers=administrator)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"][0]["id"] == str(provider.id)
    db.refresh(provider)
    db.refresh(account)
    assert (provider.status, provider.publication_status) == (original_status, original_publication)
    assert account.id == user_id and account.email == "direct-save@example.com"
    action = db.scalar(select(AuditLog).where(AuditLog.action == "provider_portal.profile_updated"))
    assert action.user_id == account.id


@pytest.mark.parametrize("journey", ["registration", "invitation"])
def test_first_approval_cannot_be_bypassed_even_with_an_access_token(client, db, seeded_admin, journey):
    provider, account = _portal_provider(
        db, seeded_admin[0], email="first-approval@example.com", name="Unapproved",
        publication_status=PublicationStatus.PUBLISHED,
        registered_account=journey == "registration",
    )
    # Synthetic forged-ready account state: a signed token is not approval.
    if journey == "registration":
        account.provider_registration_application.review_status = ProviderApplicationStatus.PENDING_REVIEW
    else:
        account.provider_portal_approval_pending = True
    db.commit()
    token = create_access_token(str(account.id), {"role": account.role.name})
    response = client.patch("/api/v1/provider/portal/profile",
        headers={"Authorization": f"Bearer {token}"}, json={"name": "Bypass"})
    assert response.status_code == 403, response.text
    db.refresh(provider)
    assert provider.name == "Unapproved"


@pytest.mark.parametrize("state", [ProviderProfileUpdateStatus.PENDING_REVIEW, ProviderProfileUpdateStatus.REJECTED])
def test_retained_draft_explicit_save_preserves_history_and_blocks_stale_admin_decisions(
    client, db, seeded_admin, state
):
    admin, password = seeded_admin
    provider, account = _portal_provider(db, admin, email="legacy-save@example.com",
        name="Canonical clinic", publication_status=PublicationStatus.PUBLISHED)
    owner, administrator = _headers(client, account), _headers(client, admin, password)
    initial = _legacy_draft(client, db, provider, headers=owner, json={"name": "Retained clinic"})
    update_id = initial.json()["profile_update"]["id"]
    update = db.get(ProviderProfileUpdate, update_id)
    update.review_status = state
    if state == ProviderProfileUpdateStatus.REJECTED:
        update.reviewed_by_user_id = admin.id
        update.reviewed_at = datetime.now(timezone.utc)
        update.rejection_reason = "Historical reason"
    db.commit()
    original_base, original_proposal = dict(update.base_profile), dict(update.proposed_profile)
    # Reading alone never applies or discards a draft.
    assert client.get("/api/v1/provider/portal/profile", headers=owner).json()["name"] == "Canonical clinic"
    saved = client.patch("/api/v1/provider/portal/profile", headers=owner,
                         json={"description": "Explicit owner save"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["name"] == "Retained clinic"
    assert saved.json()["profile_update"]["review_status"] == "SAVED_DIRECTLY"
    db.refresh(update)
    assert update.base_profile == original_base and update.proposed_profile == original_proposal
    assert update.reviewed_by_user_id == (admin.id if state == ProviderProfileUpdateStatus.REJECTED else None)
    assert db.query(AuditLog).filter_by(action="provider_profile_update.approved").count() == 0
    retirement = db.query(AuditLog).filter_by(action="provider_profile_update.saved_directly").one()
    assert retirement.user_id == account.id
    # A second owner write cannot revive the obsolete pending proposal.
    assert client.patch("/api/v1/provider/portal/profile", headers=owner,
                        json={"name": "Newer owner edit"}).status_code == 200
    for decision in ("approve", "reject"):
        response = client.post(f"/api/v1/admin/provider-profile-updates/{update_id}/{decision}",
            headers=administrator, json={"rejection_reason": "Stale browser"})
        assert response.status_code == 409, response.text
    assert client.post("/api/v1/provider/portal/profile-update/discard", headers=owner).status_code == 409
    assert client.get("/api/v1/provider/portal/profile", headers=owner).json()["name"] == "Newer owner edit"


@pytest.mark.parametrize("state", [ProviderProfileUpdateStatus.PENDING_REVIEW, ProviderProfileUpdateStatus.REJECTED])
def test_stale_legacy_draft_refuses_owner_save_but_allows_explicit_discard(client, db, seeded_admin, state):
    provider, account = _portal_provider(db, seeded_admin[0], email="stale-save@example.com",
        name="Base clinic", publication_status=PublicationStatus.PUBLISHED)
    owner = _headers(client, account)
    draft = _legacy_draft(client, db, provider, headers=owner, json={"name": "Old proposal"})
    update = db.get(ProviderProfileUpdate, draft.json()["profile_update"]["id"])
    update.review_status = state
    provider.description = "New administrator correction"
    db.commit()
    failed = client.patch("/api/v1/provider/portal/profile", headers=owner, json={"name": "Still stale"})
    assert failed.status_code == 409, failed.text
    db.refresh(provider)
    db.refresh(update)
    assert provider.name == "Base clinic" and provider.description == "New administrator correction"
    assert update.review_status == state and update.proposed_profile["name"] == "Old proposal"
    discarded = client.post("/api/v1/provider/portal/profile-update/discard", headers=owner)
    assert discarded.status_code == 200
    assert discarded.json()["editable_profile"]["description"] == "New administrator correction"
    assert discarded.json()["profile_update"] is None


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_preloaded_admin_session_cannot_replay_owner_retired_proposal(client, db, seeded_admin, decision):
    admin, _ = seeded_admin
    provider, account = _portal_provider(db, admin, email="stale-session@example.com",
        name="Current clinic", publication_status=PublicationStatus.PUBLISHED)
    owner = _headers(client, account)
    draft = _legacy_draft(client, db, provider, headers=owner, json={"name": "Retained clinic"})
    update_id = draft.json()["profile_update"]["id"]
    with Session(bind=db.get_bind()) as stale_session:
        updates = ProviderProfileUpdateRepository(stale_session)
        cached = updates.get(update_id)
        assert cached.review_status == ProviderProfileUpdateStatus.PENDING_REVIEW
        assert client.patch("/api/v1/provider/portal/profile", headers=owner,
            json={"name": "New canonical clinic"}).status_code == 200
        service = ProviderProfileUpdateService(updates, ProviderRepository(stale_session))
        with pytest.raises(ProviderProfileUpdateDecisionError):
            if decision == "approve":
                service.approve(update_id, admin.id)
            else:
                service.reject(update_id, admin.id, "Stale administrator page")
    assert client.get("/api/v1/provider/portal/profile", headers=owner).json()["name"] == "New canonical clinic"


@pytest.mark.parametrize("field,value", [
    ("status", "ACTIVE"), ("publication_status", "PUBLISHED"),
    ("provider_type", "DOCTOR"), ("owner_user_id", "00000000-0000-0000-0000-000000000001"),
    ("provider_portal_approval_pending", False),
])
def test_privileged_fields_reject_entire_payload(client, db, seeded_admin, field, value):
    provider, account = _portal_provider(db, seeded_admin[0], email="protected-save@example.com",
        name="Protected clinic", publication_status=PublicationStatus.UNPUBLISHED)
    response = client.patch("/api/v1/provider/portal/profile", headers=_headers(client, account),
        json={"name": "Must not save", field: value})
    assert response.status_code == 422, response.text
    db.refresh(provider)
    assert provider.name == "Protected clinic"


def test_invalid_visit_rolls_back_entire_owner_snapshot_and_retains_draft(client, db, seeded_admin):
    provider, account = _portal_doctor(db, seeded_admin[0], email="atomic-save@example.com",
        publication_status=PublicationStatus.PUBLISHED)
    owner = _headers(client, account)
    day = date.today() + timedelta(days=10)
    initial = _legacy_draft(client, db, provider, headers=owner, json={
        "doctor_availability": "VISITING", "visit_additions": [_visit_addition(day, day)],
    })
    db.add(DoctorVisit(provider_id=provider.id, start_date=day, end_date=day,
                      location={"address_line_1": "Admin road", "city": "Dubai"}))
    db.commit()
    before = client.get("/api/v1/provider/portal/profile", headers=owner).json()
    response = client.patch("/api/v1/provider/portal/profile", headers=owner, json={
        "first_name": "No", "last_name": "Mutation",
        "emails": [{"email": "no-change@example.com", "is_primary": True}],
        "photos": [], "locations": [{"address_line_1": "No change", "city": "Dubai"}],
    })
    assert response.status_code == 422, response.text
    assert "overlap" in response.text
    after = client.get("/api/v1/provider/portal/profile", headers=owner).json()
    assert after == before
    assert after["profile_update"]["id"] == initial.json()["profile_update"]["id"]


def test_write_failure_rolls_back_collections_and_trip_rows(db, seeded_admin, monkeypatch):
    provider, account = _portal_doctor(db, seeded_admin[0], email="rollback-save@example.com",
        publication_status=PublicationStatus.PUBLISHED)
    repo = ProviderRepository(db)
    service = ProviderPortalService(repo, ReviewRepository(db), ProviderProfileUpdateRepository(db))
    original = service.get_profile(account).model_dump(mode="json")
    real_add = repo.add_visit

    def failing_add(*args, **kwargs):
        real_add(*args, **kwargs)  # a row and earlier collection writes have been flushed
        raise RuntimeError("Synthetic write failure")

    monkeypatch.setattr(repo, "add_visit", failing_add)
    day = date.today() + timedelta(days=12)
    with pytest.raises(RuntimeError, match="Synthetic write"):
        service.update_profile(account, {
            "first_name": "No", "last_name": "Mutation", "doctor_availability": "VISITING",
            "visit_additions": [_visit_addition(day, day)],
            "locations": [{"address_line_1": "No change", "city": "Dubai"}],
        }, audit_context=None)
    assert service.get_profile(account).model_dump(mode="json") == original
    assert repo.visits(provider.id) == []


def test_waiting_owner_patch_reads_latest_canonical_collections(db, seeded_admin):
    provider, account = _portal_provider(db, seeded_admin[0], email="concurrent-save@example.com",
        name="Concurrent clinic", publication_status=PublicationStatus.PUBLISHED)
    provider_id, account_id = provider.id, account.id
    bind = db.get_bind()
    started, finished = Event(), Event()
    outcome = {}
    with Session(bind=bind) as administrator:
        repo = ProviderRepository(administrator)
        repo.lock_provider(provider_id).description = "Committed by administrator"

        def save():
            with Session(bind=bind) as owner:
                from app.models.user import User
                svc = ProviderPortalService(ProviderRepository(owner), ReviewRepository(owner),
                    ProviderProfileUpdateRepository(owner))
                user = owner.get(User, account_id)
                outcome["pid"] = owner.scalar(text("SELECT pg_backend_pid()"))
                started.set()
                try:
                    svc.update_profile(user, {"name": "Owner saved after admin"}, audit_context=None)
                except Exception as error:
                    outcome["error"] = error
                finally:
                    finished.set()

        thread = Thread(target=save)
        thread.start()
        assert started.wait(5)
        # Observe the actual lock wait, rather than rely on a timing sleep.
        import time
        deadline = time.monotonic() + 5
        blocked = False
        with Session(bind=bind) as observer:
            while time.monotonic() < deadline:
                blocked = bool(observer.scalar(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                                               {"pid": outcome["pid"]}))
                if blocked:
                    break
                time.sleep(0.02)
        try:
            assert blocked
        finally:
            administrator.commit()
            thread.join(10)
    assert finished.is_set() and "error" not in outcome, outcome
    latest = ProviderRepository(db).get_by_id(provider_id)
    assert latest.name == "Owner saved after admin"
    assert latest.description == "Committed by administrator"
