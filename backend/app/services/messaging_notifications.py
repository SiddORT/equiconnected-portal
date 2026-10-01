"""One-shot, minimal-content email delivery for private provider conversations."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.models.provider import Provider
from app.models.user import User
from app.models.messaging import (
    MessagingNotificationOutbox,
    ProviderConversation,
    ProviderMessage,
)
from app.repositories.email_delivery_repository import EmailDeliveryRepository
from app.services.email_service import EmailDeliveryError, EmailService
from app.services.messaging_service import (
    MessagingService,
    ProviderMessagingUnavailableError,
    is_member_account,
)


_PURPOSES = {
    "member_acknowledgement": EmailPurpose.MESSAGING_MEMBER_ACKNOWLEDGEMENT,
    "provider_new_message": EmailPurpose.MESSAGING_PROVIDER_NEW_MESSAGE,
    "member_reply": EmailPurpose.MESSAGING_MEMBER_REPLY,
}


def _preflight(
    db: Session, item: MessagingNotificationOutbox
) -> tuple[User, Provider, str] | None:
    """Recheck account, listing, and explicit ownership before contacting anyone."""
    conversation = db.get(ProviderConversation, item.conversation_id)
    message = db.get(ProviderMessage, item.message_id)
    if conversation is None or message is None:
        return None
    member = db.get(User, conversation.member_user_id)
    if member is None or not member.is_active or not is_member_account(member):
        return None
    try:
        provider, provider_user = MessagingService(db).resolve_provider_account(
            conversation.provider_id
        )
    except ProviderMessagingUnavailableError:
        return None
    # Reuse API ownership resolution: ambiguity on either side of the link
    # invalidates this saved conversation and never redirects its notice.
    if (
        provider_user.id != conversation.provider_user_id
        or provider_user.provider_portal_setup_pending
    ):
        return None

    if (
        item.event_type == "member_acknowledgement"
        and item.recipient_user_id == member.id
        and message.sender_user_id == member.id
        and message.sender_side == "member"
    ):
        return member, provider, "member"
    if (
        item.event_type == "provider_new_message"
        and item.recipient_user_id == provider_user.id
        and message.sender_user_id == member.id
        and message.sender_side == "member"
    ):
        return provider_user, provider, "provider"
    if (
        item.event_type == "member_reply"
        and item.recipient_user_id == member.id
        and message.sender_user_id == provider_user.id
        and message.sender_side == "provider"
    ):
        return member, provider, "member"
    return None


def _set_status(
    db: Session,
    item_id: UUID,
    *,
    status: str,
    last_error: str | None = None,
) -> None:
    db.execute(
        update(MessagingNotificationOutbox)
        .where(MessagingNotificationOutbox.id == item_id)
        .values(status=status, locked_at=None, last_error=last_error)
    )
    db.commit()


def _dispatch_one(db: Session, item_id: UUID) -> None:
    now = datetime.now(timezone.utc)
    claimed = db.execute(
        update(MessagingNotificationOutbox)
        .where(
            MessagingNotificationOutbox.id == item_id,
            MessagingNotificationOutbox.status == "pending",
            MessagingNotificationOutbox.available_at <= now,
        )
        .values(
            status="processing",
            locked_at=now,
            attempt_count=MessagingNotificationOutbox.attempt_count + 1,
            last_error=None,
        )
    )
    db.commit()
    if claimed.rowcount != 1:
        return

    item = db.get(MessagingNotificationOutbox, item_id)
    if item is None:
        return
    try:
        target = _preflight(db, item)
    except Exception:
        # SMTP has not been touched yet; preserve the intent for later recovery.
        db.rollback()
        _set_status(
            db,
            item_id,
            status="pending",
            last_error="notification_preflight_unavailable",
        )
        return
    if target is None:
        _set_status(db, item_id, status="failed", last_error="participant_unavailable")
        return

    recipient, provider, side = target
    purpose = _PURPOSES.get(item.event_type)
    if purpose is None:
        _set_status(db, item_id, status="failed", last_error="unsupported_notification")
        return

    logs = EmailDeliveryRepository(db)
    try:
        attempt_id = logs.record_durable_attempt(
            recipient_email=recipient.email, purpose=purpose
        )
    except Exception:
        # SMTP must never run without its independently durable pending record.
        db.rollback()
        _set_status(
            db,
            item_id,
            status="pending",
            last_error="delivery_log_unavailable",
        )
        return

    if item.event_type == "member_acknowledgement":
        send = lambda: EmailService().send_member_message_acknowledgement(
            recipient.email,
            provider_name=provider.name,
            thread_url=_thread_url(item.conversation_id, side),
        )
    elif item.event_type == "provider_new_message":
        send = lambda: EmailService().send_provider_message_notification(
            recipient.email,
            thread_url=_thread_url(item.conversation_id, side),
        )
    else:
        send = lambda: EmailService().send_member_reply_notification(
            recipient.email,
            provider_name=provider.name,
            thread_url=_thread_url(item.conversation_id, side),
        )

    try:
        send()
    except EmailDeliveryError as exc:
        try:
            logs.complete_durable_attempt(
                attempt_id,
                status=EmailDeliveryStatus.FAILED,
                failure_message=exc,
            )
        except Exception:
            db.rollback()
        _set_status(db, item_id, status="failed", last_error="email_delivery_failed")
        return
    except Exception:
        # The handoff outcome is uncertain. Leave `processing` so it cannot be
        # automatically retried and duplicate a message that SMTP accepted.
        db.rollback()
        return

    try:
        logs.complete_durable_attempt(
            attempt_id, status=EmailDeliveryStatus.SUCCESS
        )
    except Exception:
        # SMTP accepted the message, so do not retry even if outcome accounting
        # could not be updated. Keep the non-retryable processing state.
        db.rollback()
        return
    db.execute(
        update(MessagingNotificationOutbox)
        .where(
            MessagingNotificationOutbox.id == item_id,
            MessagingNotificationOutbox.status == "processing",
        )
        .values(status="sent", sent_at=datetime.now(timezone.utc), locked_at=None)
    )
    db.commit()


def _complete_failed(logs: EmailDeliveryRepository, attempt_id: UUID) -> None:
    try:
        logs.complete_durable_attempt(
            attempt_id,
            status=EmailDeliveryStatus.FAILED,
            failure_message="Unable to deliver email.",
        )
    except Exception:
        pass


def _thread_url(conversation_id: UUID, side: str) -> str:
    from app.core.config import get_settings

    portal = "provider" if side == "provider" else "member"
    return get_settings().public_link(f"{portal}/messages/{conversation_id}")


def dispatch_pending(
    outbox_ids: list[UUID] | None = None, *, batch_size: int = 20
) -> None:
    """Deliver a bounded set of pending messages, or recover a bounded batch.

    A claimed row is deliberately never reclaimed after a process crash: SMTP
    may have accepted a handoff whose result was lost. Only safe pre-SMTP
    failures return an item to pending.
    """
    db = SessionLocal()
    try:
        statement = (
            select(MessagingNotificationOutbox.id)
            .where(
                MessagingNotificationOutbox.status == "pending",
                MessagingNotificationOutbox.available_at <= datetime.now(timezone.utc),
            )
            .order_by(
                MessagingNotificationOutbox.available_at,
                MessagingNotificationOutbox.created_at,
                MessagingNotificationOutbox.id,
            )
            .limit(max(1, min(batch_size, 100)))
        )
        if outbox_ids is not None:
            if not outbox_ids:
                return
            statement = statement.where(MessagingNotificationOutbox.id.in_(outbox_ids))
        ids = list(db.scalars(statement).all())
        for item_id in ids:
            try:
                _dispatch_one(db, item_id)
            except Exception:
                # Keep errors out of logs; no message, contact, recipient, or raw
                # SMTP details are useful in an operational exception string.
                db.rollback()
    finally:
        db.close()