"""Private member feedback lifecycle and persisted browsing-history coverage."""
from datetime import datetime, timezone
import uuid

from app.core.security import create_access_token, hash_password
from app.models.enums import ProviderStatus, ProviderType, PublicationStatus, VisitStability
from app.models.member_feedback import MemberFeedback, MemberFeedbackAction
from app.models.member_history import MemberBrowsingHistory
from app.models.provider import Provider
from app.repositories.user_repository import UserRepository

MEMBER_FEEDBACK = "/api/v1/member/feedback"
MEMBER_HISTORY = "/api/v1/member/history"
ADMIN_FEEDBACK = "/api/v1/admin/feedback"


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _member(db, email):
    users = UserRepository(db)
    role = users.get_role_by_name("horse_owner") or users.create_role("horse_owner")
    member = users.create_user(
        email=email,
        password_hash=hash_password("MemberPassword1"),
        role=role,
        roles=[role],
        first_name=email.split("@")[0].title(),
        last_name="Member",
    )
    member.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return member


def test_feedback_is_private_idempotent_editable_and_withdrawable(client, db, seeded_admin):
    member = _member(db, "feedback-owner@example.com")
    other = _member(db, "feedback-other@example.com")
    body = {
        "category": "Website / App",
        "subject": "Search page",
        "rating": 4,
        "message": "The filter reset is confusing.",
        "idempotency_key": str(uuid.uuid4()),
    }
    created = client.post(MEMBER_FEEDBACK, headers=_headers(member), json=body)
    assert created.status_code == 200
    item = created.json()
    assert item["status"] == "Pending"
    assert item["version"] == 1

    retried = client.post(MEMBER_FEEDBACK, headers=_headers(member), json=body)
    assert retried.status_code == 200
    assert retried.json()["id"] == item["id"]
    assert db.query(MemberFeedback).count() == 1
    assert db.query(MemberFeedbackAction).count() == 1

    assert client.get(MEMBER_FEEDBACK, headers=_headers(other)).json()["meta"]["total"] == 0
    assert client.get(
        f"{MEMBER_FEEDBACK}/{item['id']}", headers=_headers(other)
    ).status_code == 404

    update = client.patch(
        f"{MEMBER_FEEDBACK}/{item['id']}",
        headers=_headers(member),
        json={"expected_version": 1, "message": "Updated: filters reset unexpectedly."},
    )
    assert update.status_code == 200
    assert update.json()["version"] == 2
    assert update.json()["status"] == "Pending"

    stale = client.patch(
        f"{MEMBER_FEEDBACK}/{item['id']}",
        headers=_headers(member),
        json={"expected_version": 1, "subject": "Stale update"},
    )
    assert stale.status_code == 409
    withdrawn = client.delete(
        f"{MEMBER_FEEDBACK}/{item['id']}?expected_version=2",
        headers=_headers(member),
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["withdrawn_at"] is not None
    assert withdrawn.json()["version"] == 3
    assert client.get(
        f"{MEMBER_FEEDBACK}/counts", headers=_headers(member)
    ).json()["total"] == 0
    assert client.get(MEMBER_FEEDBACK, headers=_headers(member)).json()["meta"]["total"] == 0

    admin, _ = seeded_admin
    admin_detail = client.get(
        f"{ADMIN_FEEDBACK}/{item['id']}", headers=_headers(admin)
    )
    assert admin_detail.status_code == 200
    assert admin_detail.json()["history"][0]["content_snapshot"]["message"] == body["message"]
    assert admin_detail.json()["history"][-1]["action"] == "withdrawn"
    withdrawn_filter = client.get(
        f"{ADMIN_FEEDBACK}?status=withdrawn", headers=_headers(admin)
    )
    assert withdrawn_filter.status_code == 200
    assert withdrawn_filter.json()["meta"]["total"] == 1
    assert client.get(MEMBER_FEEDBACK, headers=_headers(admin)).status_code == 403


def test_admin_member_response_is_distinct_from_internal_note(client, db, seeded_admin):
    member = _member(db, "feedback-moderation@example.com")
    admin, _ = seeded_admin
    submitted = client.post(
        MEMBER_FEEDBACK,
        headers=_headers(member),
        json={
            "category": "Suggestion",
            "message": "Please add a clearer search summary.",
            "idempotency_key": str(uuid.uuid4()),
        },
    ).json()
    processed = client.patch(
        f"{ADMIN_FEEDBACK}/{submitted['id']}",
        headers=_headers(admin),
        json={
            "expected_version": 1,
            "status": "In review",
            "member_response": "Thanks, our team is reviewing this.",
            "internal_note": "Check related usability reports.",
        },
    )
    assert processed.status_code == 200
    assert processed.json()["history"][-1]["content_snapshot"]["internal_note"] == (
        "Check related usability reports."
    )

    member_detail = client.get(
        f"{MEMBER_FEEDBACK}/{submitted['id']}", headers=_headers(member)
    )
    assert member_detail.status_code == 200
    assert member_detail.json()["member_response"] == "Thanks, our team is reviewing this."
    assert "internal_note" not in member_detail.json()
    assert all("content_snapshot" not in event for event in member_detail.json()["history"])
    assert client.patch(
        f"{MEMBER_FEEDBACK}/{submitted['id']}",
        headers=_headers(member),
        json={"expected_version": 1, "message": "Should no longer be editable."},
    ).status_code == 409


def test_member_history_deduplicates_and_never_persists_coordinates(client, db):
    member = _member(db, "history-owner@example.com")
    other = _member(db, "history-other@example.com")
    key = str(uuid.uuid4())
    saved = client.post(
        MEMBER_HISTORY,
        headers=_headers(member),
        json={
            "event_key": key,
            "type": "search",
            "filters": {
                "name": "clinic",
                "minimum_rating": 4,
                "latitude": 25.2,
                "longitude": 55.3,
            },
        },
    )
    assert saved.status_code == 200
    assert saved.json()["filters"] == {"name": "clinic", "minimum_rating": 4.0}
    repeated = client.post(
        MEMBER_HISTORY,
        headers=_headers(member),
        json={"event_key": key, "type": "search", "filters": {"region": "Dubai"}},
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == saved.json()["id"]
    assert db.query(MemberBrowsingHistory).count() == 1

    isolated = client.get(MEMBER_HISTORY, headers=_headers(other)).json()
    assert isolated["meta"]["total"] == 0
    history = client.get(MEMBER_HISTORY, headers=_headers(member))
    assert history.status_code == 200
    assert history.json()["data"][0]["filters"] == {"name": "clinic", "minimum_rating": 4.0}


def test_provider_history_rejects_inaccessible_provider_ids(client, db):
    member = _member(db, "history-provider@example.com")
    private_provider = Provider(
        provider_type=ProviderType.CLINIC,
        name="Private listing",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=PublicationStatus.UNPUBLISHED,
    )
    db.add(private_provider)
    db.commit()
    recorded = client.post(
        MEMBER_HISTORY,
        headers=_headers(member),
        json={
            "event_key": str(uuid.uuid4()),
            "type": "provider",
            "provider_id": str(uuid.uuid4()),
        },
    )
    assert recorded.status_code == 404
    private_listing = client.post(
        MEMBER_HISTORY,
        headers=_headers(member),
        json={
            "event_key": str(uuid.uuid4()),
            "type": "provider",
            "provider_id": str(private_provider.id),
        },
    )
    assert private_listing.status_code == 404
    assert db.query(MemberBrowsingHistory).count() == 0


def test_feedback_validation_and_admin_filtering(client, db, seeded_admin):
    member = _member(db, "feedback-filter@example.com")
    admin, _ = seeded_admin
    invalid = client.post(
        MEMBER_FEEDBACK,
        headers=_headers(member),
        json={
            "category": "Other",
            "message": "   ",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert invalid.status_code == 422
    for required_null in ("category", "message"):
        null_field = {
            "category": "Other",
            "message": "A valid message for this test.",
            "idempotency_key": str(uuid.uuid4()),
            required_null: None,
        }
        rejected_null = client.post(
            MEMBER_FEEDBACK, headers=_headers(member), json=null_field
        )
        assert rejected_null.status_code == 422
    assert db.query(MemberFeedback).count() == 0
    valid = client.post(
        MEMBER_FEEDBACK,
        headers=_headers(member),
        json={
            "category": "Technical Issue",
            "rating": 5,
            "message": "The profile page displayed a temporary error.",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert valid.status_code == 200
    listed = client.get(
        f"{ADMIN_FEEDBACK}?status=Pending&category=Technical%20Issue&q=temporary",
        headers=_headers(admin),
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1
    assert listed.json()["data"][0]["submitter_email"] == member.email