"""Doctor organization mapping tests."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.doctor import DoctorOrganization
from app.models.enums import (
    DoctorOrganizationStatus,
    InvitationStatus,
    OrganizationRequestStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.organization_request import OrganizationRequest
from app.models.provider import Provider, ProviderLocation


PUBLIC_INVITATIONS = "/api/v1/provider/invitations"
PUBLIC_SEARCH = "/api/v1/provider/organizations/search"
ADMIN_REQUESTS = "/api/v1/admin/organization-requests"


def _provider(db, provider_type: ProviderType, name: str, city: str | None = None) -> Provider:
    provider = Provider(
        provider_type=provider_type,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=PublicationStatus.PUBLISHED,
    )
    db.add(provider)
    db.flush()
    if city:
        db.add(
            ProviderLocation(
                provider_id=provider.id,
                address_line_1="1 Test Street",
                city=city,
                is_primary=True,
            )
        )
    db.commit()
    return provider


def _invitation(db, admin, provider: Provider, raw_token: str | None = None) -> str:
    token = raw_token or f"mapping-{uuid.uuid4()}"
    db.add(
        ProviderInvitation(
            provider_id=provider.id,
            provider_type=provider.provider_type,
            recipient_email=f"{provider.id}@example.com",
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            status=InvitationStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            sent_at=datetime.now(timezone.utc),
            created_by=admin.id,
        )
    )
    db.commit()
    return token


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def doctor_invitation(db, seeded_admin):
    admin, _ = seeded_admin
    doctor = _provider(db, ProviderType.DOCTOR, "Dr Mapping")
    return doctor, _invitation(db, admin, doctor)


@pytest.fixture()
def admin_headers(client, seeded_admin):
    admin, password = seeded_admin
    return _login(client, admin.email, password)


def test_search_returns_only_organizations_and_is_paginated(client, db):
    _provider(db, ProviderType.HOSPITAL, "Alpha Hospital", "Nairobi")
    _provider(db, ProviderType.CLINIC, "Beta Clinic", "Mombasa")
    _provider(db, ProviderType.DOCTOR, "Dr Alpha", "Nairobi")

    response = client.get(PUBLIC_SEARCH, params={"q": "Nairobi", "page": 1, "page_size": 1})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"]["total"] == 1
    assert len(payload["data"]) == 1
    assert payload["data"][0]["provider_type"] == "HOSPITAL"
    assert payload["data"][0]["city"] == "Nairobi"


def test_search_type_filter_rejects_doctor(client, db):
    _provider(db, ProviderType.DOCTOR, "Dr Hidden")
    response = client.get(PUBLIC_SEARCH, params={"type": "DOCTOR"})
    assert response.status_code == 422


def test_search_does_not_expose_unpublished_or_draft_organizations(client, db):
    visible = _provider(db, ProviderType.HOSPITAL, "Visible Hospital")
    unpublished = _provider(db, ProviderType.CLINIC, "Hidden Clinic")
    unpublished.publication_status = PublicationStatus.UNPUBLISHED
    draft = _provider(db, ProviderType.HOSPITAL, "Draft Hospital")
    draft.status = ProviderStatus.DRAFT
    db.commit()

    response = client.get(PUBLIC_SEARCH)

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert str(visible.id) in ids
    assert str(unpublished.id) not in ids
    assert str(draft.id) not in ids


def test_associate_existing_organization_is_pending(client, db, doctor_invitation):
    doctor, token = doctor_invitation
    hospital = _provider(db, ProviderType.HOSPITAL, "Pending Hospital")

    response = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organizations",
        json={"organization_id": str(hospital.id)},
    )

    assert response.status_code == 201, response.text
    relationship = db.scalar(
        select(DoctorOrganization).where(
            DoctorOrganization.doctor_id == doctor.id,
            DoctorOrganization.organization_id == hospital.id,
        )
    )
    assert relationship is not None
    assert relationship.status == DoctorOrganizationStatus.PENDING


def test_associate_doctor_target_is_rejected(client, db, doctor_invitation):
    _, token = doctor_invitation
    other_doctor = _provider(db, ProviderType.DOCTOR, "Dr Invalid Target")

    response = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organizations",
        json={"organization_id": str(other_doctor.id)},
    )

    assert response.status_code == 422


def test_duplicate_relationship_is_conflict(client, db, doctor_invitation):
    _, token = doctor_invitation
    clinic = _provider(db, ProviderType.CLINIC, "Duplicate Clinic")
    url = f"{PUBLIC_INVITATIONS}/{token}/organizations"
    body = {"organization_id": str(clinic.id)}

    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 409


def test_new_organization_request_is_created(client, db, doctor_invitation):
    doctor, token = doctor_invitation

    response = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organization-requests",
        json={
            "organization_name": "New Community Clinic",
            "organization_type": "CLINIC",
            "contact_email": "clinic@example.com",
            "location_hint": "Westlands",
        },
    )

    assert response.status_code == 201, response.text
    request = db.get(OrganizationRequest, uuid.UUID(response.json()["id"]))
    assert request.doctor_provider_id == doctor.id
    assert request.status == OrganizationRequestStatus.PENDING


def test_duplicate_prevention_returns_suggestions(client, db, doctor_invitation):
    _, token = doctor_invitation
    existing = _provider(db, ProviderType.HOSPITAL, "Central Hospital")

    response = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organization-requests",
        json={"organization_name": "Central Hosp", "organization_type": "HOSPITAL"},
    )

    assert response.status_code == 409, response.text
    suggestions = response.json()["detail"]["suggestions"]
    assert any(item["id"] == str(existing.id) for item in suggestions)


def test_confirm_no_match_bypasses_suggestions(client, db, doctor_invitation):
    _, token = doctor_invitation
    _provider(db, ProviderType.HOSPITAL, "Central Hospital")

    response = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organization-requests",
        json={
            "organization_name": "Central Hosp",
            "organization_type": "HOSPITAL",
            "confirm_no_match": True,
        },
    )

    assert response.status_code == 201, response.text


def test_admin_approve_creates_draft_provider_and_active_relationship(
    client, db, seeded_admin, admin_headers, doctor_invitation
):
    doctor, token = doctor_invitation
    created = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organization-requests",
        json={"organization_name": "Approved Clinic", "organization_type": "CLINIC"},
    )
    request_id = created.json()["id"]

    response = client.post(f"{ADMIN_REQUESTS}/{request_id}/approve", headers=admin_headers)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"
    provider = db.scalar(select(Provider).where(Provider.name == "Approved Clinic"))
    assert provider is not None
    assert provider.status == ProviderStatus.DRAFT
    assert provider.publication_status == PublicationStatus.UNPUBLISHED
    relationship = db.scalar(
        select(DoctorOrganization).where(
            DoctorOrganization.doctor_id == doctor.id,
            DoctorOrganization.organization_id == provider.id,
        )
    )
    assert relationship is not None
    assert relationship.status == DoctorOrganizationStatus.ACTIVE


def test_admin_reject_marks_request_rejected(
    client, db, seeded_admin, admin_headers, doctor_invitation
):
    _, token = doctor_invitation
    created = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organization-requests",
        json={"organization_name": "Rejected Hospital", "organization_type": "HOSPITAL"},
    )

    response = client.post(
        f"{ADMIN_REQUESTS}/{created.json()['id']}/reject", headers=admin_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REJECTED"


def test_admin_endpoints_require_authentication(client):
    assert client.get(ADMIN_REQUESTS).status_code == 401
    assert client.post(f"{ADMIN_REQUESTS}/{uuid.uuid4()}/approve").status_code == 401


def test_public_mapping_requires_valid_doctor_invitation(client, db, seeded_admin):
    admin, _ = seeded_admin
    hospital = _provider(db, ProviderType.HOSPITAL, "Invited Hospital")
    target = _provider(db, ProviderType.CLINIC, "Target Clinic")
    hospital_token = _invitation(db, admin, hospital)

    invalid = client.post(
        f"{PUBLIC_INVITATIONS}/invalid-token/organizations",
        json={"organization_id": str(target.id)},
    )
    wrong_type = client.post(
        f"{PUBLIC_INVITATIONS}/{hospital_token}/organizations",
        json={"organization_id": str(target.id)},
    )

    assert invalid.status_code == 404
    assert wrong_type.status_code == 422


def test_expired_invitation_is_rejected_by_mapping_endpoints(
    client, db, seeded_admin
):
    admin, _ = seeded_admin
    doctor = _provider(db, ProviderType.DOCTOR, "Dr Expired")
    target = _provider(db, ProviderType.HOSPITAL, "Target Hospital")
    token = _invitation(db, admin, doctor)
    invitation = db.scalar(
        select(ProviderInvitation).where(
            ProviderInvitation.token_hash == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    invitation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    association = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organizations",
        json={"organization_id": str(target.id)},
    )
    request = client.post(
        f"{PUBLIC_INVITATIONS}/{token}/organization-requests",
        json={"organization_name": "Late Clinic", "organization_type": "CLINIC"},
    )

    assert association.status_code == 410
    assert request.status_code == 410