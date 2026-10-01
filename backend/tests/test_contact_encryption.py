"""Security and storage-boundary regressions for encrypted contact persistence."""
from __future__ import annotations

import base64
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import insert, text, update
from sqlalchemy.exc import IntegrityError

from app.db.contact_types import (
    ContactPersistenceError,
    prepare_contact_values,
    protect_snapshot_values,
)
from app.models.contact_enquiry import ContactEnquiry
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import (
    ContactEnquiryType,
    ProviderApplicationStatus,
    ProviderType,
    SubscriberRegistrationType,
    VisitStability,
)
from app.models.invitation import ProviderInvitation
from app.models.member_feedback import MemberFeedback, MemberFeedbackAction
from app.models.organization_request import OrganizationRequest
from app.models.profile import StableProfile
from app.models.provider import (
    DirectProviderPortalAccess,
    Provider,
    ProviderEmail,
    ProviderPhone,
    ProviderProfileUpdate,
    ProviderReview,
)
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.provider_review_action import ProviderReviewAction
from app.models.role import Role
from app.models.subscriber import Subscriber
from app.models.user import User
from app.services import contact_encryption
from app.services.contact_encryption import (
    ContactCiphertextInvalid,
    ContactEncryptionUnavailable,
    contact_blind_index,
    decrypt_contact,
    encrypt_contact,
)
from tests.conftest import TestingSessionLocal


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _settings(keyring: dict[str, str], active_id: str, index_key: bytes):
    from types import SimpleNamespace

    return SimpleNamespace(
        CONTACT_ENCRYPTION_KEYRING=json.dumps(keyring),
        CONTACT_ENCRYPTION_ACTIVE_KEY_ID=active_id,
        CONTACT_BLIND_INDEX_KEY=_b64(index_key),
    )


def test_aes_gcm_contact_envelopes_are_randomized_and_bound_to_record_and_field():
    value = "person@example.invalid"
    first = encrypt_contact(value, table="users", record_id="user-1", field="email")
    second = encrypt_contact(value, table="users", record_id="user-1", field="email")

    assert first != second
    assert first.startswith("v1.test-ephemeral.")
    assert decrypt_contact(first, table="users", record_id="user-1", field="email") == value
    with pytest.raises(ContactCiphertextInvalid):
        decrypt_contact(first, table="users", record_id="user-2", field="email")
    with pytest.raises(ContactCiphertextInvalid):
        decrypt_contact(first, table="users", record_id="user-1", field="mobile_number")


def test_keyring_fails_closed_but_reads_retained_key_versions(monkeypatch):
    old_key = secrets.token_bytes(32)
    new_key = secrets.token_bytes(32)
    index_key = secrets.token_bytes(32)
    old_settings = _settings({"old": _b64(old_key)}, "old", index_key)
    monkeypatch.setattr(contact_encryption, "get_settings", lambda: old_settings)
    legacy_envelope = encrypt_contact(
        "retained@example.invalid", table="users", record_id="retained", field="email"
    )

    monkeypatch.setattr(
        contact_encryption,
        "get_settings",
        lambda: _settings(
            {"old": _b64(old_key), "new": _b64(new_key)}, "new", index_key
        ),
    )
    assert decrypt_contact(
        legacy_envelope, table="users", record_id="retained", field="email"
    ) == "retained@example.invalid"
    assert encrypt_contact(
        "new@example.invalid", table="users", record_id="new", field="email"
    ).startswith("v1.new.")

    monkeypatch.setattr(
        contact_encryption,
        "get_settings",
        lambda: _settings({}, "missing", index_key),
    )
    with pytest.raises(ContactEncryptionUnavailable):
        encrypt_contact("nobody@example.invalid", table="users", record_id="1", field="email")
    with pytest.raises(ContactEncryptionUnavailable):
        decrypt_contact(
            legacy_envelope, table="users", record_id="retained", field="email"
        )

    monkeypatch.setattr(
        contact_encryption,
        "get_settings",
        lambda: _settings({"old": _b64(old_key)}, "old", old_key),
    )
    with pytest.raises(ContactEncryptionUnavailable):
        contact_blind_index("person@example.invalid", table="users", field="email")

    monkeypatch.setattr(
        contact_encryption,
        "get_settings",
        lambda: _settings({"new": _b64(new_key)}, "new", index_key),
    )
    with pytest.raises(ContactEncryptionUnavailable):
        decrypt_contact(
            legacy_envelope, table="users", record_id="retained", field="email"
        )


