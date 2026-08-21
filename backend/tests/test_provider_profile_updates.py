"""Provider-owned published-profile update review lifecycle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.enums import (
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderProfileUpdateStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.provider import Provider, ProviderLocation, ProviderProfileUpdate
from app.models.provider_registration import ProviderRegistrationApplication
from app.repositories.user_repository import UserRepository
from app.services.provider_profile_update_service import editable_profile_from_provider


def _login(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _portal_provider(
    db,
    admin,
    *,
    email: str,
    name: str,
    publication_status: PublicationStatus,
    registered_account: bool = False,
):
    users = UserRepository(db)
    role = users.get_role_by_name("provider") or users.create_role("provider", "Provider portal")
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=publication_status,
        description="Approved description",
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