"""Provider review privacy, lifecycle and read-only authorization boundaries."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from sqlalchemy import text
from fastapi.testclient import TestClient
from app.main import app

import pytest

from app.core.security import hash_password
from app.models.enums import ProviderReviewStatus
from app.models.provider import ProviderReview
from app.repositories.user_repository import UserRepository
from app.services.provider_feedback import masked_member_name
from tests.test_provider_portal import _approved_registration_provider, _login


@pytest.mark.parametrize(("first", "last", "expected"), [
    ("Amina", "Rider", "Member A. R."),
    (" Élodie ", "O’Neil", "Member É. O."),
    (None, None, "Member"),
    ("", "Rider", "Member"),
    ("person@example.com", "Rider", "Member"),
    ("123", "Rider", "Member"),
    ("ß", "Rider", "Member"),
])
def test_mask_structured_names_only(first, last, expected):
    member = SimpleNamespace(first_name=first, last_name=last, full_name="Never expose")
    assert masked_member_name(member) == expected
    assert masked_member_name(None) == "Member"


def _feedback_fixture(client, db):
    provider, account = _approved_registration_provider(db)
    other, _ = _approved_registration_provider(db, email="other-provider@portal.example.com")
    users = UserRepository(db)
    role = users.get_role_by_name("visitor") or users.create_role("visitor", "Visitor")
    statuses = [
        (ProviderReviewStatus.PENDING, True),
        (ProviderReviewStatus.PUBLISHED, True),
        (ProviderReviewStatus.REJECTED, True),
        (ProviderReviewStatus.HIDDEN, False),
        (ProviderReviewStatus.PUBLISHED, False),  # legacy hide
        (ProviderReviewStatus.PUBLISHED, True),  # rating-only
        (ProviderReviewStatus.PENDING, False),  # lifecycle wins over legacy flag
    ]
    reviews = []
    members = []
    for index, (status, visible) in enumerate(statuses):
        member = users.create_user(
            email=f"feedback-member-{index}@example.com",
            password_hash=hash_password("FeedbackMember9"),
            first_name="Amina", last_name="Rider", role=role, roles=[role],
        )
        member.email_verified_at = datetime.now(timezone.utc)
        review = ProviderReview(
            provider_id=provider.id, member_id=member.id, rating=index % 5 + 1,
            comment="" if index == 5 else f"Review {index}",
            status=status, comment_visible=visible,
            internal_note="Confidential administrator note",
            member_note="Private member-directed note",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index),
        )
        db.add(review)
        reviews.append(review)
        members.append(member)
    db.flush()
    db.add_all([
        ProviderReview(provider_id=other.id, member_id=members[0].id, rating=1,
                       comment="Other listing secret", status=ProviderReviewStatus.PUBLISHED),
        ProviderReview(provider_id=provider.id, member_id=members[0].id, rating=1,
                       comment="Deleted secret", status=ProviderReviewStatus.HIDDEN,
                       deleted_at=datetime.now(timezone.utc)),
    ])
    db.commit()
    token = _login(client, account.email, "RegisteredPass9")
    return provider, account, reviews, members, {"Authorization": f"Bearer {token}"}


def test_feedback_lifecycle_pagination_and_profile_privacy(client, db):
    provider, _, reviews, members, headers = _feedback_fixture(client, db)
    response = client.get("/api/v1/provider/portal/feedback?page_size=3", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"] == {"page": 1, "page_size": 3, "total": 7, "total_pages": 3}
    all_rows = payload["data"]
    for page in (2, 3):
        result = client.get(
            f"/api/v1/provider/portal/feedback?page_size=3&page={page}", headers=headers
        )
        assert result.status_code == 200
        all_rows += result.json()["data"]
    assert [r["id"] for r in all_rows] == [str(r.id) for r in reversed(reviews)]
    assert [r["status"] for r in all_rows] == [
        "PENDING", "PUBLISHED", "HIDDEN", "HIDDEN", "REJECTED", "PUBLISHED", "PENDING",
    ]
    assert all_rows[1]["comment"] == ""
    assert all_rows[3]["comment"] == "Review 3"
    for row in all_rows:
        assert set(row) == {"id", "rating", "comment", "reviewer_name", "created_at", "status"}
        assert row["reviewer_name"] == "Member A. R."
        assert str(provider.id) not in str(row)
        for member in members:
            assert str(member.id) not in str(row)
            assert member.email not in str(row)
    profile = client.get("/api/v1/provider/portal/profile", headers=headers)
    assert profile.status_code == 200, profile.text
    visible = profile.json()["visible_reviews"]
    assert [r["comment"] for r in visible] == ["Review 1"]
    assert visible[0]["reviewer_name"] == "Member A. R."
    assert set(visible[0]) == {"id", "rating", "comment", "reviewer_name", "created_at"}
    saved = client.patch("/api/v1/provider/portal/profile", headers=headers,
                         json={"name": "Updated synthetic clinic"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["visible_reviews"] == visible
    for data in (response.text, profile.text):
        for forbidden in ("Amina", "Rider", "Confidential administrator note", "Private member-directed note",
                          "Other listing secret", "Deleted secret"):
            assert forbidden not in data
    beyond = client.get("/api/v1/provider/portal/feedback?page=100", headers=headers)
    assert beyond.json()["data"] == []
    for query in ("page=0", "page_size=0", "page_size=101", f"provider_id={provider.id}"):
        assert client.get(f"/api/v1/provider/portal/feedback?{query}", headers=headers).status_code == 422


def test_feedback_does_not_hydrate_unrelated_member_contacts(client, db):
    """Feedback needs masked structured names, not decryptable member contacts.

    Synthetic incompatible storage reproduces the over-broad query failure;
    strict contact reads elsewhere must still fail closed.
    """
    _, _, _, members, headers = _feedback_fixture(client, db)
    db.execute(text("UPDATE users SET mobile_number = :value WHERE id = :id"),
               {"value": "synthetic-incompatible-contact", "id": members[0].id})
    db.commit()
    with TestClient(app, raise_server_exceptions=False) as transport:
        response = transport.get("/api/v1/provider/portal/feedback", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["meta"]["total"] == 7
    assert all(row["reviewer_name"] == "Member A. R." for row in response.json()["data"])


def test_feedback_roles_ownership_and_mutations(client, db, seeded_admin):
    provider, account, reviews, members, headers = _feedback_fixture(client, db)
    assert client.get("/api/v1/provider/portal/feedback").status_code == 401
    admin, password = seeded_admin
    admin_token = _login(client, admin.email, password)
    assert client.get("/api/v1/provider/portal/feedback",
                      headers={"Authorization": f"Bearer {admin_token}"}).status_code == 403
    member_token = _login(client, members[0].email, "FeedbackMember9")
    assert client.get("/api/v1/provider/portal/feedback",
                      headers={"Authorization": f"Bearer {member_token}"}).status_code == 403
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/v1/provider/portal/feedback", headers=headers).status_code == 405
    assert client.put(f"/api/v1/member/providers/{provider.id}/review", headers=headers,
                      json={"rating": 5, "comment": "Not allowed"}).status_code == 403
    assert client.patch(f"/api/v1/admin/reviews/{reviews[0].id}/status", headers=headers,
                        json={"status": "PUBLISHED", "expected_version": 1}).status_code == 403
    assert client.patch(f"/api/v1/admin/reviews/{reviews[0].id}/comment-visibility", headers=headers,
                        json={"comment_visible": False}).status_code == 403
    from app.models.provider_registration import ProviderRegistrationApplication
    application = db.query(ProviderRegistrationApplication).filter_by(user_id=account.id).one()
    other_application = db.query(ProviderRegistrationApplication).filter(
        ProviderRegistrationApplication.user_id != account.id
    ).one()
    from app.models.provider import DirectProviderPortalAccess
    ambiguous_link = DirectProviderPortalAccess(
        provider_id=other_application.provider_id,
        user_id=account.id, recipient_email=account.email,
    )
    db.add(ambiguous_link)
    db.commit()
    assert client.get("/api/v1/provider/portal/feedback", headers=headers).status_code == 403
    db.delete(ambiguous_link)
    db.commit()
    db.delete(application)
    db.commit()
    assert client.get("/api/v1/provider/portal/feedback", headers=headers).status_code == 403


def test_empty_provider_feedback(client, db):
    _, account = _approved_registration_provider(db)
    headers = {"Authorization": f"Bearer {_login(client, account.email, 'RegisteredPass9')}"}
    result = client.get("/api/v1/provider/portal/feedback", headers=headers)
    assert result.status_code == 200
    assert result.json() == {"data": [], "meta": {"page": 1, "page_size": 10, "total": 0, "total_pages": 0}}