def test_invalid_key_material_and_tampered_envelopes_are_rejected(monkeypatch):
    index_key = secrets.token_bytes(32)
    monkeypatch.setattr(
        contact_encryption,
        "get_settings",
        lambda: _settings({"broken": _b64(secrets.token_bytes(16))}, "broken", index_key),
    )
    with pytest.raises(ContactEncryptionUnavailable):
        encrypt_contact("a@example.invalid", table="users", record_id="1", field="email")

    good_key = secrets.token_bytes(32)
    monkeypatch.setattr(
        contact_encryption,
        "get_settings",
        lambda: _settings({"valid": _b64(good_key)}, "valid", index_key),
    )
    envelope = encrypt_contact("a@example.invalid", table="users", record_id="1", field="email")
    changed = envelope[:-5] + ("A" if envelope[-5] != "A" else "B") + envelope[-4:]
    with pytest.raises(ContactCiphertextInvalid):
        decrypt_contact(changed, table="users", record_id="1", field="email")


def _contact(tag: str) -> str:
    return f"{tag}.{uuid4().hex[:12]}@contact.invalid"


def _raw_value(db, table: str, column: str, key_column: str, key):
    return db.execute(
        text(f"SELECT {column} FROM {table} WHERE {key_column} = :key"),
        {"key": key},
    ).scalar_one()


