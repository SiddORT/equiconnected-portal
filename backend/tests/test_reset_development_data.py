"""Isolated-schema coverage for the operator-only development reset."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import (
    InvitationStatus, ProviderType, SubscriberRegistrationType, VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.language import Language
from app.models.provider import Provider
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.public_visit import PublicVisitDaily
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.specialization import Specialization
from app.models.subscriber import Subscriber
from app.models.system_settings import SystemSettings
from app.models.user import User
from app.repositories.user_repository import UserRepository
from scripts import reset_development_data as reset


@pytest.fixture(autouse=True)
def migration_bookkeeping(db):
    db.execute(text("CREATE TABLE test_equiconnected.alembic_version "
                    "(version_num varchar(32) PRIMARY KEY)"))
    db.execute(text("INSERT INTO test_equiconnected.alembic_version VALUES ('test_version')"))
    db.commit()
    yield
    db.rollback()
    db.execute(text("DROP TABLE test_equiconnected.alembic_version"))
    db.commit()


def seed(db):
    admin_role = Role(name="admin")
    member_role = Role(name="horse_owner")
    db.add_all([admin_role, member_role])
    db.flush()
    repo = UserRepository(db)
    admin = repo.create_user(email="admin@example.com",
                             password_hash=hash_password("StrongPassword2026!"),
                             role=admin_role, roles=[admin_role])
    assigned = repo.create_user(email="assigned@example.com",
                                password_hash=hash_password("StrongPassword2026!"),
                                role=member_role, roles=[member_role, admin_role])
    member = repo.create_user(email="member@example.com",
                              password_hash=hash_password("StrongPassword2026!"),
                              role=member_role, roles=[member_role])
    provider = Provider(provider_type=ProviderType.DOCTOR, name="Temporary",
                        visit_stability="STABLE_VISIT")
    db.add_all([provider, Language(name="English", code="en"),
                Specialization(name="Medicine"), SystemSettings()])
    db.flush()
    now = datetime.now(timezone.utc)
    db.add_all([
        RefreshToken(user_id=admin.id, token_hash="a" * 64,
                     expires_at=now + timedelta(days=1)),
        AuditLog(user_id=admin.id, action="admin.test"),
        EmailDeliveryLog(recipient_email="recipient@example.com",
                         purpose="provider_invitation", status="success"),
        Subscriber(email="subscriber@example.com",
                   registration_type=SubscriberRegistrationType.OTHER),
        PublicVisitDaily(visit_date=date(2026, 1, 1), visit_count=4),
        ProviderInvitation(provider_type=ProviderType.DOCTOR,
                           recipient_email="recipient@example.com", token_hash="b" * 64,
                           status=InvitationStatus.PENDING, created_by=member.id,
                           portal_user_id=member.id, provider_id=provider.id,
                           expires_at=now + timedelta(days=1), sent_at=now),
        ProviderRegistrationApplication(
            user_id=member.id, provider_id=provider.id,
            provider_type=ProviderType.DOCTOR, provider_name="Temporary",
            visit_stability=VisitStability.STABLE_VISIT, postal_code="12345",
        ),
    ])
    db.commit()
    return admin, assigned, member


def plan(db):
    return reset.build_plan(db, database="heliumdb", schema="test_equiconnected")


def backup(db, tmp_path):
    path = tmp_path / "before.dump"
    reset.make_backup(db, plan(db), path)
    return path


def execute(db, path):
    return reset.execute_reset(
        db, database="heliumdb", schema="test_equiconnected",
        confirmation="RESET_DEVELOPMENT_DATA:heliumdb:test_equiconnected",
        backup=path,
    )


def test_full_reset_preserves_masters_admins_and_login(db, client, tmp_path):
    admin, assigned, member = seed(db)
    admin_id, assigned_id, member_id = admin.id, assigned.id, member.id
    before = plan(db)
    path = backup(db, tmp_path)
    actual_before, after = execute(db, path)
    assert actual_before == before
    assert after.counts["users"] == 2
    assert after.counts["user_roles"] == 2
    assert all(after.counts[name] == 0 for name in reset.EXPECTED -
               reset.PRESERVED - {"users", "user_roles"})
    assert all(after.counts[name] == before.counts[name] for name in reset.PRESERVED)
    assert after.preserved_digest == before.preserved_digest
    db.expire_all()
    assert db.get(User, member_id) is None
    assert db.get(User, assigned_id) is not None
    assert db.get(User, admin_id) is not None
    assert client.post("/api/v1/auth/login", json={
        "email": "admin@example.com", "password": "StrongPassword2026!"
    }).status_code == 200
    # Logging in writes new activity and a session, so repeatability is checked
    # independently without a login between resets.


def test_preview_confirmation_and_wrong_target_refuse(db, tmp_path, monkeypatch):
    _, _, member = seed(db)
    assert plan(db).counts["users"] == 3
    assert db.get(User, member.id)
    with pytest.raises(reset.ResetError, match="identity"):
        reset.build_plan(db, database="wrong", schema="test_equiconnected")
    monkeypatch.setattr(reset, "get_settings", lambda: type("Settings", (), {
        "ENVIRONMENT": "production"
    })())
    with pytest.raises(reset.ResetError, match="development"):
        plan(db)
    monkeypatch.undo()
    with pytest.raises(reset.ResetError, match="Confirmation required"):
        reset.execute_reset(db, database="heliumdb", schema="test_equiconnected",
                            confirmation=None, backup=tmp_path / "absent")
    assert db.get(User, member.id)
    with pytest.raises(reset.ResetError, match="backup"):
        execute(db, tmp_path / "absent")
    assert db.get(User, member.id)


def test_repeat_reset_and_tampered_backup_refusal(db, tmp_path):
    seed(db)
    path = backup(db, tmp_path)
    with path.open("ab") as output:
        output.write(b"changed")
    with pytest.raises(reset.ResetError, match="Backup"):
        execute(db, path)
    path.unlink()
    (tmp_path / "before.dump.json").unlink()
    execute(db, backup(db, tmp_path))
    # The first backup describes the pre-reset snapshot. A new backup is
    # mandatory even for a no-op rerun.
    with pytest.raises(reset.ResetError, match="Backup"):
        execute(db, path)
    path.unlink()
    (tmp_path / "before.dump.json").unlink()
    execute(db, backup(db, tmp_path))
    assert plan(db).counts["users"] == 2


def test_unknown_schema_and_rollback_after_partial_deletes(db, tmp_path, monkeypatch):
    seed(db)
    db.execute(text("CREATE TABLE test_equiconnected.unexpected_reset_table (id int)"))
    db.commit()
    with pytest.raises(reset.ResetError, match="Unknown or missing"):
        plan(db)
    db.execute(text("DROP TABLE test_equiconnected.unexpected_reset_table"))
    db.commit()
    path = backup(db, tmp_path)
    original = reset._delete_order
    monkeypatch.setattr(reset, "_delete_order", lambda graph: ["audit_logs", "missing_table"])
    with pytest.raises(Exception):
        execute(db, path)
    assert plan(db).counts["audit_logs"] == 1
    assert plan(db).counts["users"] == 3
    monkeypatch.setattr(reset, "_delete_order", original)
    execute(db, path)


def test_no_active_admin_and_external_reference_refuse(db):
    admin, _, member = seed(db)
    db.execute(text("UPDATE test_equiconnected.users SET is_active = false "
                    "WHERE id <> :member"), {"member": member.id})
    db.commit()
    with pytest.raises(reset.ResetError, match="No active administrator"):
        plan(db)
    db.execute(text("UPDATE test_equiconnected.users SET is_active = true "
                    "WHERE id = :admin"), {"admin": admin.id})
    db.commit()
    db.execute(text("CREATE SCHEMA reset_external_check"))
    db.execute(text("CREATE TABLE reset_external_check.reference "
                    "(id uuid REFERENCES test_equiconnected.users(id))"))
    db.commit()
    try:
        with pytest.raises(reset.ResetError, match="Other schemas reference"):
            plan(db)
    finally:
        db.rollback()
        db.execute(text("DROP SCHEMA reset_external_check CASCADE"))
        db.commit()


@pytest.mark.parametrize("change", ["update", "replace"])
def test_same_count_data_change_invalidates_backup(db, tmp_path, change):
    seed(db)
    path = backup(db, tmp_path)
    if change == "update":
        db.execute(text("UPDATE test_equiconnected.providers SET name = 'Changed'"))
    else:
        db.execute(text("DELETE FROM test_equiconnected.subscribers"))
        db.add(Subscriber(email="different@example.com",
                          registration_type=SubscriberRegistrationType.OTHER))
    db.commit()
    current = plan(db)
    assert current.counts["providers"] == 1
    assert current.counts["subscribers"] == 1
    with pytest.raises(reset.ResetError, match="Backup does not match"):
        execute(db, path)
    assert plan(db) == current