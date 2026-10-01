"""Durable, participant-safe message notification delivery."""
import base64
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event, Lock
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token
from app.models.enums import (
    EmailDeliveryStatus,
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderStatus,
    ProviderType,
    PublicationStatus,
    VisitStability,
)
from app.models.messaging import (
    MessagingNotificationOutbox,
    ProviderConversation,
    ProviderMessage,
)
from app.models.invitation import ProviderInvitation
from app.models.provider import DirectProviderPortalAccess, Provider
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.user import User
from app.core.config import get_settings
from app.repositories.email_delivery_repository import EmailDeliveryRepository
from app.repositories.user_repository import UserRepository
from app.services import messaging_notifications
from app.services.email_service import EmailDeliveryError, EmailService
from app.services.messaging_service import MessagingService


def _configure_synthetic_key(monkeypatch):
    key = base64.b64encode(b"test-only-synthetic-messaging-key!"[:32].ljust(32, b"!")).decode()
    monkeypatch.setattr(
        "app.services.messaging_encryption.get_settings",
        lambda: SimpleNamespace(
            MESSAGING_ENCRYPTION_KEYRING=json.dumps({"test-v1": key}),
            MESSAGING_ENCRYPTION_ACTIVE_KEY_ID="test-v1",
        ),
    )


def _api_member_provider(db):
    users = UserRepository(db)
    member_role = users.get_role_by_name("horse_owner") or users.create_role(
        "horse_owner", "Horse owner"
    )
    provider_role = users.get_role_by_name("provider") or users.create_role(
        "provider", "Provider portal"
    )
    now = datetime.now(timezone.utc)
    member = users.create_user(
        email="api-member@example.test",
        password_hash="not-used",
        role=member_role,
        first_name="API",
        last_name="Member",
        mobile_number="+15551234567",
    )
    provider_user = users.create_user(
        email="api-provider@example.test",
        password_hash="not-used",
        role=provider_role,
    )
    member.email_verified_at = now
    provider_user.email_verified_at = now
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name="API Delivery Clinic",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=PublicationStatus.PUBLISHED,
    )
    db.add(provider)
    db.flush()
    db.add(
        DirectProviderPortalAccess(
            provider_id=provider.id,
            user_id=provider_user.id,
            recipient_email=provider_user.email,
            sent_at=now,
        )
    )
    db.commit()
    return member, provider


def _pending_provider_notice(db, *, provider_active=True):
    users = UserRepository(db)
    member_role = users.get_role_by_name("horse_owner") or users.create_role(
        "horse_owner", "Horse owner"
    )
    provider_role = users.get_role_by_name("provider") or users.create_role(
        "provider", "Provider portal"
    )
    member = users.create_user(
        email="member-account@example.test",
        password_hash="not-used",
        role=member_role,
        first_name="Member",
        last_name="Name",
        mobile_number="+15551234567",
    )
    provider_user = users.create_user(
        email="provider-account@example.test",
        password_hash="not-used",
        role=provider_role,
        first_name="Provider",
        last_name="Account",
        is_active=provider_active,
    )
    now = datetime.now(timezone.utc)
    member.email_verified_at = now
    provider_user.email_verified_at = now
    provider = Provider(
        provider_type=ProviderType.CLINIC,
        name="Listed Care Clinic",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=PublicationStatus.PUBLISHED,
    )
    db.add(provider)
    db.flush()
    db.add(
        DirectProviderPortalAccess(
            provider_id=provider.id,
            user_id=provider_user.id,
            recipient_email=provider_user.email,
        )
    )
    conversation = ProviderConversation(
        member_user_id=member.id,
        provider_id=provider.id,
        provider_user_id=provider_user.id,
        contact_snapshot_ciphertext="encrypted-contact-snapshot",
        contact_consent_at=now,
    )
    db.add(conversation)
    db.flush()
    message = ProviderMessage(
        conversation_id=conversation.id,
        sender_user_id=member.id,
        sender_side="member",
        sequence=1,
        request_id=uuid4(),
        body_ciphertext="encrypted-private-body",
    )
    db.add(message)
    db.flush()
    outbox = MessagingNotificationOutbox(
        conversation_id=conversation.id,
        message_id=message.id,
        recipient_user_id=provider_user.id,
        event_type="provider_new_message",
        status="pending",
        attempt_count=0,
        available_at=now,
    )
    db.add(outbox)
    db.commit()
    return member, provider_user, provider, conversation, message, outbox


