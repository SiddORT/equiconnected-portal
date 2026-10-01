"""Private, participant-scoped member/provider messaging endpoints."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User
from app.services.messaging_encryption import (
    MessagingCiphertextInvalid,
    MessagingEncryptionUnavailable,
    ensure_encryption_available,
)
from app.services.messaging_service import (
    MessagingConsentRequiredError,
    MessagingIdempotencyConflictError,
    MessagingNotFoundError,
    MessagingProfileIncompleteError,
    MessagingReadSequenceError,
    MessagingSendLimitError,
    MessagingService,
    ProviderMessagingUnavailableError,
    is_admin_account,
    is_member_account,
    is_provider_account,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/messages", tags=["Private provider messaging"])
_DB = Annotated[Session, Depends(get_db)]


class AvailabilityResponse(BaseModel):
    available: bool
    reason: str | None = None
    provider_name: str | None = None


class MessageStartRequest(BaseModel):
    provider_id: UUID
    request_id: UUID
    message: str = Field(min_length=1, max_length=5_000)
    consent: bool

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Messages cannot be empty.")
        return clean


class MessageReplyRequest(BaseModel):
    request_id: UUID
    message: str = Field(min_length=1, max_length=5_000)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Messages cannot be empty.")
        return clean


class ReadCursorRequest(BaseModel):
    message_sequences: list[int] | None = Field(default=None, max_length=100)
    # Compatibility for clients that can confirm exactly one rendered message.
    through_sequence: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_one_read_selection(self):
        if (self.message_sequences is None) == (self.through_sequence is None):
            raise ValueError("Supply message_sequences or through_sequence.")
        if self.message_sequences is not None and any(sequence < 1 for sequence in self.message_sequences):
            raise ValueError("Message sequences must be positive.")
        return self

    @property
    def selected_sequences(self) -> list[int]:
        if self.message_sequences is not None:
            return sorted(set(self.message_sequences))
        return [self.through_sequence] if self.through_sequence is not None else []


class MessageItem(BaseModel):
    id: UUID
    sequence: int
    sender_side: str
    created_at: datetime
    body: str


class ConversationSummary(BaseModel):
    id: UUID
    provider_id: UUID
    provider_name: str
    last_message_at: datetime | None
    unread_count: int
    last_sequence: int
    notifications_failed: bool


class InboxResponse(BaseModel):
    items: list[ConversationSummary]
    page: int
    page_size: int
    total: int


class UnreadResponse(BaseModel):
    count: int


class ContactSnapshot(BaseModel):
    name: str
    email: str
    phone: str


class ThreadResponse(BaseModel):
    conversation: ConversationSummary
    messages: list[MessageItem]
    contact: ContactSnapshot | None
    next_before_sequence: int | None
    unread_count: int


class ReadResponse(BaseModel):
    read_sequence: int
    read_sequences: list[int]


def require_messaging_participant(user: CurrentUser) -> User:
    if (
        is_admin_account(user)
        or user.email_verified_at is None
        or not (
            is_member_account(user)
            or is_provider_account(user)
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "messaging_forbidden",
                "message": "Private messaging is available to verified members and linked providers only.",
            },
        )
    return user


MessagingParticipant = Annotated[User, Depends(require_messaging_participant)]


def _service(db: Session) -> MessagingService:
    return MessagingService(db)


def _dispatch_notifications(outbox_ids: list[UUID]) -> None:
    """Import worker lazily; delivery is best-effort after message commit."""
    if not outbox_ids:
        return
    try:
        from app.services.messaging_notifications import dispatch_pending

        dispatch_pending(outbox_ids)
    except Exception:
        # Never include SMTP exception text, message content, or recipient details.
        logger.error("messaging_notification_dispatch_failed", extra={"outbox_count": len(outbox_ids)})


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "conversation_not_found", "message": "Conversation not found."},
    )


def _encryption_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "messaging_encryption_unavailable",
            "message": "Private messaging is temporarily unavailable.",
        },
    )


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MessagingEncryptionUnavailable):
        return _encryption_unavailable()
    if isinstance(exc, MessagingCiphertextInvalid):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "message_content_unavailable",
                "message": "This private message could not be opened.",
            },
        )
    if isinstance(exc, ProviderMessagingUnavailableError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "provider_messaging_unavailable",
                "message": "Private messaging is unavailable for this provider.",
                "reason": exc.reason,
            },
        )
    if isinstance(exc, MessagingProfileIncompleteError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "profile_incomplete",
                "message": "Add your name and phone number to your profile before messaging a provider.",
            },
        )
    if isinstance(exc, MessagingConsentRequiredError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "contact_sharing_consent_required",
                "message": "Agree to share your name, account email, and phone number with this provider before sending.",
            },
        )
    if isinstance(exc, MessagingSendLimitError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "message_send_limit",
                "message": "You have reached the hourly message limit. Please try again later.",
            },
            headers={"Retry-After": "3600"},
        )
    if isinstance(exc, MessagingIdempotencyConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "message_request_conflict",
                "message": "This send request identifier was already used for a different message.",
            },
        )
    if isinstance(exc, MessagingReadSequenceError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_read_cursor",
                "message": "Choose a message from this conversation to mark as read.",
            },
        )
    if isinstance(exc, (MessagingNotFoundError,)):
        return _not_found()
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_message", "message": str(exc)},
        )
    raise exc


@router.get("/availability", response_model=AvailabilityResponse)
def messaging_availability(
    provider_id: UUID,
    user: MessagingParticipant,
    db: _DB,
) -> AvailabilityResponse:
    if not is_member_account(user):
        raise _not_found()
    available, reason, provider_name = _service(db).availability(provider_id)
    if available:
        try:
            ensure_encryption_available()
        except MessagingEncryptionUnavailable:
            return AvailabilityResponse(
                available=False,
                reason="messaging_encryption_unavailable",
                provider_name=provider_name,
            )
    return AvailabilityResponse(
        available=available,
        reason=reason,
        provider_name=provider_name,
    )


@router.post("/start", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
def start_conversation(
    body: MessageStartRequest,
    background_tasks: BackgroundTasks,
    user: MessagingParticipant,
    db: _DB,
) -> ThreadResponse:
    if not is_member_account(user):
        raise _not_found()
    svc = _service(db)
    try:
        conversation, _message, outbox_ids, _created = svc.start(
            user,
            provider_id=body.provider_id,
            request_id=body.request_id,
            raw_body=body.message,
            consent=body.consent,
        )
        response = svc.thread(
            user, conversation_id=conversation.id, before_sequence=None, limit=50
        )
    except Exception as exc:
        raise _map_error(exc) from None
    background_tasks.add_task(_dispatch_notifications, outbox_ids)
    return ThreadResponse.model_validate(response)


@router.get("/inbox", response_model=InboxResponse)
def list_conversations(
    user: MessagingParticipant,
    db: _DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
) -> InboxResponse:
    try:
        items, total = _service(db).inbox(user, page=page, page_size=page_size)
    except Exception as exc:
        raise _map_error(exc) from None
    return InboxResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/unread", response_model=UnreadResponse)
def unread_count(user: MessagingParticipant, db: _DB) -> UnreadResponse:
    try:
        count = _service(db).unread_count(user)
    except Exception as exc:
        raise _map_error(exc) from None
    return UnreadResponse(count=count)


@router.get("/{conversation_id}", response_model=ThreadResponse)
def get_thread(
    conversation_id: UUID,
    user: MessagingParticipant,
    db: _DB,
    before_sequence: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> ThreadResponse:
    try:
        thread = _service(db).thread(
            user,
            conversation_id=conversation_id,
            before_sequence=before_sequence,
            limit=limit,
        )
    except Exception as exc:
        raise _map_error(exc) from None
    return ThreadResponse.model_validate(thread)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageItem,
    status_code=status.HTTP_201_CREATED,
)
def send_reply(
    conversation_id: UUID,
    body: MessageReplyRequest,
    background_tasks: BackgroundTasks,
    user: MessagingParticipant,
    db: _DB,
) -> MessageItem:
    try:
        _conversation, message, outbox_ids, side = _service(db).reply(
            user,
            conversation_id=conversation_id,
            request_id=body.request_id,
            raw_body=body.message,
        )
        plaintext = _service(db)._message_plaintext(_conversation, message)
    except Exception as exc:
        raise _map_error(exc) from None
    background_tasks.add_task(_dispatch_notifications, outbox_ids)
    return MessageItem(
        id=message.id,
        sequence=message.sequence,
        sender_side=side,
        created_at=message.created_at,
        body=plaintext,
    )


@router.post("/{conversation_id}/read", response_model=ReadResponse)
def advance_read_cursor(
    conversation_id: UUID,
    body: ReadCursorRequest,
    user: MessagingParticipant,
    db: _DB,
) -> ReadResponse:
    try:
        read_sequences, sequence = _service(db).mark_read(
            user,
            conversation_id=conversation_id,
            message_sequences=body.selected_sequences,
        )
    except Exception as exc:
        raise _map_error(exc) from None
    return ReadResponse(read_sequence=sequence, read_sequences=read_sequences)