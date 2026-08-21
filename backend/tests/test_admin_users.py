"""Approval workflow coverage for public account registrations."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.enums import PublicAccountApprovalStatus
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.audit_repository import AuditContext
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.public_account_service import (
    PublicAccountAlreadyDecidedError,
    PublicAccountService,
)


USERS_URL = "/api/v1/admin/users"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_token(client: TestClient, seeded_admin) -> str:
    admin, password = seeded_admin
    response = client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _public_roles(db):
    repo = UserRepository(db)
    owner = repo.get_role_by_name("horse_owner") or repo.create_role(
        "horse_owner", "Public horse owner"
    )
    manager = repo.get_role_by_name("stable_manager") or repo.create_role(
        "stable_manager", "Public stable manager"
    )
    return owner, manager


def _registrant(
    db,
    *,
    email: str,
    first_name: str = "Amina",
    roles: tuple[str, ...] = ("horse_owner",),
    verified: bool = False,
    status: PublicAccountApprovalStatus = PublicAccountApprovalStatus.PENDING,
) -> User:
    owner, manager = _public_roles(db)
    available = {"horse_owner": owner, "stable_manager": manager}
    selected = [available[name] for name in roles]
    user = UserRepository(db).create_user(
        email=email,
        password_hash=hash_password("HorseCare2026"),
        role=selected[0],
        roles=selected,
        first_name=first_name,
        last_name="Rider",
        mobile_number="+971 50 123 4567",
        country="United Arab Emirates",
        city="Dubai",
        approval_status=status,
    )
    if verified:
        user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return user


class TestAdminUserDirectory:
    def test_lists_filters_and_excludes_administrators(self, client, db, seeded_admin):
        admin_token = _admin_token(client, seeded_admin)
        _registrant(
            db,
            email="verified-owner@example.com",
            first_name="Zara",
            verified=True,
            status=PublicAccountApprovalStatus.APPROVED,
        )
        _registrant(
            db,
            email="pending-manager@example.com",
            first_name="Amina",
            roles=("stable_manager",),
        )

        response = client.get(
            USERS_URL,
            params={
                "search": "Amina",
                "role": "stable_manager",
                "approval_status": "PENDING",
                "email_verified": "false",
                "page_size": 10,
            },
            headers=_auth(admin_token),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["meta"] == {"page": 1, "page_size": 10, "total": 1, "total_pages": 1}
        assert body["data"][0]["email"] == "pending-manager@example.com"
        assert body["data"][0]["roles"] == ["stable_manager"]
        assert body["data"][0]["approval_status"] == "PENDING"
        assert "password_hash" not in body["data"][0]

    def test_detail_and_decision_are_immutable_and_audited(
        self, client, db, seeded_admin, monkeypatch
    ):
        sent: list[tuple[str, bool]] = []
        monkeypatch.setattr(
            EmailService,
            "send_account_decision_email",
            lambda _self, recipient, *, approved: sent.append((recipient, approved)),
        )
        admin_token = _admin_token(client, seeded_admin)
        registrant = _registrant(db, email="pending@example.com")

        detail = client.get(f"{USERS_URL}/{registrant.id}", headers=_auth(admin_token))
        assert detail.status_code == 200
        assert detail.json()["approval_decided_at"] is None

        rejected = client.post(
            f"{USERS_URL}/{registrant.id}/reject", headers=_auth(admin_token)
        )
        assert rejected.status_code == 200
        assert rejected.json()["approval_status"] == "REJECTED"
        assert rejected.json()["approval_decided_by"] == str(seeded_admin[0].id)
        assert sent == [("pending@example.com", False)]

        db.expire_all()
        stored = db.get(User, registrant.id)
        assert stored is not None
        assert stored.is_active is True
        assert stored.approval_status == PublicAccountApprovalStatus.REJECTED
        assert stored.approval_decided_at is not None
        event = db.query(AuditLog).filter(AuditLog.resource_id == str(registrant.id)).one()
        assert event.action == "public_account.rejected"
        assert event.user_id == seeded_admin[0].id

        repeated = client.post(
            f"{USERS_URL}/{registrant.id}/approve", headers=_auth(admin_token)
        )
        assert repeated.status_code == 409
        assert repeated.json()["detail"]["code"] == "approval_already_decided"

    def test_only_administrators_can_manage_registrants(self, client, db, seeded_admin):
        registrant = _registrant(db, email="member@example.com")
        response = client.get(f"{USERS_URL}/{registrant.id}")
        assert response.status_code == 401

        owner = UserRepository(db).get_role_by_name("horse_owner")
        assert owner is not None
        member = UserRepository(db).create_user(
            email="approved-member@example.com",
            password_hash=hash_password("HorseCare2026"),
            role=owner,
            approval_status=PublicAccountApprovalStatus.APPROVED,
        )
        member.email_verified_at = datetime.now(timezone.utc)
        db.commit()
        login = client.post(
            "/api/v1/auth/login",
            json={"email": member.email, "password": "HorseCare2026"},
        )
        assert login.status_code == 200
        assert client.get(USERS_URL, headers=_auth(login.json()["access_token"])).status_code == 403


class TestPublicAccountAccess:
    def test_approved_verified_account_can_sign_in_and_rejection_revokes_sessions(
        self, client, db, seeded_admin, monkeypatch
    ):
        monkeypatch.setattr(
            EmailService, "send_account_decision_email", lambda *_args, **_kwargs: None
        )
        approved = _registrant(
            db,
            email="access@example.com",
            verified=True,
            status=PublicAccountApprovalStatus.APPROVED,
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": approved.email, "password": "HorseCare2026"},
        )
        assert login.status_code == 200

        # A legacy access token or an already-issued member session must not
        # outlive a subsequent rejection. Public accounts cannot transition
        # from APPROVED to REJECTED, so model that prior session explicitly.
        registrant = _registrant(
            db,
            email="rejected-session@example.com",
            verified=True,
        )
        pair = AuthService(db)._issue_token_pair(registrant.id)
        db.commit()
        client.cookies.set("refresh_token", pair.refresh_token)
        access_token = pair.access_token

        admin, _ = seeded_admin
        PublicAccountService(db).decide(
            user_id=registrant.id,
            administrator_id=admin.id,
            decision=PublicAccountApprovalStatus.REJECTED,
            audit_context=AuditContext(user_id=admin.id),
        )

        db.expire_all()
        assert db.query(RefreshToken).filter(
            RefreshToken.user_id == registrant.id,
            RefreshToken.revoked_at.is_(None),
        ).count() == 0
        assert client.post("/api/v1/auth/refresh").status_code == 401
        denied = client.get("/api/v1/auth/me", headers=_auth(access_token))
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "account_rejected"

    def test_repeat_service_decision_cannot_overwrite_status(self, db, seeded_admin, monkeypatch):
        monkeypatch.setattr(
            EmailService, "send_account_decision_email", lambda *_args, **_kwargs: None
        )
        registrant = _registrant(db, email="immutable@example.com")
        admin, _ = seeded_admin
        service = PublicAccountService(db)
        service.decide(
            user_id=registrant.id,
            administrator_id=admin.id,
            decision=PublicAccountApprovalStatus.APPROVED,
            audit_context=AuditContext(user_id=admin.id),
        )

        try:
            service.decide(
                user_id=registrant.id,
                administrator_id=admin.id,
                decision=PublicAccountApprovalStatus.REJECTED,
                audit_context=AuditContext(user_id=admin.id),
            )
        except PublicAccountAlreadyDecidedError:
            pass
        else:
            raise AssertionError("A second approval decision must be rejected.")

        db.expire_all()
        assert db.get(User, registrant.id).approval_status == PublicAccountApprovalStatus.APPROVED