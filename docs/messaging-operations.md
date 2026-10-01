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

### Development preview and published environments

Configure both values as **protected secrets**, not ordinary environment
variables. On Replit, development secrets are entered through the workspace
Secrets tool (or the Agent's secure secrets form); published app secrets are
configured separately in Publishing. A preview failure does not establish the
published app's configuration. Never copy secret values into chat, terminal
output, screenshots, test artifacts, `.env` files, or setup documentation.
Messaging keys must also remain independent of contact-encryption keys.

Before initial provisioning, inspect only aggregate conversation/message counts
and the version/key-ID prefixes of stored envelopes in the target environment.
Do not retrieve message bodies, contact snapshots, or participant details.
If any ciphertext exists, recover its original keys through the operator's
protected backup process and retain every required key ID. A newly generated key,
even under the same ID, cannot decrypt that history. Stop if recovery is not
possible; do not reset records or overwrite the keyring to make availability pass.

When both tables are empty, an operator may generate a new independent 32-byte
key using a trusted cryptographically secure local tool or secret manager,
Base64-encode those bytes, and enter the JSON keyring directly into the protected
form. Choose an ID containing only letters, digits, underscores, or hyphens
(1–32 characters), and enter the identical ID as the active-key secret. Preserve
a protected recovery copy before accepting messages. The example above contains
no usable key and must not be submitted literally.

Restart the development backend after saving secrets: settings are cached per
process. Validate using `ensure_encryption_available()` without printing settings
or decoded keys, then check the authenticated availability endpoint for an
eligible provider. Successful encryption configuration does not make an
unpublished, inactive, unlinked, or ambiguously linked provider eligible.
Do not change account approval states or link accounts by email to work around
these separate eligibility checks. Direct contact must remain available when
messaging fails closed.

Verify the full conversation flow with labelled synthetic participants and
isolated SMTP before reporting recovery, including reopening encrypted history
after a backend restart. Record preview evidence separately from deployment
evidence. Production provisioning, restart, or deployment requires separate
operator approval; restoring the preview is not proof that production works.

### Repeatable isolated recovery check

With the normal development frontend running and valid protected messaging
settings available, run from the repository root:

```sh
python3 scripts/check-private-messaging-isolated-browser.py
```

This check runs the shipped frontend against temporary application processes
and a uniquely owned `pm_smoke_*` PostgreSQL schema. Browser API requests are
routed only to those processes, and SMTP methods are stubbed before startup.
The check never changes public-schema accounts, providers, or messages. It
removes its own schema and disposable processes on exit. Do not run it against
production. It requires free local ports 8008/8009 and Chromium.

The check exercises profile entry, contact preview, client/server consent,
both inboxes, provider replies, participant isolation, ciphertext-only storage,
and reading the thread after a fresh backend process starts with the same
protected settings. Additional isolated processes verify missing/invalid-key
failures while direct contact remains available. Its output contains safe
counts and stage/status diagnostics only. Screenshots under
`screenshots/private-messaging-isolated-smoke/` contain labelled synthetic
records, not real user activity. See `messaging-recovery-verification.md` for
the development recovery evidence and deployment boundary.

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
authorized application process or conversation participants. Private message
bodies and conversation-specific consent/contact snapshots use the separate
messaging keyring described above. Account, profile, invitation, delivery,
enquiry, subscriber, feedback, and historical contact data have their own
encryption and blind-index key material and operational lifecycle; do not reuse
messaging keys for contact encryption. See
[`contact-encryption-operations.md`](contact-encryption-operations.md) for
contact-data conversion, cutover, rotation, and recovery procedures.

Database encryption does not sanitize older backups, WAL/archive files,
replicas, exports, application logs, or SMTP systems. Contact encryption also
does not discover arbitrary contact details typed into unrelated free-text
fields. Treat old database copies as containing plaintext contacts unless they
were independently protected or securely retired under the organization's
retention process.