def _test_session_factory(db):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)


def test_provider_notice_uses_explicit_account_and_never_loads_private_content(
    db, monkeypatch
):
    member, provider_user, _provider, conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    sent = []
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )
    monkeypatch.setattr(
        EmailService,
        "send_provider_message_notification",
        lambda _self, recipient, **kwargs: sent.append((recipient, kwargs)),
    )

    messaging_notifications.dispatch_pending([outbox.id])
    messaging_notifications.dispatch_pending([outbox.id])

    assert len(sent) == 1
    assert sent[0][0] == provider_user.email
    assert sent[0][1]["thread_url"] == get_settings().public_link(
        f"provider/messages/{conversation.id}"
    )
    assert member.email not in repr(sent)
    assert "encrypted-private-body" not in repr(sent)
    assert "encrypted-contact-snapshot" not in repr(sent)
    db.refresh(outbox)
    assert outbox.status == "sent"
    assert outbox.attempt_count == 1
    entries, total = EmailDeliveryRepository(db).list()
    assert total == 1
    assert entries[0].recipient_email == provider_user.email
    assert entries[0].status == EmailDeliveryStatus.SUCCESS.value
    assert entries[0].purpose == "messaging_provider_new_message"


def test_delivery_accounting_start_failure_leaves_intent_pending_without_smtp(
    db, monkeypatch
):
    _member, _provider_user, _provider, _conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )
    monkeypatch.setattr(
        EmailDeliveryRepository,
        "record_durable_attempt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("private")),
    )
    sent = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_message_notification",
        lambda *_args, **_kwargs: sent.append(True),
    )

    messaging_notifications.dispatch_pending([outbox.id])

    assert sent == []
    db.refresh(outbox)
    assert outbox.status == "pending"
    assert outbox.last_error == "delivery_log_unavailable"
    assert EmailDeliveryRepository(db).list()[1] == 0


def test_smtp_failure_is_outcome_logged_and_not_automatically_retried(db, monkeypatch):
    _member, _provider_user, _provider, _conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )

    def fail_delivery(*_args, **_kwargs):
        raise EmailDeliveryError("SMTP handoff failed.")

    monkeypatch.setattr(EmailService, "send_provider_message_notification", fail_delivery)
    messaging_notifications.dispatch_pending([outbox.id])
    messaging_notifications.dispatch_pending([outbox.id])

    db.refresh(outbox)
    assert outbox.status == "failed"
    assert outbox.attempt_count == 1
    entries, total = EmailDeliveryRepository(db).list()
    assert total == 1
    assert entries[0].status == EmailDeliveryStatus.FAILED.value
    assert entries[0].failure_message == "SMTP handoff failed."


def test_unexpected_smtp_exception_is_nonretryable_and_never_exposes_error(
    db, monkeypatch, caplog
):
    _member, _provider_user, _provider, _conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )
    sent = []
    private_error = "unexpected SMTP response recipient-secret@example.test"

    def fail_delivery(*_args, **_kwargs):
        sent.append(True)
        raise RuntimeError(private_error)

    monkeypatch.setattr(EmailService, "send_provider_message_notification", fail_delivery)
    with caplog.at_level(logging.ERROR):
        messaging_notifications.dispatch_pending([outbox.id])
        messaging_notifications.dispatch_pending([outbox.id])

    assert sent == [True]
    db.refresh(outbox)
    assert outbox.status == "processing"
    assert outbox.attempt_count == 1
    assert private_error not in caplog.text
    assert private_error not in (outbox.last_error or "")
    entries, total = EmailDeliveryRepository(db).list()
    assert total == 1
    assert entries[0].status == EmailDeliveryStatus.PENDING.value
    assert entries[0].failure_message is None