def _seed_contact_inventory_records(db):
    """Check every direct contact column and protected historical JSON copy."""
    role = Role(name="contact-storage-test", description="Test only")
    db.add(role)
    db.flush()

    user_id = uuid4()
    user_email, user_mobile = _contact("user"), "+971501234567"
    user = User(
        id=user_id,
        email=user_email,
        mobile_number=user_mobile,
        password_hash="not-a-real-password-hash",
        role_id=role.id,
    )
    db.add(user)
    db.flush()

    provider_id = uuid4()
    provider_email, provider_phone, emergency = (
        _contact("provider"),
        "+971502345678",
        "+971503456789",
    )
    provider = Provider(
        id=provider_id,
        provider_type=ProviderType.DOCTOR,
        name="Encrypted contact provider",
        visit_stability=VisitStability.STABLE_VISIT,
        email=provider_email,
        phone=provider_phone,
        emergency_contact_number=emergency,
    )
    db.add(provider)
    db.flush()

    app_id = uuid4()
    application_emergency = "+971504567890"
    application = ProviderRegistrationApplication(
        id=app_id,
        user_id=user_id,
        provider_type=ProviderType.DOCTOR,
        provider_name="Encrypted applicant",
        visit_stability=VisitStability.STABLE_VISIT,
        postal_code="12345",
        emergency_contact_number=application_emergency,
        review_status=ProviderApplicationStatus.AWAITING_EMAIL_VERIFICATION,
    )
    profile_id = uuid4()
    stable_email, stable_phone = _contact("stable"), "+971505678901"
    stable_profile = StableProfile(
        id=profile_id,
        user_id=user_id,
        name="Encrypted stable",
        contact_email=stable_email,
        contact_phone=stable_phone,
    )

    provider_email_id, provider_phone_id = uuid4(), uuid4()
    provider_email_value, provider_phone_value = _contact("provider-collection"), "+971506789012"
    email_row = ProviderEmail(
        id=provider_email_id,
        provider_id=provider_id,
        email=provider_email_value,
    )
    phone_row = ProviderPhone(
        id=provider_phone_id,
        provider_id=provider_id,
        country_code="+971",
        number=provider_phone_value,
    )
    organization_id = uuid4()
    organization_email = _contact("organization")
    organization = OrganizationRequest(
        id=organization_id,
        doctor_provider_id=provider_id,
        organization_name="Encrypted organization",
        organization_type=ProviderType.CLINIC,
        contact_email=organization_email,
    )

    invitation_id = uuid4()
    invitation_email = _contact("invitation")
    now = datetime.now(timezone.utc)
    invitation = ProviderInvitation(
        id=invitation_id,
        provider_id=provider_id,
        provider_type=ProviderType.DOCTOR,
        recipient_email=invitation_email,
        token_hash=secrets.token_hex(32),
        expires_at=now,
        sent_at=now,
        created_by=user_id,
    )
    access_email = _contact("direct-access")
    direct_access = DirectProviderPortalAccess(
        provider_id=provider_id,
        user_id=user_id,
        recipient_email=access_email,
    )
    log_id, log_email = uuid4(), _contact("delivery")
    delivery_log = EmailDeliveryLog(
        id=log_id,
        recipient_email=log_email,
        purpose="account_verification",
        status="success",
    )
    enquiry_id, enquiry_email, enquiry_phone = (
        uuid4(),
        _contact("enquiry"),
        "+971507890123",
    )
    enquiry = ContactEnquiry(
        id=enquiry_id,
        name="Encrypted sender",
        email=enquiry_email,
        enquiry_type=ContactEnquiryType.GENERAL.value,
        phone=enquiry_phone,
        message="A request with no contact copied into this free text.",
    )
    subscriber_id, subscriber_email = uuid4(), _contact("subscriber")
    subscriber = Subscriber(
        id=subscriber_id,
        email=subscriber_email,
        registration_type=SubscriberRegistrationType.OTHER,
    )
    feedback_id, feedback_email = uuid4(), _contact("feedback")
    feedback = MemberFeedback(
        id=feedback_id,
        member_id=user_id,
        submitter_name="Encrypted submitter",
        submitter_email=feedback_email,
        category="Other",
        message="A structured feedback message.",
    )
    db.add_all(
        [
            application,
            stable_profile,
            email_row,
            phone_row,
            organization,
            invitation,
            direct_access,
            delivery_log,
            enquiry,
            subscriber,
            feedback,
        ]
    )
    db.flush()

    feedback_action_id, feedback_actor_email = uuid4(), _contact("feedback-action")
    feedback_snapshot_email = _contact("feedback-snapshot")
    feedback_action = MemberFeedbackAction(
        id=feedback_action_id,
        feedback_id=feedback_id,
        actor_name="Test operator",
        actor_email=feedback_actor_email,
        actor_type="admin",
        action="updated",
        version=1,
        content_snapshot={
            "submitter_email": feedback_snapshot_email,
            "message": "Snapshot without contact data in free text.",
        },
    )
    review_id, review_action_id = uuid4(), uuid4()
    review = ProviderReview(
        id=review_id,
        provider_id=provider_id,
        member_id=user_id,
        rating=5,
        comment="A provider review.",
    )
    db.add_all([review, feedback_action])
    db.flush()

    review_actor_email, review_snapshot_email = _contact("review-action"), _contact("review-snapshot")
    review_action = ProviderReviewAction(
        id=review_action_id,
        review_id=review_id,
        actor_name="Test operator",
        actor_email=review_actor_email,
        actor_type="admin",
        action="published",
        version=1,
        content_snapshot={
            "email": review_snapshot_email,
            "comment": "Review snapshot.",
        },
    )
    update_id = uuid4()
    profile_update = ProviderProfileUpdate(
        id=update_id,
        provider_id=provider_id,
        submitted_at=now,
        proposed_profile={
            "email": _contact("proposed"),
            "phone": "+971508901234",
            "emergency_contact_number": "+971509012345",
            "emails": [{"email": _contact("proposed-collection")}],
            "phones": [{"country_code": "+971", "number": "+971501112223"}],
        },
        base_profile={
            "email": _contact("base"),
            "phone": "+971501223344",
            "emails": [{"email": _contact("base-collection")}],
            "phones": [{"country_code": "+971", "number": "+971501334455"}],
        },
    )
    db.add_all([review_action, profile_update])
    db.commit()

    direct_contacts = {
        ("users", "email"): (user_id, user_email),
        ("users", "mobile_number"): (user_id, user_mobile),
        ("providers", "email"): (provider_id, provider_email),
        ("providers", "phone"): (provider_id, provider_phone),
        ("providers", "emergency_contact_number"): (provider_id, emergency),
        ("provider_registration_applications", "emergency_contact_number"): (
            app_id,
            application_emergency,
        ),
        ("stable_profiles", "contact_email"): (profile_id, stable_email),
        ("stable_profiles", "contact_phone"): (profile_id, stable_phone),
        ("provider_emails", "email"): (provider_email_id, provider_email_value),
        ("provider_phones", "number"): (provider_phone_id, provider_phone_value),
        ("organization_requests", "contact_email"): (organization_id, organization_email),
        ("provider_invitations", "recipient_email"): (invitation_id, invitation_email),
        ("direct_provider_portal_access", "recipient_email"): (provider_id, access_email),
        ("email_delivery_logs", "recipient_email"): (log_id, log_email),
        ("contact_enquiries", "email"): (enquiry_id, enquiry_email),
        ("contact_enquiries", "phone"): (enquiry_id, enquiry_phone),
        ("subscribers", "email"): (subscriber_id, subscriber_email),
        ("member_feedback", "submitter_email"): (feedback_id, feedback_email),
        ("member_feedback_actions", "actor_email"): (
            feedback_action_id,
            feedback_actor_email,
        ),
        ("provider_review_actions", "actor_email"): (
            review_action_id,
            review_actor_email,
        ),
    }
    primary_keys = {
        "direct_provider_portal_access": "provider_id",
    }
    for (table, column), (record_id, cleartext) in direct_contacts.items():
        pk_column = primary_keys.get(table, "id")
        raw = _raw_value(db, table, column, pk_column, record_id)
        assert raw.startswith("ecv1:")
        packed = json.loads(
            base64.b64decode(raw.removeprefix("ecv1:").encode(), altchars=b"-_")
        )
        assert packed["table"] == table
        assert packed["record"] == str(record_id)
        assert packed["field"] == column
        assert packed["ciphertext"].startswith("v1.")
        assert cleartext not in raw
        stored_index = _raw_value(
            db, table, f"{column}_blind_index", pk_column, record_id
        )
        assert stored_index == contact_blind_index(
            cleartext, table=table, field=column
        )
        assert cleartext not in stored_index

    snapshot_rows = [
        ("member_feedback_actions", feedback_action_id, "content_snapshot", {
            "submitter_email": feedback_snapshot_email,
        }),
        ("provider_review_actions", review_action_id, "content_snapshot", {
            "email": review_snapshot_email,
        }),
        ("provider_profile_updates", update_id, "proposed_profile", {
            "email": profile_update.proposed_profile["email"],
            "phone": profile_update.proposed_profile["phone"],
            "emergency_contact_number": profile_update.proposed_profile[
                "emergency_contact_number"
            ],
            "emails.0.email": profile_update.proposed_profile["emails"][0]["email"],
            "phones.0.number": profile_update.proposed_profile["phones"][0]["number"],
        }),
        ("provider_profile_updates", update_id, "base_profile", {
            "email": profile_update.base_profile["email"],
            "phone": profile_update.base_profile["phone"],
            "emails.0.email": profile_update.base_profile["emails"][0]["email"],
            "phones.0.number": profile_update.base_profile["phones"][0]["number"],
        }),
    ]
    assert {
        table for table, _record_id, _column, _contacts in snapshot_rows
    } == {
        "member_feedback_actions",
        "provider_review_actions",
        "provider_profile_updates",
    }
    for table, record_id, column, contacts in snapshot_rows:
        raw_snapshot = _raw_value(db, table, column, "id", record_id)
        serialized = json.dumps(raw_snapshot, sort_keys=True)
        for cleartext in contacts.values():
            assert cleartext not in serialized
        for dotted_path, cleartext in contacts.items():
            value = raw_snapshot
            for part in dotted_path.split("."):
                value = value[int(part)] if part.isdigit() else value[part]
            assert isinstance(value, str) and value.startswith("v1.")
            assert decrypt_contact(
                value,
                table=table,
                record_id=str(record_id),
                field=f"{column}:{dotted_path}",
            ) == cleartext
    return direct_contacts, snapshot_rows


