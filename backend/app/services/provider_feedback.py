"""Provider-safe review projection, separate from member/admin review contracts."""
from app.models.enums import ProviderReviewStatus
from typing import Protocol
from app.schemas.review import ProviderFeedbackReview, ProviderVisibleReview


class MemberName(Protocol):
    first_name: str | None
    last_name: str | None


def masked_member_name(member: MemberName | None) -> str:
    """Never infer identity from full_name, email, or unstructured legacy names."""
    if member is None:
        return "Member"
    initials = []
    for value in (member.first_name, member.last_name):
        value = (value or "").strip()
        # Fail closed on contact-like or malformed structured names.
        if not value or not all(char.isalpha() or char in " '-’" for char in value):
            return "Member"
        initial = value[0].upper()
        if len(initial) != 1 or not initial.isalpha():
            return "Member"
        initials.append(f"{initial}.")
    return "Member " + " ".join(initials)


def visible_review(review, member) -> ProviderVisibleReview:
    return ProviderVisibleReview(
        id=review.id,
        rating=review.rating,
        comment=review.comment,
        reviewer_name=masked_member_name(member),
        created_at=review.created_at,
    )


def feedback_review(review, member) -> ProviderFeedbackReview:
    # A legacy published review can have its comment hidden without a status
    # transition. Pending/rejected records must retain their actual lifecycle.
    status = review.status
    if status == ProviderReviewStatus.PUBLISHED and not review.comment_visible:
        status = ProviderReviewStatus.HIDDEN
    return ProviderFeedbackReview(
        **visible_review(review, member).model_dump(),
        status=status,
    )