def test_successful_smtp_with_failed_outcome_accounting_is_not_retried(
    db, monkeypatch, caplog
):
    _member, _provider_user, _provider, _conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )
    sent = []
    private_error = "private accounting detail recipient-secret@example.test"
    monkeypatch.setattr(
        EmailService,
        "send_provider_message_notification",
        lambda *_args, **_kwargs: sent.append(True),
    )

    def fail_success_accounting(
        _self, _attempt_id, *, status, failure_message=None
    ):
        assert status == EmailDeliveryStatus.SUCCESS
        raise RuntimeError(private_error)

    monkeypatch.setattr(
        EmailDeliveryRepository,
        "complete_durable_attempt",
        fail_success_accounting,
    )
    with caplog.at_level(logging.ERROR):
        messaging_notifications.dispatch_pending([outbox.id])
        messaging_notifications.dispatch_pending([outbox.id])

    assert sent == [True]
    db.refresh(outbox)
    assert outbox.status == "processing"
    assert outbox.attempt_count == 1
    assert private_error not in caplog.text
    entries, total = EmailDeliveryRepository(db).list()
    assert total == 1
    assert entries[0].status == EmailDeliveryStatus.PENDING.value
    assert entries[0].failure_message is None


def test_sent_status_commit_failure_keeps_smtp_nonretryable(db, monkeypatch):
    _member, _provider_user, _provider, _conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    class FailSentCommitSession(Session):
        commit_count = 0

        def commit(self):
            self.commit_count += 1
            if self.commit_count == 2:
                raise RuntimeError("private final status persistence error")
            return super().commit()

    monkeypatch.setattr(
        messaging_notifications,
        "SessionLocal",
        sessionmaker(
            bind=db.get_bind(),
            class_=FailSentCommitSession,
            autocommit=False,
            autoflush=False,
        ),
    )
    sent = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_message_notification",
        lambda *_args, **_kwargs: sent.append(True),
    )

    messaging_notifications.dispatch_pending([outbox.id])
    messaging_notifications.dispatch_pending([outbox.id])

    assert sent == [True]
    db.refresh(outbox)
    assert outbox.status == "processing"
    assert outbox.attempt_count == 1
    entries, total = EmailDeliveryRepository(db).list()
    assert total == 1
    assert entries[0].status == EmailDeliveryStatus.SUCCESS.value


def test_concurrent_dispatchers_claim_an_outbox_item_once(db, monkeypatch):
    _member, _provider_user, _provider, _conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )
    send_entered = Event()
    allow_send_to_finish = Event()
    sent = []
    sent_lock = Lock()

    def blocking_send(*_args, **_kwargs):
        with sent_lock:
            sent.append(True)
        send_entered.set()
        assert allow_send_to_finish.wait(timeout=10)

    monkeypatch.setattr(
        EmailService, "send_provider_message_notification", blocking_send
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(messaging_notifications.dispatch_pending, [outbox.id])
        assert send_entered.wait(timeout=10)
        second = pool.submit(messaging_notifications.dispatch_pending, [outbox.id])
        second.result(timeout=10)
        allow_send_to_finish.set()
        first.result(timeout=10)

    assert sent == [True]
    db.refresh(outbox)
    assert outbox.status == "sent"
    assert outbox.attempt_count == 1
    assert EmailDeliveryRepository(db).list()[1] == 1


@pytest.mark.parametrize("failure_stage", ["accounting", "dispatcher"])
def test_api_saves_message_when_notification_accounting_or_dispatcher_throws(
    client, db, monkeypatch, caplog, failure_stage
):
    from app.models.messaging import ProviderMessage

    _configure_synthetic_key(monkeypatch)
    member, provider = _api_member_provider(db)
    private_error = "private SMTP recipient-secret@example.test"
    if failure_stage == "accounting":
        monkeypatch.setattr(
            EmailDeliveryRepository,
            "record_durable_attempt",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError(private_error)
            ),
        )
    else:
        monkeypatch.setattr(
            messaging_notifications,
            "dispatch_pending",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError(private_error)
            ),
        )

    with caplog.at_level(logging.ERROR):
        response = client.post(
            "/api/v1/messages/start",
            headers={
                "Authorization": f"Bearer {create_access_token(subject=member.id)}"
            },
            json={
                "provider_id": str(provider.id),
                "request_id": str(uuid4()),
                "message": "Please send delivery information.",
                "consent": True,
            },
        )

    assert response.status_code == 201, response.text
    assert response.json()["messages"][0]["body"] == (
        "Please send delivery information."
    )
    assert db.query(ProviderMessage).count() == 1
    assert private_error not in response.text
    assert private_error not in caplog.text
    intents = db.query(MessagingNotificationOutbox).all()
    assert len(intents) == 2
    assert all(intent.status == "pending" for intent in intents)