def test_raw_sql_contact_inventory_contains_only_ciphertext(db):
    _seed_contact_inventory_records(db)


def test_core_preparation_is_the_only_plaintext_core_write_escape_hatch(db):
    role = Role(name="contact-core-test", description="Test only")
    db.add(role)
    db.flush()
    db.commit()
    with pytest.raises(ContactPersistenceError):
        db.execute(
            insert(User.__table__).values(
                id=uuid4(),
                email="bypass@example.invalid",
                password_hash="not-a-real-password-hash",
                role_id=role.id,
            )
        )
    db.rollback()

    user_id = uuid4()
    values = {
        User.__table__.c.id: user_id,
        User.__table__.c.password_hash: "not-a-real-password-hash",
        User.__table__.c.role_id: role.id,
        **prepare_contact_values(User, str(user_id), {"email": "core@example.invalid"}),
    }
    db.execute(insert(User.__table__).values(values))
    db.commit()
    stored = db.get(User, user_id)
    assert stored.email == "core@example.invalid"


def test_plaintext_bulk_write_cannot_bypass_orm_boundary(db):
    role = Role(name="contact-bulk-test", description="Test only")
    db.add(role)
    db.flush()
    user = User(
        id=uuid4(),
        email="bulk-bypass@example.invalid",
        password_hash="not-a-real-password-hash",
        role_id=role.id,
    )
    with pytest.raises(ContactPersistenceError):
        db.bulk_save_objects([user])
    db.rollback()


