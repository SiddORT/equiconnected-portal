# Private provider messaging API contract

Base path: `/api/v1/messages`. All endpoints require an access token. Member
endpoints accept only verified `horse_owner`/`stable_manager` accounts; provider
endpoints accept only the provider account explicitly linked to the conversation.
Accounts with the `admin` role as their primary or any assigned role are never
participants, even if they also have a member/provider role assignment.

The API is deliberately unified: the authenticated participant role selects the
inbox/thread view. Message bodies and consented contact snapshots are decrypted
only after current participant, account, listing, and explicit ownership checks.
If the listing becomes unavailable or provider ownership changes, access is
unavailable; private history is never transferred to a new owner. Messaging also
fails closed with HTTP 503 when its dedicated encryption keyring is missing or
invalid, without disabling unrelated portal functionality.

## Endpoints

- `GET /availability?provider_id=<uuid>` — verified member only. Returns
  `{ "available": boolean, "reason": string | null, "provider_name": string | null }`.
  `reason` is one of `provider_unavailable`, `provider_account_unavailable`,
  `provider_account_ambiguous`, or `messaging_encryption_unavailable`; do not
  expose owner account details here.
- `POST /start` — verified member only. Body:
  `{ "provider_id": "<uuid>", "request_id": "<uuid>", "message": "<plain text>", "consent": true }`.
  Account name/email/phone and participant IDs are derived server-side. Reject
  missing name/phone with `profile_incomplete`; reject absent consent. Creates
  or reuses the one conversation for that member/listing/provider-account tuple
  and atomically saves the first message and notification outbox entries.
- `GET /inbox?page=1&page_size=20` — participant-scoped inbox, newest activity
  first. Returns `{ "items": [...], "page": number, "page_size": number,
  "total": number }`. Items include conversation/provider (or member) display
  metadata, latest message timestamp, participant's unread count, and no body.
  Each summary exposes only the caller's own `notifications_failed` boolean,
  never a recipient, other participant's delivery status, or SMTP detail.
- `GET /unread` — `{ "count": number }`, scoped to the authenticated participant.
- `GET /{conversation_id}?before_sequence=<int>&limit=50` — participant-scoped
  thread. Returns the conversation metadata, ordered message items (each with
  sequence, sender side, timestamp, and plaintext body), and the participant's
  encrypted contact snapshot only in the provider view. This is a read-only
  fetch: it does not mark any message read or advance a cursor. The conversation
  summary's `notifications_failed` value reflects only failed notification
  intents addressed to the authenticated participant.
- `POST /{conversation_id}/messages` — participant-scoped reply. Body:
  `{ "request_id": "<uuid>", "message": "<plain text>" }`. Returns the saved
  message; duplicate request IDs return the original message and never create
  another notification.
- `POST /{conversation_id}/read` — body
  `{ "message_sequences": [<int>, ...] }` (at most 100 sequences). Marks only
  those exact, existing, received messages as read; the response includes the
  marked sequences and the highest contiguous read cursor. Legacy clients may
  send `{ "through_sequence": <int> }`, which marks only that single message,
  not every earlier sequence.

Messages are plain text only (1–5,000 characters after trimming). Bodies are
rendered as text, never HTML. The UI should send only sequences actually made
visible to the participant (for example, after a message enters the viewport),
not every message returned by a thread fetch. Message-specific read receipts
prevent a visible later message, pagination, or a reply from implicitly marking
an earlier unseen received message read. Inbox/thread pagination and send limits
are database-backed; conversation message sequences serialize concurrent sends.
Responses never reveal whether an unrelated conversation ID exists.

## Consented provider conversation labels

Inbox items and thread conversation summaries include the compatible nullable
`member_name` field (clients may also receive an omitted field from older servers).
Only the currently authorized, original provider participant receives a non-null
value. It is the trimmed usable string name in the saved encrypted contact
snapshot, with recorded `contact_consent_at`, not the member's live profile.
Existing snapshots work without resubmission or backfill; later profile edits
never replace the historical shared name.

For members this field is null and labels continue to use `provider_name`.
Without recorded consent the provider receives null and no thread contact
snapshot. A readable snapshot with a missing, non-string, or blank name produces
null; the provider interface uses “Member conversation” consistently. It must
never substitute email, phone, profile data, or another participant's identity.
Inbox summaries contain no other contact fields. Label decryption happens only
for the requested authorized page; thread reads decrypt the contact once and
reuse it for the summary.

Missing/invalid keys and unknown key IDs retain the safe HTTP 503
`messaging_encryption_unavailable` response. Unauthenticated ciphertext and
invalid JSON/object snapshots retain HTTP 503 `message_content_unavailable`,
without identity fallback. Names are not stored as plaintext labels, added to
notifications/logs/analytics, or exposed through public/admin APIs. Existing
participant and original-owner checks apply before name decryption.

## Durable notification outbox

Every accepted new message creates its notification intent(s) in the same
database transaction as the encrypted message. The `messaging_notification_outbox`
table is an internal worker contract, not a public API:

- `id UUID` — stable outbox item identifier.
- `conversation_id UUID`, `message_id UUID`, `recipient_user_id UUID` — all
  refer to the exact bound conversation/message/account; recipient is resolved
  from the conversation participant, never request data.
- `event_type` — `member_acknowledgement`, `provider_new_message`, or
  `member_reply`; unique with `(message_id, recipient_user_id, event_type)`.
- `status` — `pending`, `processing`, `sent`, or `failed`.
- `attempt_count` integer (starts at zero), `available_at` timestamp,
  `locked_at` nullable timestamp, `sent_at` nullable timestamp, `last_error`
  nullable short safe code (never content, contact information, email address,
  or raw SMTP exception).
- `created_at`, `updated_at` timestamps.

Outbox rows contain no body, contact snapshot, or untrusted mail payload. The
notification worker obtains the explicit recipient account email and safe
provider display name from the referenced records; deep links point to the
authenticated inbox. API handlers schedule a lazy
`app.services.messaging_notifications.dispatch_pending` background import only
after commit, passing the committed outbox item UUIDs. SMTP and delivery-log
accounting are never response-critical. A lost HTTP response is recovered with
the same request UUID and does not resend an acknowledgement.

## Encryption operations

Use an AES-256-GCM keyring supplied only via the dedicated
`MESSAGING_ENCRYPTION_KEYRING` JSON environment setting and a
`MESSAGING_ENCRYPTION_ACTIVE_KEY_ID`. Each keyring value is canonical Base64
for exactly 32 random bytes. Envelopes retain a format version and key ID, and
authenticated data binds ciphertext to its record and field. Provision through
the deployment secret manager; never reuse `SECRET_KEY`, commit keys, print
them, or put plaintext in logs/audit/analytics. Keep old key IDs available for
decryption through a planned re-encryption before retiring a key. Back up keys
separately from the database and test key restoration before database recovery.
Production requires HTTPS. This is encrypted storage plus HTTPS, not end-to-end
encryption, and does not protect content from an authorized application process
or participant.