def test_thread_delivery_failure_flag_is_limited_to_the_target_account(db):
    member, provider_user, _provider, conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    outbox.status = "failed"
    outbox.last_error = "email_delivery_failed"
    db.commit()

    service = MessagingService(db)

    assert service._notifications_failed(conversation, provider_user) is True
    assert service._notifications_failed(conversation, member) is False


def test_provider_disabled_before_dispatch_prevents_notification(db, monkeypatch):
    _member, _provider_user, _provider, _conversation, _message, outbox = (
        _pending_provider_notice(db, provider_active=False)
    )
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )
    sent = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_message_notification",
        lambda *_args, **_kwargs: sent.append(True),
    )

    messaging_notifications.dispatch_pending([outbox.id])

    assert sent == []
    db.refresh(outbox)
    assert outbox.status == "failed"
    assert outbox.last_error == "participant_unavailable"
    assert EmailDeliveryRepository(db).list()[1] == 0


def test_notice_is_suppressed_when_listing_has_multiple_linked_accounts(db, monkeypatch):
    _member, provider_user, provider, _conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    users = UserRepository(db)
    provider_role = users.get_role_by_name("provider")
    other_user = users.create_user(
        email="other-provider-account@example.test",
        password_hash="not-used",
        role=provider_role,
    )
    other_user.email_verified_at = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    db.add(
        ProviderInvitation(
            provider_id=provider.id,
            provider_type=provider.provider_type,
            recipient_email=other_user.email,
            token_hash="second-linked-owner-token-hash",
            status=InvitationStatus.COMPLETED,
            expires_at=now,
            sent_at=now,
            completed_at=now,
            portal_user_id=other_user.id,
            created_by=provider_user.id,
        )
    )
    db.commit()
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )
    sent = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_message_notification",
        lambda *_args, **_kwargs: sent.append(True),
    )

    messaging_notifications.dispatch_pending([outbox.id])

    assert sent == []
    db.refresh(outbox)
    assert outbox.status == "failed"
    assert outbox.last_error == "participant_unavailable"
    assert EmailDeliveryRepository(db).list()[1] == 0
    assert provider_user.id != other_user.id


def test_notice_is_suppressed_when_account_owns_multiple_listings(db, monkeypatch):
    _member, provider_user, provider, _conversation, _message, outbox = (
        _pending_provider_notice(db)
    )
    other_provider = Provider(
        provider_type=ProviderType.CLINIC,
        name="Another Listed Clinic",
        visit_stability=VisitStability.STABLE_VISIT,
        status=ProviderStatus.ACTIVE,
        publication_status=PublicationStatus.PUBLISHED,
    )
    db.add(other_provider)
    db.flush()
    db.add(
        ProviderRegistrationApplication(
            user_id=provider_user.id,
            provider_id=other_provider.id,
            provider_type=other_provider.provider_type,
            provider_name=other_provider.name,
            visit_stability=other_provider.visit_stability,
            postal_code="12345",
            review_status=ProviderApplicationStatus.APPROVED,
        )
    )
    db.commit()
    monkeypatch.setattr(
        messaging_notifications, "SessionLocal", _test_session_factory(db)
    )
    sent = []
    monkeypatch.setattr(
        EmailService,
        "send_provider_message_notification",
        lambda *_args, **_kwargs: sent.append(True),
    )

    messaging_notifications.dispatch_pending([outbox.id])

    assert sent == []
    db.refresh(outbox)
    assert outbox.status == "failed"
    assert outbox.last_error == "participant_unavailable"
    assert EmailDeliveryRepository(db).list()[1] == 0