def test_protected_snapshot_core_helper_blocks_plain_json_bypass(db):
    role = Role(name="contact-snapshot-core-test", description="Test only")
    db.add(role)
    db.flush()
    user = User(
        id=uuid4(),
        email="snapshot-owner@example.invalid",
        password_hash="not-a-real-password-hash",
        role_id=role.id,
    )
    provider = Provider(
        id=uuid4(),
        provider_type=ProviderType.DOCTOR,
        name="Snapshot core provider",
        visit_stability=VisitStability.STABLE_VISIT,
    )
    db.add_all([user, provider])
    db.flush()
    update_id = uuid4()
    snapshot = ProviderProfileUpdate(
        id=update_id,
        provider_id=provider.id,
        submitted_at=datetime.now(timezone.utc),
        base_profile={"email": "original@example.invalid"},
        proposed_profile={"email": "original@example.invalid"},
    )
    db.add(snapshot)
    db.commit()

    with pytest.raises(ContactPersistenceError):
        db.execute(
            update(ProviderProfileUpdate.__table__)
            .where(ProviderProfileUpdate.__table__.c.id == update_id)
            .values(proposed_profile={"email": "bypass@example.invalid"})
        )
    db.rollback()

    cleartext = "prepared@example.invalid"
    protected = protect_snapshot_values(
        ProviderProfileUpdate,
        str(update_id),
        "proposed_profile",
        {"email": cleartext},
    )
    db.execute(
        update(ProviderProfileUpdate.__table__)
        .where(ProviderProfileUpdate.__table__.c.id == update_id)
        .values(proposed_profile=protected)
    )
    db.commit()
    db.expire_all()
    assert db.get(ProviderProfileUpdate, update_id).proposed_profile == {
        "email": cleartext
    }


def test_orm_rejects_double_encryption_and_raw_ciphertext_field_swaps(db):
    role = Role(name="contact-tamper-test", description="Test only")
    db.add(role)
    db.flush()
    first_id, second_id = uuid4(), uuid4()
    first = User(
        id=first_id,
        email="first@example.invalid",
        password_hash="not-a-real-password-hash",
        role_id=role.id,
    )
    second = User(
        id=second_id,
        email="second@example.invalid",
        mobile_number="+971501234567",
        password_hash="not-a-real-password-hash",
        role_id=role.id,
    )
    db.add_all([first, second])
    db.commit()

    first_raw = _raw_value(db, "users", "email", "id", first_id)
    second_raw = _raw_value(db, "users", "email", "id", second_id)
    db.execute(
        text("UPDATE users SET email = :replacement WHERE id = :id"),
        {"replacement": second_raw, "id": first_id},
    )
    db.commit()
    db.expire_all()
    with pytest.raises(ContactCiphertextInvalid):
        db.get(User, first_id).email
    db.rollback()

    db.expire_all()
    db.execute(
        text("UPDATE users SET mobile_number = :replacement WHERE id = :id"),
        {"replacement": first_raw, "id": first_id},
    )
    db.commit()
    db.expire_all()
    with pytest.raises(ContactCiphertextInvalid):
        db.get(User, first_id)
    db.rollback()

    ciphertext = encrypt_contact(
        "already@example.invalid", table="users", record_id=str(uuid4()), field="email"
    )
    db.add(
        User(
            id=uuid4(),
            email=ciphertext,
            password_hash="not-a-real-password-hash",
            role_id=role.id,
        )
    )
    with pytest.raises(ContactCiphertextInvalid):
        db.flush()
    db.rollback()


def test_concurrent_normalized_account_identity_has_one_winner(seeded_admin):
    admin, _ = seeded_admin
    role_id = admin.role_id
    barrier = Barrier(2)
    email = f"concurrent-{uuid4().hex}@example.invalid"

    def create_account():
        session = TestingSessionLocal()
        try:
            barrier.wait(timeout=10)
            session.add(
                User(
                    id=uuid4(),
                    email=email.upper(),
                    password_hash="not-a-real-password-hash",
                    role_id=role_id,
                )
            )
            session.commit()
            return "created"
        except IntegrityError:
            session.rollback()
            return "duplicate"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: create_account(), range(2)))
    assert sorted(outcomes) == ["created", "duplicate"]