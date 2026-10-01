"""Participant authorization, persistence, limits, and encrypted message reads."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import (
    InvitationStatus,
    ProviderApplicationStatus,
    ProviderStatus,
    PublicationStatus,
)
from app.models.invitation import ProviderInvitation
from app.models.messaging import (
    MessagingNotificationOutbox,
    MessagingSendLimit,
    ProviderConversation,
    ProviderMessage,
)
from app.models.provider import DirectProviderPortalAccess, Provider
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.role import Role
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User, UserRole
from app.services.contact_encryption import normalize_contact
from app.services.messaging_encryption import MessagingCiphertextInvalid, decrypt_text, encrypt_text

MAX_MESSAGE_LENGTH = 5_000
SEND_LIMIT = 20
SEND_WINDOW = timedelta(hours=1)


class MessagingNotFoundError(Exception):
    """A resource is absent or deliberately hidden from this participant."""


class ProviderMessagingUnavailableError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class MessagingProfileIncompleteError(Exception):
    """Member must supply the required name and phone in their account profile."""


class MessagingConsentRequiredError(Exception):
    """A member did not explicitly consent to sharing the contact snapshot."""


class MessagingSendLimitError(Exception):
    """Account-level database send limit has been reached."""


class MessagingIdempotencyConflictError(Exception):
    """A request identifier was reused with different content or destination."""


class MessagingReadSequenceError(Exception):
    """Requested read cursor is not an existing message in the conversation."""


def _role_names(user: User) -> set[str]:
    return {user.role.name, *(assignment.role.name for assignment in user.role_assignments)}


def is_admin_account(user: User) -> bool:
    """Treat an administrator assignment as disqualifying any messaging role."""
    return "admin" in _role_names(user)


def is_member_account(user: User) -> bool:
    return (
        not is_admin_account(user)
        and user.email_verified_at is not None
        and bool(_role_names(user).intersection(PUBLIC_ACCOUNT_ROLE_NAMES))
    )


def is_provider_account(user: User) -> bool:
    return (
        not is_admin_account(user)
        and user.role.name == "provider"
        and user.email_verified_at is not None
        and user.is_active
        and not user.provider_portal_setup_pending
        and not user.provider_portal_approval_pending
    )


class MessagingService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _active_provider(self, provider_id: UUID) -> Provider | None:
        provider = self._db.get(Provider, provider_id)
        if (
            provider is None
            or provider.status != ProviderStatus.ACTIVE
            or provider.publication_status != PublicationStatus.PUBLISHED
        ):
            return None
        return provider

    def resolve_provider_account(self, provider_id: UUID) -> tuple[Provider, User]:
        """Resolve one explicitly linked active provider account, never by email."""
        provider = self._active_provider(provider_id)
        if provider is None:
            raise ProviderMessagingUnavailableError("provider_unavailable")

        invitation_rows = self._db.scalars(
            select(ProviderInvitation).where(
                ProviderInvitation.provider_id == provider.id,
                ProviderInvitation.status == InvitationStatus.COMPLETED,
                ProviderInvitation.portal_user_id.is_not(None),
            )
        ).all()
        registration_ids = set(
            self._db.scalars(
                select(ProviderRegistrationApplication.user_id).where(
                    ProviderRegistrationApplication.provider_id == provider.id,
                    ProviderRegistrationApplication.review_status
                    == ProviderApplicationStatus.APPROVED,
                )
            ).all()
        )
        direct_ids = set(
            self._db.scalars(
                select(DirectProviderPortalAccess.user_id).where(
                    DirectProviderPortalAccess.provider_id == provider.id,
                )
            ).all()
        )
        candidates = {invitation.portal_user_id for invitation in invitation_rows}
        candidates.update(registration_ids)
        candidates.update(direct_ids)
        if len(candidates) > 1:
            raise ProviderMessagingUnavailableError("provider_account_ambiguous")
        if not candidates:
            raise ProviderMessagingUnavailableError("provider_account_unavailable")

        owner = self._db.scalar(
            select(User)
            .options(
                joinedload(User.role),
                selectinload(User.role_assignments).joinedload(UserRole.role),
            )
            .where(User.id == next(iter(candidates)))
        )
        if owner is None or not is_provider_account(owner):
            raise ProviderMessagingUnavailableError("provider_account_unavailable")
        invitation_matches = any(
            invitation.portal_user_id == owner.id
            and normalize_contact(invitation.recipient_email, field="email")
            == normalize_contact(owner.email, field="email")
            for invitation in invitation_rows
        )
        if not (
            invitation_matches
            or owner.id in registration_ids
            or owner.id in direct_ids
        ):
            raise ProviderMessagingUnavailableError("provider_account_unavailable")
        owned_provider_ids = {
            linked_id
            for linked_id in self._db.scalars(
                select(ProviderInvitation.provider_id).where(
                    ProviderInvitation.portal_user_id == owner.id,
                    ProviderInvitation.status == InvitationStatus.COMPLETED,
                    ProviderInvitation.provider_id.is_not(None),
                )
            ).all()
        }
        owned_provider_ids.update(
            linked_id
            for linked_id in self._db.scalars(
                select(ProviderRegistrationApplication.provider_id).where(
                    ProviderRegistrationApplication.user_id == owner.id,
                    ProviderRegistrationApplication.review_status
                    == ProviderApplicationStatus.APPROVED,
                    ProviderRegistrationApplication.provider_id.is_not(None),
                )
            ).all()
        )
        owned_provider_ids.update(
            self._db.scalars(
                select(DirectProviderPortalAccess.provider_id).where(
                    DirectProviderPortalAccess.user_id == owner.id
                )
            ).all()
        )
        if owned_provider_ids != {provider.id}:
            raise ProviderMessagingUnavailableError("provider_account_ambiguous")
        return provider, owner

    def availability(self, provider_id: UUID) -> tuple[bool, str | None, str | None]:
        try:
            provider, _owner = self.resolve_provider_account(provider_id)
        except ProviderMessagingUnavailableError as exc:
            return False, exc.reason, None
        return True, None, provider.name

    def _conversation_for_participant(
        self, conversation_id: UUID, user: User
    ) -> tuple[ProviderConversation, str, Provider, User]:
        conversation = self._db.get(ProviderConversation, conversation_id)
        if conversation is None:
            raise MessagingNotFoundError()
        if conversation.member_user_id == user.id and is_member_account(user):
            side = "member"
        elif conversation.provider_user_id == user.id and is_provider_account(user):
            side = "provider"
        else:
            raise MessagingNotFoundError()
        try:
            provider, owner = self.resolve_provider_account(conversation.provider_id)
        except ProviderMessagingUnavailableError:
            raise MessagingNotFoundError() from None
        # Explicit owner changes invalidate access; historical conversations never transfer.
        if owner.id != conversation.provider_user_id:
            raise MessagingNotFoundError()
        if side == "provider" and owner.id != user.id:
            raise MessagingNotFoundError()
        if side == "member" and user.id == owner.id:
            raise MessagingNotFoundError()
        return conversation, side, provider, owner

    def _lock_conversation(self, conversation_id: UUID) -> ProviderConversation:
        conversation = self._db.scalar(
            select(ProviderConversation)
            .where(ProviderConversation.id == conversation_id)
            .with_for_update(of=ProviderConversation)
            .execution_options(populate_existing=True)
        )
        if conversation is None:
            raise MessagingNotFoundError()
        return conversation

    def _lock_send_budget(self, user_id: UUID) -> MessagingSendLimit:
        now = datetime.now(timezone.utc)
        self._db.execute(
            insert(MessagingSendLimit)
            .values(user_id=user_id, window_started_at=now, send_count=0)
            .on_conflict_do_nothing(index_elements=[MessagingSendLimit.user_id])
        )
        budget = self._db.scalar(
            select(MessagingSendLimit)
            .where(MessagingSendLimit.user_id == user_id)
            .with_for_update(of=MessagingSendLimit)
            .execution_options(populate_existing=True)
        )
        assert budget is not None
        if now - budget.window_started_at >= SEND_WINDOW:
            budget.window_started_at = now
            budget.send_count = 0
        return budget

    @staticmethod
    def _charge_send_budget(budget: MessagingSendLimit) -> None:
        if budget.send_count >= SEND_LIMIT:
            raise MessagingSendLimitError()
        budget.send_count += 1

    def _existing_request(self, sender_id: UUID, request_id: UUID) -> ProviderMessage | None:
        return self._db.scalar(
            select(ProviderMessage).where(
                ProviderMessage.sender_user_id == sender_id,
                ProviderMessage.request_id == request_id,
            )
        )

    @staticmethod
    def _validate_message(body: str) -> str:
        clean = body.strip()
        if not clean or len(clean) > MAX_MESSAGE_LENGTH or "\x00" in clean:
            raise ValueError("Messages must be between 1 and 5,000 characters.")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in clean):
            raise ValueError("Messages must not contain control characters.")
        return clean

    def _message_plaintext(self, conversation: ProviderConversation, message: ProviderMessage) -> str:
        return decrypt_text(
            message.body_ciphertext,
            conversation_id=conversation.id,
            record_id=message.id,
            field="message_body",
        )

    def _check_idempotent_retry(
        self,
        existing: ProviderMessage,
        *,
        conversation: ProviderConversation,
        side: str,
        body: str,
    ) -> ProviderMessage:
        if (
            existing.conversation_id != conversation.id
            or existing.sender_side != side
            or self._message_plaintext(conversation, existing) != body
        ):
            raise MessagingIdempotencyConflictError()
        return existing

    def _outbox_ids(self, message_id: UUID) -> list[UUID]:
        return list(
            self._db.scalars(
                select(MessagingNotificationOutbox.id)
                .where(
                    MessagingNotificationOutbox.message_id == message_id,
                    MessagingNotificationOutbox.status.in_(("pending", "failed")),
                )
                .order_by(MessagingNotificationOutbox.created_at, MessagingNotificationOutbox.id)
            ).all()
        )

    def _queue_notifications(
        self, conversation: ProviderConversation, message: ProviderMessage, side: str
    ) -> list[UUID]:
        if side == "member":
            events = (
                [
                    ("member_acknowledgement", conversation.member_user_id),
                    ("provider_new_message", conversation.provider_user_id),
                ]
                if message.sequence == 1
                else [("provider_new_message", conversation.provider_user_id)]
            )
        else:
            events = [("member_reply", conversation.member_user_id)]

        for event_type, recipient_id in events:
            self._db.add(
                MessagingNotificationOutbox(
                    conversation_id=conversation.id,
                    message_id=message.id,
                    recipient_user_id=recipient_id,
                    event_type=event_type,
                    status="pending",
                    attempt_count=0,
                    available_at=datetime.now(timezone.utc),
                )
            )
        self._db.flush()
        return self._outbox_ids(message.id)

    def start(
        self, member: User, *, provider_id: UUID, request_id: UUID, raw_body: str, consent: bool
    ) -> tuple[ProviderConversation, ProviderMessage, list[UUID], bool]:
        if not is_member_account(member):
            raise MessagingNotFoundError()
        if not consent:
            raise MessagingConsentRequiredError()
        body = self._validate_message(raw_body)
        # Serialize concurrent first-thread creation for this listing.
        locked_provider = self._db.scalar(
            select(Provider)
            .where(Provider.id == provider_id)
            .with_for_update(of=Provider)
        )
        if locked_provider is None:
            raise ProviderMessagingUnavailableError("provider_unavailable")
        provider, owner = self.resolve_provider_account(provider_id)
        if member.id == owner.id:
            raise ProviderMessagingUnavailableError("provider_account_unavailable")

        prior = self._existing_request(member.id, request_id)
        if prior is not None:
            conversation = self._db.get(ProviderConversation, prior.conversation_id)
            if (
                conversation is None
                or conversation.member_user_id != member.id
                or conversation.provider_id != provider.id
                or conversation.provider_user_id != owner.id
            ):
                raise MessagingIdempotencyConflictError()
            self._check_idempotent_retry(
                prior, conversation=conversation, side="member", body=body
            )
            return conversation, prior, self._outbox_ids(prior.id), False

        name = " ".join(part for part in (member.first_name, member.last_name) if part).strip()
        phone = (member.mobile_number or "").strip()
        email = member.email.strip()
        if not name or not phone or not email:
            raise MessagingProfileIncompleteError()

        conversation = self._db.scalar(
            select(ProviderConversation)
            .where(
                ProviderConversation.member_user_id == member.id,
                ProviderConversation.provider_id == provider.id,
                ProviderConversation.provider_user_id == owner.id,
            )
            .with_for_update(of=ProviderConversation)
        )
        is_new = conversation is None
        if conversation is None:
            conversation_id = uuid4()
            contact_json = json.dumps(
                {"name": name, "email": email, "phone": phone},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            conversation = ProviderConversation(
                id=conversation_id,
                member_user_id=member.id,
                provider_id=provider.id,
                provider_user_id=owner.id,
                contact_snapshot_ciphertext=encrypt_text(
                    contact_json,
                    conversation_id=conversation_id,
                    record_id=conversation_id,
                    field="contact_snapshot",
                ),
                contact_consent_at=datetime.now(timezone.utc),
            )
            self._db.add(conversation)
            self._db.flush()

        budget = self._lock_send_budget(member.id)
        conversation = self._lock_conversation(conversation.id)
        prior = self._existing_request(member.id, request_id)
        if prior is not None:
            self._check_idempotent_retry(
                prior, conversation=conversation, side="member", body=body
            )
            outbox_ids = self._outbox_ids(prior.id)
            self._db.commit()
            return conversation, prior, outbox_ids, False

        self._charge_send_budget(budget)
        message = self._append_message(conversation, member, "member", body, request_id)
        outbox_ids = self._queue_notifications(conversation, message, "member")
        self._db.commit()
        return conversation, message, outbox_ids, is_new

    def _append_message(
        self,
        conversation: ProviderConversation,
        sender: User,
        side: str,
        body: str,
        request_id: UUID,
    ) -> ProviderMessage:
        sequence = conversation.last_sequence + 1
        message_id = uuid4()
        message = ProviderMessage(
            id=message_id,
            conversation_id=conversation.id,
            sender_user_id=sender.id,
            sender_side=side,
            sequence=sequence,
            request_id=request_id,
            member_read_at=(
                datetime.now(timezone.utc) if side == "member" else None
            ),
            provider_read_at=(
                datetime.now(timezone.utc) if side == "provider" else None
            ),
            body_ciphertext=encrypt_text(
                body,
                conversation_id=conversation.id,
                record_id=message_id,
                field="message_body",
            ),
        )
        conversation.last_sequence = sequence
        conversation.last_message_at = datetime.now(timezone.utc)
        self._db.add(message)
        self._db.flush()
        self._advance_read_cursor(conversation, side)
        return message

    def reply(
        self, user: User, *, conversation_id: UUID, request_id: UUID, raw_body: str
    ) -> tuple[ProviderConversation, ProviderMessage, list[UUID], str]:
        body = self._validate_message(raw_body)
        conversation, side, _provider, _owner = self._conversation_for_participant(
            conversation_id, user
        )
        conversation = self._lock_conversation(conversation.id)
        # Re-check the live listing and exact owner after acquiring the write lock.
        _current, current_side, _provider, owner = self._conversation_for_participant(
            conversation.id, user
        )
        if current_side != side or owner.id != conversation.provider_user_id:
            raise MessagingNotFoundError()
        prior = self._existing_request(user.id, request_id)
        if prior is not None:
            self._check_idempotent_retry(prior, conversation=conversation, side=side, body=body)
            outbox_ids = self._outbox_ids(prior.id)
            self._db.commit()
            return conversation, prior, outbox_ids, side
        budget = self._lock_send_budget(user.id)
        # The account row lock serializes identical request IDs even when two
        # browser retries target different conversation locks at once.
        prior = self._existing_request(user.id, request_id)
        if prior is not None:
            self._check_idempotent_retry(prior, conversation=conversation, side=side, body=body)
            outbox_ids = self._outbox_ids(prior.id)
            self._db.commit()
            return conversation, prior, outbox_ids, side
        self._charge_send_budget(budget)
        message = self._append_message(conversation, user, side, body, request_id)
        outbox_ids = self._queue_notifications(conversation, message, side)
        self._db.commit()
        return conversation, message, outbox_ids, side

    def inbox(self, user: User, *, page: int, page_size: int) -> tuple[list[dict], int]:
        member_ok = is_member_account(user)
        provider_ok = is_provider_account(user)
        if not member_ok and not provider_ok:
            raise MessagingNotFoundError()
        filters = []
        if member_ok:
            filters.append(ProviderConversation.member_user_id == user.id)
        if provider_ok:
            filters.append(ProviderConversation.provider_user_id == user.id)
        condition = or_(*filters)
        conversations = self._db.scalars(
            select(ProviderConversation)
            .where(condition)
            .order_by(
                ProviderConversation.last_message_at.desc().nullslast(),
                ProviderConversation.id.desc(),
            )
        ).all()
        authorized = []
        for conversation in conversations:
            try:
                _conversation, side, provider, _owner = self._conversation_for_participant(
                    conversation.id, user
                )
            except MessagingNotFoundError:
                continue
            authorized.append((conversation, side, provider))
        total = len(authorized)
        start = (page - 1) * page_size
        items = []
        # Keep the existing authorized pagination boundary. Only decrypt saved
        # contacts on the requested page, never across the entire history.
        for conversation, side, provider in authorized[start : start + page_size]:
            contact = self._shared_contact(conversation, side)
            unread = self._unread_count(conversation, side)
            items.append(
                {
                    "id": conversation.id,
                    "provider_id": provider.id,
                    "provider_name": provider.name,
                    "member_name": (contact["name"] or None) if contact is not None else None,
                    "last_message_at": conversation.last_message_at,
                    "unread_count": unread,
                    "last_sequence": conversation.last_sequence,
                    "notifications_failed": self._notifications_failed(
                        conversation, user
                    ),
                }
            )
        return items, total

    @staticmethod
    def _shared_contact(conversation: ProviderConversation, side: str) -> dict | None:
        """Read historical consented contact only after participant authorization.

        Missing/unusable names are not identities to infer from other fields.
        Encryption and invalid snapshot failures retain the safe content error.
        """
        if side != "provider" or conversation.contact_consent_at is None:
            return None
        plaintext = decrypt_text(
            conversation.contact_snapshot_ciphertext,
            conversation_id=conversation.id,
            record_id=conversation.id,
            field="contact_snapshot",
        )
        try:
            contact = json.loads(plaintext)
            if not isinstance(contact, dict):
                raise ValueError
            if any(not isinstance(contact.get(field, ""), str) for field in ("email", "phone")):
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise MessagingCiphertextInvalid(
                "Private message content could not be authenticated."
            ) from exc
        name = contact.get("name")
        return {
            "name": name.strip() if isinstance(name, str) else "",
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
        }

    def _unread_count(self, conversation: ProviderConversation, side: str) -> int:
        other_side = "provider" if side == "member" else "member"
        read_column = (
            ProviderMessage.member_read_at
            if side == "member"
            else ProviderMessage.provider_read_at
        )
        return int(
            self._db.scalar(
                select(func.count())
                .select_from(ProviderMessage)
                .where(
                    ProviderMessage.conversation_id == conversation.id,
                    ProviderMessage.sender_side == other_side,
                    read_column.is_(None),
                )
            )
            or 0
        )

    def _notifications_failed(
        self, conversation: ProviderConversation, participant: User
    ) -> bool:
        return bool(
            self._db.scalar(
                select(func.count())
                .select_from(MessagingNotificationOutbox)
                .where(
                    MessagingNotificationOutbox.conversation_id == conversation.id,
                    MessagingNotificationOutbox.recipient_user_id == participant.id,
                    MessagingNotificationOutbox.status == "failed",
                )
            )
            or 0
        )

    def unread_count(self, user: User) -> int:
        if not is_member_account(user) and not is_provider_account(user):
            raise MessagingNotFoundError()
        conversations = self._db.scalars(
            select(ProviderConversation).where(
                or_(
                    ProviderConversation.member_user_id == user.id,
                    ProviderConversation.provider_user_id == user.id,
                )
            )
        ).all()
        total = 0
        for conversation in conversations:
            try:
                _conversation, side, _provider, _owner = self._conversation_for_participant(
                    conversation.id, user
                )
            except MessagingNotFoundError:
                continue
            total += self._unread_count(conversation, side)
        return total

    def thread(
        self, user: User, *, conversation_id: UUID, before_sequence: int | None, limit: int
    ) -> dict:
        conversation, side, provider, _owner = self._conversation_for_participant(
            conversation_id, user
        )
        stmt = select(ProviderMessage).where(
            ProviderMessage.conversation_id == conversation.id
        )
        if before_sequence is not None:
            stmt = stmt.where(ProviderMessage.sequence < before_sequence)
        rows = list(
            self._db.scalars(
                stmt.order_by(ProviderMessage.sequence.desc()).limit(limit)
            ).all()
        )
        rows.reverse()
        messages = [
            {
                "id": row.id,
                "sequence": row.sequence,
                "sender_side": row.sender_side,
                "created_at": row.created_at,
                "body": self._message_plaintext(conversation, row),
            }
            for row in rows
        ]
        contact = self._shared_contact(conversation, side)
        return {
            "conversation": {
                "id": conversation.id,
                "provider_id": provider.id,
                "provider_name": provider.name,
                "member_name": (contact["name"] or None) if contact is not None else None,
                "last_message_at": conversation.last_message_at,
                "unread_count": self._unread_count(conversation, side),
                "last_sequence": conversation.last_sequence,
                "notifications_failed": self._notifications_failed(conversation, user),
            },
            "messages": messages,
            "contact": contact,
            "next_before_sequence": rows[0].sequence if len(rows) == limit else None,
            "unread_count": self._unread_count(conversation, side),
        }

    def _advance_read_cursor(
        self, conversation: ProviderConversation, side: str
    ) -> int:
        cursor_attr = "member_read_sequence" if side == "member" else "provider_read_sequence"
        read_attr = "member_read_at" if side == "member" else "provider_read_at"
        cursor = getattr(conversation, cursor_attr)
        rows = self._db.execute(
            select(ProviderMessage.sequence, ProviderMessage.sender_side, getattr(ProviderMessage, read_attr))
            .where(
                ProviderMessage.conversation_id == conversation.id,
                ProviderMessage.sequence > cursor,
            )
            .order_by(ProviderMessage.sequence)
        ).all()
        for sequence, sender_side, read_at in rows:
            if sender_side != side and read_at is None:
                break
            cursor = sequence
        setattr(conversation, cursor_attr, cursor)
        return cursor

    def mark_read(
        self, user: User, *, conversation_id: UUID, message_sequences: list[int]
    ) -> tuple[list[int], int]:
        conversation, side, _provider, _owner = self._conversation_for_participant(
            conversation_id, user
        )
        conversation = self._lock_conversation(conversation.id)
        if message_sequences:
            if any(sequence > conversation.last_sequence for sequence in message_sequences):
                raise MessagingReadSequenceError()
            messages = list(
                self._db.scalars(
                    select(ProviderMessage)
                    .where(
                    ProviderMessage.conversation_id == conversation.id,
                    ProviderMessage.sequence.in_(message_sequences),
                    )
                ).all()
            )
            if len({message.sequence for message in messages}) != len(set(message_sequences)):
                raise MessagingReadSequenceError()
            read_attr = "member_read_at" if side == "member" else "provider_read_at"
            now = datetime.now(timezone.utc)
            for message in messages:
                if message.sender_side != side and getattr(message, read_attr) is None:
                    setattr(message, read_attr, now)
            self._db.flush()
            received_sequences = sorted(
                message.sequence for message in messages if message.sender_side != side
            )
        else:
            received_sequences = []
        cursor = self._advance_read_cursor(conversation, side)
        self._db.commit()
        return received_sequences, cursor