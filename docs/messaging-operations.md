# Private messaging operations

## Encryption key provisioning

Messaging is unavailable until its dedicated keyring is provisioned. Set
`MESSAGING_ENCRYPTION_KEYRING` in the deployment secret manager to a JSON object
whose values are canonical Base64 encodings of 32 independently generated,
cryptographically random bytes, for example:

```json
{"2026-01":"<base64-encoded-32-random-bytes>"}
```

Set `MESSAGING_ENCRYPTION_ACTIVE_KEY_ID` to the selected object key (for
example, `2026-01`). The value in angle brackets is an instruction, not a
usable key. Never store a real key in source control, database backups,
application logs, or ordinary configuration files. Never derive or reuse the
JWT `SECRET_KEY`.

Back up the keyring through the secret manager's protected recovery process,
separately from database backups. Verify key recovery before relying on a
database restore. For rotation, provision a new key ID while retaining all old
keys, switch the active ID, and re-encrypt existing records with authenticated
record/field binding. Only remove an old key after verifying there are no
remaining ciphertexts that need it. Losing a key makes corresponding content
unreadable; do not replace an unavailable key with plaintext fallback.

## Notification delivery

Message notification outbox entries are committed with the accepted message.
SMTP runs after commit and is not part of the message-send response. Mail
contains no message text or consented contact snapshot; recipients are the
explicit member/provider account addresses and links lead to authenticated
inboxes. An accepted message remains accepted if SMTP or delivery accounting is
unavailable.

Outbox work is claimed durably before SMTP so concurrent workers cannot send
the same notification. A `processing` item left by a crash or uncertain SMTP
handoff is intentionally not retried automatically: an SMTP server may have
accepted it before the process lost its result. Inspect the correlated delivery
log and SMTP provider records before deciding on any operator action. A failure
to create the durable delivery attempt occurs before SMTP and leaves the intent
recoverable as pending. Outbox errors must never contain message text, contact
data, recipient addresses, or raw SMTP responses.

## Privacy and transport

Deploy the application only behind HTTPS. Database ciphertext at rest plus
HTTPS is **not end-to-end encryption** and does not protect content from the
authorized application process or conversation participants. Existing account
and profile contact fields retain their existing storage behavior; the
messaging encryption applies only to the new conversation bodies and
conversation-specific consent/contact snapshots.