"""Stale review edits cannot resurrect replacements or misstate moderation history."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.enums import ProviderReviewStatus
from app.models.provider import ProviderReview
from app.models.provider_review_action import ProviderReviewAction
from app.repositories.audit_repository import AuditContext
from app.repositories.review_repository import ReviewRepository
from app.services.review_service import ReviewConflictError, ReviewService
from tests.conftest import TestingSessionLocal
from tests.test_member_provider_reviews import _member, _provider


def _service(session: TestingSessionLocal) -> ReviewService:
    return ReviewService(ReviewRepository(session))


def _member_edit(service, route, review, member_id, *, comment="Member edit"):
    if route == "review-id":
        return service.edit_member_review(
            review.id,
            member_id,
            rating=3,
            comment=comment,
            expected_version=review.version,
            audit_context=AuditContext(user_id=member_id, actor_type="member"),
        )
    return service.save_member_review(
        review.provider_id,
        member_id,
        rating=3,
        comment=comment,
        expected_version=review.version,
        audit_context=AuditContext(user_id=member_id, actor_type="member"),
    )


@pytest.mark.parametrize("route", ["review-id", "provider-member"])
@pytest.mark.parametrize("create_replacement", [False, True])
def test_delete_racing_member_edit_cannot_resurrect_or_edit_replacement(
    db, monkeypatch, route, create_replacement
):
    member = _member(db, f"delete-edit-{route}-{create_replacement}@example.com")
    provider = _provider(db, f"Delete race {route} {create_replacement}")
    original = ProviderReview(
        provider_id=provider.id,
        member_id=member.id,
        rating=5,
        comment="Original review",
        status=ProviderReviewStatus.PUBLISHED,
        version=1,
    )
    db.add(original)
    db.commit()
    original_id, member_id, provider_id = original.id, member.id, provider.id
    edit_service = _service(db)
    edit_repository = edit_service._repo
    update_member_review = edit_repository.update_member_review

    def delete_before_bound_update(
        review_id, update_member_id, *, rating, comment, expected_version
    ):
        # A committed delete happens after the service has read the review but
        # before its versioned write. Optionally submit a new active review in
        # another session to prove the stale edit remains bound to the old ID.
        with TestingSessionLocal() as racing_session:
            racing_service = _service(racing_session)
            racing_service.delete_member_review(
                original_id,
                member_id,
                expected_version=1,
                audit_context=AuditContext(user_id=member_id, actor_type="member"),
            )
            if create_replacement:
                replacement = racing_service.save_member_review(
                    provider_id,
                    member_id,
                    rating=4,
                    comment="Replacement submitted after deletion",
                    expected_version=None,
                    audit_context=AuditContext(
                        user_id=member_id, actor_type="member"
                    ),
                )
                assert replacement is not None

        return update_member_review(
            review_id,
            update_member_id,
            rating=rating,
            comment=comment,
            expected_version=expected_version,
        )

    monkeypatch.setattr(edit_repository, "update_member_review", delete_before_bound_update)

    with pytest.raises(ReviewConflictError):
        _member_edit(edit_service, route, original, member_id)

    db.expire_all()
    retained = db.get(ProviderReview, original_id)
    assert retained is not None
    assert retained.deleted_at is not None
    assert retained.comment == "Original review"
    assert retained.status == ProviderReviewStatus.PUBLISHED

    actions = (
        db.query(ProviderReviewAction)
        .filter_by(review_id=original_id)
        .order_by(ProviderReviewAction.version)
        .all()
    )
    assert [action.action for action in actions] == ["member_deleted"]
    assert [action.version for action in actions] == [2]

    active = (
        db.query(ProviderReview)
        .filter_by(provider_id=provider_id, member_id=member_id, deleted_at=None)
        .all()
    )
    if create_replacement:
        assert len(active) == 1
        assert active[0].id != original_id
        assert active[0].version == 1
        assert active[0].status == ProviderReviewStatus.PENDING
        assert active[0].comment == "Replacement submitted after deletion"
        assert (
            db.query(ProviderReviewAction)
            .filter_by(review_id=active[0].id)
            .count()
            == 1
        )
    else:
        assert active == []


@pytest.mark.parametrize("route", ["review-id", "provider-member"])
@pytest.mark.parametrize(
    ("prior_status", "expected_from_status"),
    [
        (ProviderReviewStatus.PUBLISHED, ProviderReviewStatus.PUBLISHED),
        (ProviderReviewStatus.REJECTED, ProviderReviewStatus.REJECTED),
    ],
)
def test_member_edit_history_captures_status_before_resubmission(
    db, route, prior_status, expected_from_status
):
    member = _member(
        db,
        f"review-status-history-{route}-{prior_status.value.lower()}@example.com",
    )
    provider = _provider(
        db, f"Review status history {route} {prior_status.value}"
    )
    review = ProviderReview(
        provider_id=provider.id,
        member_id=member.id,
        rating=4,
        comment="Previous moderation lifecycle",
        status=prior_status,
        version=1,
    )
    db.add(review)
    db.commit()

    updated = _member_edit(_service(db), route, review, member.id)

    assert updated.id == review.id
    assert updated.version == 2
    assert updated.status == ProviderReviewStatus.PENDING
    db.expire_all()
    actions = db.query(ProviderReviewAction).filter_by(review_id=review.id).all()
    assert len(actions) == 1
    assert actions[0].action == "member_edited"
    assert actions[0].from_status == expected_from_status
    assert actions[0].to_status == ProviderReviewStatus.PENDING
    assert actions[0].version == 2


def test_versioned_provider_edit_without_an_active_original_does_not_insert(
    db,
):
    member = _member(db, f"versioned-edit-no-active-{uuid4()}@example.com")
    provider = _provider(db, f"Versioned edit no active {uuid4()}")
    deleted_review = ProviderReview(
        provider_id=provider.id,
        member_id=member.id,
        rating=5,
        comment="Already deleted",
        status=ProviderReviewStatus.PUBLISHED,
        version=1,
        deleted_at=datetime.now(timezone.utc),
    )
    db.add(deleted_review)
    db.commit()

    with pytest.raises(ReviewConflictError):
        _service(db).save_member_review(
            provider.id,
            member.id,
            rating=3,
            comment="Stale edit must not create a new review",
            expected_version=1,
            audit_context=AuditContext(user_id=member.id, actor_type="member"),
        )

    db.expire_all()
    assert (
        db.query(ProviderReview)
        .filter_by(provider_id=provider.id, member_id=member.id)
        .count()
        == 1
    )
    assert db.get(ProviderReview, deleted_review.id).deleted_at is not None
    assert (
        db.query(ProviderReviewAction)
        .filter_by(review_id=deleted_review.id)
        .count()
        == 0
    )