"""Cross-session regression tests for member feedback and review writes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from app.models.enums import MemberFeedbackCategory, MemberFeedbackStatus, ProviderReviewStatus
from app.models.member_feedback import MemberFeedback, MemberFeedbackAction
from app.models.provider import ProviderReview
from app.models.provider_review_action import ProviderReviewAction
from app.repositories.audit_repository import AuditContext
from app.repositories.member_feedback_repository import MemberFeedbackRepository
from app.repositories.review_repository import ReviewRepository
from app.services.member_feedback_service import (
    FeedbackStaleVersionError,
    MemberFeedbackService,
)
from app.services.review_service import ReviewConflictError, ReviewService
from tests.conftest import TestingSessionLocal
from tests.test_member_provider_reviews import _member, _provider


def _feedback_service(session):
    return MemberFeedbackService(MemberFeedbackRepository(session))


def _review_service(session):
    return ReviewService(ReviewRepository(session))


def _load_actor(session, actor_id):
    from app.models.user import User

    actor = session.get(User, actor_id)
    assert actor is not None
    return actor


def test_same_idempotency_key_submitted_concurrently_creates_one_feedback_and_history(
    db
):
    member = _member(db, "feedback-concurrent-member@example.com")
    member_id = member.id
    key = uuid4()
    barrier = Barrier(2)

    def submit():
        session = TestingSessionLocal()
        try:
            actor = _load_actor(session, member_id)
            barrier.wait(timeout=10)
            feedback = _feedback_service(session).create(
                actor,
                category=MemberFeedbackCategory.SUGGESTION,
                subject="Concurrent request",
                rating=4,
                message="Same request submitted from two tabs.",
                idempotency_key=key,
                audit_context=AuditContext(user_id=member_id, actor_type="member"),
            )
            return feedback.id
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        feedback_ids = list(pool.map(lambda _: submit(), range(2)))

    assert feedback_ids[0] == feedback_ids[1]
    feedback = db.get(MemberFeedback, feedback_ids[0])
    assert feedback is not None
    assert feedback.message == "Same request submitted from two tabs."
    assert db.query(MemberFeedback).filter_by(member_id=member_id).count() == 1
    actions = (
        db.query(MemberFeedbackAction)
        .filter_by(feedback_id=feedback.id)
        .all()
    )
    assert len(actions) == 1
    assert actions[0].action == "submitted"
    assert actions[0].version == 1
    assert actions[0].actor_id == member_id
    assert actions[0].content_snapshot["message"] == feedback.message


def test_member_edit_and_admin_moderation_compete_on_feedback_version_once(
    db, seeded_admin
):
    member = _member(db, "feedback-racing-member@example.com")
    admin, _ = seeded_admin
    member_id, admin_id = member.id, admin.id
    feedback = _feedback_service(db).create(
        member,
        category=MemberFeedbackCategory.TECHNICAL_ISSUE,
        subject="A listing issue",
        rating=None,
        message="The original report.",
        idempotency_key=uuid4(),
        audit_context=AuditContext(user_id=member_id, actor_type="member"),
    )
    feedback_id = feedback.id
    barrier = Barrier(2)

    def member_edit():
        session = TestingSessionLocal()
        try:
            actor = _load_actor(session, member_id)
            service = _feedback_service(session)
            barrier.wait(timeout=10)
            service.update_member(
                feedback_id,
                actor,
                expected_version=1,
                changes={"message": "The member's edited report."},
                audit_context=AuditContext(user_id=member_id, actor_type="member"),
            )
            return "member"
        except FeedbackStaleVersionError:
            session.rollback()
            return "stale"
        finally:
            session.close()

    def admin_moderation():
        session = TestingSessionLocal()
        try:
            actor = _load_actor(session, admin_id)
            service = _feedback_service(session)
            barrier.wait(timeout=10)
            service.update_admin(
                feedback_id,
                actor,
                expected_version=1,
                changes={
                    "status": MemberFeedbackStatus.IN_REVIEW,
                    "internal_note": "Assigned to the directory team.",
                },
                audit_context=AuditContext(user_id=admin_id),
            )
            return "admin"
        except FeedbackStaleVersionError:
            session.rollback()
            return "stale"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [pool.submit(member_edit), pool.submit(admin_moderation)]
        results = [future.result(timeout=30) for future in outcomes]

    assert sorted(results) in (["admin", "stale"], ["member", "stale"])
    db.refresh(feedback)
    assert feedback.version == 2
    actions = (
        db.query(MemberFeedbackAction)
        .filter_by(feedback_id=feedback.id)
        .order_by(MemberFeedbackAction.version)
        .all()
    )
    assert [action.version for action in actions] == [1, 2]
    assert [action.action for action in actions].count("submitted") == 1
    assert len(actions) == 2
    winning = actions[-1]
    if results[0] == "member":
        assert feedback.message == "The member's edited report."
        assert feedback.status == MemberFeedbackStatus.PENDING
        assert winning.action == "edited"
        assert winning.content_snapshot["message"] == feedback.message
        assert winning.content_snapshot["internal_note"] is None
    else:
        assert feedback.message == "The original report."
        assert feedback.status == MemberFeedbackStatus.IN_REVIEW
        assert feedback.internal_note == "Assigned to the directory team."
        assert winning.action == "status_changed"
        assert winning.content_snapshot["status"] == "In review"
        assert winning.content_snapshot["internal_note"] == feedback.internal_note
        assert winning.actor_id == admin_id


def test_member_edit_and_admin_publication_race_has_one_review_history_winner(
    db, seeded_admin
):
    owner = _member(db, "review-racing-member@example.com")
    admin, _ = seeded_admin
    member_id, admin_id = owner.id, admin.id
    provider = _provider(db, "Review concurrency clinic")
    service = _review_service(db)
    review = service.save_member_review(
        provider.id,
        member_id,
        rating=3,
        comment="Original review.",
        expected_version=None,
        audit_context=AuditContext(user_id=member_id, actor_type="member"),
    )
    review_id = review.id
    barrier = Barrier(2)

    def member_edit():
        session = TestingSessionLocal()
        try:
            barrier.wait(timeout=10)
            updated = _review_service(session).edit_member_review(
                review_id,
                member_id,
                rating=5,
                comment="Revised member review.",
                expected_version=1,
                audit_context=AuditContext(user_id=member_id, actor_type="member"),
            )
            return ("member", updated.version)
        except ReviewConflictError:
            session.rollback()
            return ("stale", None)
        finally:
            session.close()

    def admin_publish():
        session = TestingSessionLocal()
        try:
            barrier.wait(timeout=10)
            updated = _review_service(session).update_admin_review(
                review_id,
                status=ProviderReviewStatus.PUBLISHED,
                expected_version=1,
                member_note="Approved.",
                internal_note="Approved after moderation.",
                update_member_note=True,
                update_internal_note=True,
                audit_context=AuditContext(user_id=admin_id),
            )
            return ("admin", updated.version)
        except ReviewConflictError:
            session.rollback()
            return ("stale", None)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(member_edit), pool.submit(admin_publish)]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(result[0] for result in results) in (
        ["admin", "stale"],
        ["member", "stale"],
    )
    winners = [result for result in results if result[0] != "stale"]
    assert len(winners) == 1
    assert winners[0][1] == 2

    db.expire_all()
    final_review = db.get(ProviderReview, review_id)
    assert final_review is not None
    history = (
        db.query(ProviderReviewAction)
        .filter_by(review_id=review_id)
        .order_by(ProviderReviewAction.version)
        .all()
    )
    assert [entry.version for entry in history] == [1, 2]
    assert history[0].action == "member_submitted"
    assert len(history) == 2
    if results[0][0] == "member":
        assert final_review.rating == 5
        assert final_review.comment == "Revised member review."
        assert final_review.status == ProviderReviewStatus.PENDING
        assert history[-1].action == "member_edited"
        assert history[-1].content_snapshot["comment"] == final_review.comment
    else:
        assert final_review.rating == 3
        assert final_review.comment == "Original review."
        assert final_review.status == ProviderReviewStatus.PUBLISHED
        assert final_review.member_note == "Approved."
        assert history[-1].action == "admin_published"
        assert history[-1].content_snapshot["status"] == "PUBLISHED"
        assert history[-1].content_snapshot["internal_note"] == (
            "Approved after moderation."
        )
        assert history[-1].actor_id == admin_id