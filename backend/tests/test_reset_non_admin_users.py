"""Safety and outcome coverage for the non-admin account reset command."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enums import InvitationStatus, ProviderType
from app.models.invitation import ProviderInvitation
from app.models.profile import Horse, StableProfile
from app.models.provider import Provider, ProviderReview
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import EmailVerificationToken, User, UserRole
from app.repositories.user_repository import UserRepository
from scripts.reset_non_admin_users import (
    ConfirmationRequiredError,
    NoActiveAdministratorError,
    RESET_CONFIRMATION,
    RestrictiveReferenceError,
    build_reset_plan,
    execute_reset,
)


def _role(db, name: str) -> Role:
    role = Role(name=name)
    db.add(role)
    db.flush()
    return role


def _user(db, *, email: str, primary_role: Role, roles: list[Role] | None = None, active=True):
    return UserRepository(db).create_user(
        email=email,
        password_hash="test-only-password-hash",
        role=primary_role,
        roles=roles or [primary_role],
        is_active=active,
    )


def _seed_roles(db):
    return _role(db, "admin"), _role(db, "horse_owner")


def test_preview_lists_scope_without_mutating_data(db):
    admin_role, member_role = _seed_roles(db)
    admin = _user(db, email="admin@example.com", primary_role=admin_role)
    member = _user(db, email="member@example.com", primary_role=member_role)
    db.add(Horse(user_id=member.id, name="Cedar", sex="MARE"))
    db.commit()

    plan = build_reset_plan(db)

    assert [account.email for account in plan.retained_administrators] == [admin.email]
    assert [account.email for account in plan.targeted_users] == [member.email]
    assert plan.dependent_record_counts["horses"] == 1
    assert db.get(User, admin.id) is not None
    assert db.get(User, member.id) is not None


def test_reset_requires_exact_confirmation_and_does_not_delete(db):
    admin_role, member_role = _seed_roles(db)
    _user(db, email="admin@example.com", primary_role=admin_role)
    member = _user(db, email="member@example.com", primary_role=member_role)
    db.commit()

    with pytest.raises(ConfirmationRequiredError):
        execute_reset(db, confirmation=None)

    assert db.get(User, member.id) is not None


def test_confirmed_reset_preserves_admin_and_cleans_member_owned_records(db):
    admin_role, member_role = _seed_roles(db)
    admin = _user(db, email="admin@example.com", primary_role=admin_role)
    member = _user(db, email="member@example.com", primary_role=member_role)
    now = datetime.now(timezone.utc)
    admin_session = RefreshToken(
        user_id=admin.id,
        token_hash="a" * 64,
        expires_at=now + timedelta(days=1),
    )
    member_session = RefreshToken(
        user_id=member.id,
        token_hash="b" * 64,
        expires_at=now + timedelta(days=1),
    )
    audit = AuditLog(user_id=member.id, action="member.created")
    provider = Provider(
        provider_type=ProviderType.DOCTOR,
        name="Directory provider",
        visit_stability="STABLE_VISIT",
    )
    db.add(provider)
    db.flush()
    verification_token = EmailVerificationToken(
        user_id=member.id,
        token_hash="c" * 64,
        expires_at=now + timedelta(days=1),
    )
    review = ProviderReview(
        provider_id=provider.id,
        member_id=member.id,
        rating=5,
        comment="Excellent care",
    )
    db.add_all(
        [
            admin_session,
            member_session,
            verification_token,
            StableProfile(user_id=member.id, name="Member Stable"),
            Horse(user_id=member.id, name="Cedar", sex="MARE"),
            review,
            audit,
        ]
    )
    db.commit()
    admin_session_id = admin_session.id
    member_session_id = member_session.id
    audit_id = audit.id
    verification_token_id = verification_token.id
    review_id = review.id

    result = execute_reset(db, confirmation=RESET_CONFIRMATION)
    db.expire_all()

    assert result.deleted_user_count == 1
    assert db.get(User, admin.id) is not None
    assert db.get(User, member.id) is None
    assert db.get(RefreshToken, admin_session_id) is not None
    assert db.get(RefreshToken, member_session_id) is None
    assert db.get(EmailVerificationToken, verification_token_id) is None
    assert db.scalar(select(Horse).where(Horse.user_id == member.id)) is None
    assert db.scalar(select(StableProfile).where(StableProfile.user_id == member.id)) is None
    assert db.get(ProviderReview, review_id) is None
    assert db.scalar(select(UserRole).where(UserRole.user_id == member.id)) is None
    assert db.get(AuditLog, audit_id).user_id is None


def test_admin_role_assignment_preserves_account_even_if_primary_role_differs(db):
    admin_role, member_role = _seed_roles(db)
    assigned_admin = _user(
        db,
        email="assigned-admin@example.com",
        primary_role=member_role,
        roles=[member_role, admin_role],
    )
    member = _user(db, email="member@example.com", primary_role=member_role)
    db.commit()

    result = execute_reset(db, confirmation=RESET_CONFIRMATION)

    assert result.deleted_user_count == 1
    assert db.get(User, assigned_admin.id) is not None
    assert db.get(User, member.id) is None


def test_reset_refuses_when_no_active_admin_remains(db):
    admin_role, member_role = _seed_roles(db)
    inactive_admin = _user(
        db, email="inactive-admin@example.com", primary_role=admin_role, active=False
    )
    member = _user(db, email="member@example.com", primary_role=member_role)
    db.commit()

    with pytest.raises(NoActiveAdministratorError):
        execute_reset(db, confirmation=RESET_CONFIRMATION)

    assert db.get(User, inactive_admin.id) is not None
    assert db.get(User, member.id) is not None


def test_reset_refuses_transactionally_for_restrictive_provider_invitation(db):
    admin_role, member_role = _seed_roles(db)
    _user(db, email="admin@example.com", primary_role=admin_role)
    member = _user(db, email="member@example.com", primary_role=member_role)
    now = datetime.now(timezone.utc)
    db.add(
        ProviderInvitation(
            provider_type=ProviderType.DOCTOR,
            recipient_email="provider@example.com",
            token_hash="d" * 64,
            status=InvitationStatus.PENDING,
            expires_at=now + timedelta(days=1),
            sent_at=now,
            created_by=member.id,
        )
    )
    db.commit()

    with pytest.raises(RestrictiveReferenceError, match="provider invitations"):
        execute_reset(db, confirmation=RESET_CONFIRMATION)

    assert db.get(User, member.id) is not None
    assert db.scalar(select(ProviderInvitation).where(ProviderInvitation.created_by == member.id))