# Contact-data encryption operations

## Scope and security boundary

Structured email addresses and telephone values are encrypted by the
application before persistence. This covers account identities, provider
contacts, applications, invitations and portal-access recipients, profile and
organization-request contacts, delivery-accounting recipients, public
enquiries/subscribers, feedback/review attribution, and inventoried historical
JSON snapshots. Exact-match operations use separate keyed blind indexes;
ciphertext is randomized and bound to its record and field. Country dialing
codes are metadata, but a complete telephone number must not remain in another
readable storage field.

This is encryption at rest, not end-to-end encryption. Authorized application
processes can decrypt values needed for authentication, delivery, or authorized
views. Blind indexes leak equality within their domain and should be treated as
sensitive. They are not plaintext search indexes and must never be returned by
an API. Existing substring search/sorting may require decrypting and filtering
the complete eligible candidate set in application memory, which has a
material performance cost as the dataset grows. Monitor query/runtime
performance without logging contacts.

The protection applies to the inventoried structured fields, not arbitrary
email addresses or phone numbers that users may type into unrelated free-text
content. Database conversion does not rewrite historical backups, WAL/archive
files, replicas, exports, logs, or copies held by external email providers.
Handle those separately under the applicable retention and incident-response
process; do not claim a live-table migration sanitizes them.

## Provisioning and recovery

Provision `CONTACT_ENCRYPTION_KEYRING` as a JSON object mapping key IDs to
canonical Base64 encodings of independently generated 32-byte random keys,
`CONTACT_ENCRYPTION_ACTIVE_KEY_ID` as one key ID in that object, and
`CONTACT_BLIND_INDEX_KEY` as a separate canonical Base64 encoding of 32
independently generated random bytes. Use the deployment's protected secret
manager. A deployment with absent or invalid contact keys must fail closed;
never substitute plaintext, a JWT secret, or the separate private-messaging
keys. Do not place real key values in source control, SQL, ordinary
configuration files, commands, logs, or this document.

Store a protected recovery copy of both keyrings separately from database
backups. Restrict access to the application/operator roles that require it,
and periodically verify restoration through the secret manager's recovery
process. Restoring encrypted database data without every key version needed by
that data makes contacts unreadable. Keep old keys available until data,
replicas, and retained recoverable backups have been assessed.

## Controlled conversion and cutover

The migration adds ciphertext-compatible TEXT storage, blind-index columns,
constraints, a migration-state table, and database triggers that reject
plaintext writes to inventoried scalar/JSON contact fields, email/phone values
in generated display-name fields, and unredacted contact data in audit
metadata. On contact-field inserts/updates, the trigger also requires an
encrypted scalar to have a well-formed blind-index value; unchanged legacy
plaintext rows remain readable for the bounded conversion. It does not itself
decrypt, encrypt, or rewrite customer rows. The conversion utility is an
operator maintenance tool, not startup/deployment automation.

Apply schema changes in a development/schema-validation environment first.
For managed Replit production, use **Publish schema diff** generated from the
applied and verified development schema; do not run Alembic or ad hoc schema
SQL against managed production. The Publish workflow is not assumed to install
custom PostgreSQL functions or triggers. Once published, run the tool's
`preview` readiness checks, which verify the expected enabled guards and
schema/index requirements without changing persistent application data. If any
guard/function is absent, the preview must fail and all production data
mutation must stop; reconcile through the platform-supported schema process
before proceeding. For externally managed
production databases, operators may instead apply the reviewed Alembic
migration with the normal production change approval.

Run development/external-production schema operations and the tool from
`backend/`:

```bash
# Development/schema validation, or externally managed production only:
alembic upgrade head
python scripts/contact_data_migration.py preview --batch-size 500

# Set only after the maintenance window is established and old writers are stopped.
export CONTACT_ENCRYPTION_MAINTENANCE_WINDOW=1
python scripts/contact_data_migration.py convert \
  --batch-size 500 --confirm CONTACT_DATA_CONVERSION
python scripts/contact_data_migration.py verify --batch-size 500
python scripts/contact_data_migration.py complete-cutover \
  --batch-size 500 --confirm CONTACT_DATA_CONVERSION
```

For production mutation, include `--production-approval <change-ticket>` on
both `convert` and `complete-cutover`; record the approval separately through
the normal change-control process. The gate treats either
`ENVIRONMENT=production` or `REPLIT_DEPLOYMENT=1` as production. The approval
reference is not a secret and is never emitted by the utility. Keep the
maintenance-window environment setting enabled only for the controlled
window.

The intended workflow is:

1. Apply the schema through the deployment-appropriate process above. The
   contact-storage revision follows the canonical merge `e352d353a901`, which
   preserves the combined delivery-purpose constraint. Verify there is one
   Alembic head in the schema source and that the published/applied database
   has the expected tables, indexes, enabled guard triggers, and guard
   functions. `preview` performs the readiness checks and fails closed if
   required guards are missing; do not infer that Publish installed them.
2. Provision and test keys in the protected secret manager. Confirm a verified,
   restorable database backup and a separate protected key recovery copy.
3. Stop all old application workers, schedulers, queue consumers, and ad hoc
   writers that can still persist plaintext. Prevent new old-version processes
    from starting for the full conversion and verification interval. There is
    no mixed-version legacy-writer compatibility phase. Deploy compatible
    readers/writers only in the coordinated cutover after verification; a
    rolling deployment with any legacy writer is not safe.
4. Run `preview` first, with no mutation approval. Preview reports only
   aggregate progress and validation results: never contact values,
   ciphertext, key material, blind-index digests, or SQL parameters. Review
   inventoried scalar and JSON coverage, planned row counts,
   duplicate/normalization conflicts, index completeness, and authentication
   checks. It also identifies historic email fallbacks in provider display
   names and feedback/review actor names for replacement, and redacts known
   contact values from audit metadata and generated summaries. Resolve every
   conflict and stop if any source is outside the expected inventory. Name
    cleanup is bounded to exact matches against the row's related decrypted
    email (including the known 200-character truncation) or a provider snapshot
    name matching an email in that same snapshot; audit cleanup is
   limited to contact-keyed values, generated summaries, and exact email
   fallbacks in known display-name metadata fields. Arbitrary user-authored
   names and unrelated free text are not rewritten.
5. After a separate operator has reviewed the preview and explicitly approved
   production mutation, run the conversion in bounded batches using the tool's
   exact destructive-approval option. The operation is idempotent and resumes
   from database state after an interruption; retain the maintenance window
   while it runs. Each successful batch is committed independently.
6. Run verification after conversion. It must authenticate-decrypt every
   converted value with record/field binding, confirm all required blind
   indexes are populated, report normalization/uniqueness conflicts, and find
    zero remaining plaintext in every inventoried scalar and JSON contact
    location, generated fallback name, or audit metadata value. Verification
    output is counts/status only. Do not mark cutover complete or resume
    traffic if any check is incomplete or has an error.
7. Use the guarded cutover-completion action only after successful verification
   and explicit operator approval. It takes locks, repeats raw inventory checks,
   and updates migration state only; it performs no persistent schema DDL. It
   must refuse completion when raw inventory checks detect plaintext or missing
   indexes. Keep the legacy plaintext writer versions blocked after cutover.

The CLI is intentionally preview-first, but a preview is only a point-in-time
audit. Re-run it immediately before mutation and use the command's approval
   gate; do not treat an earlier preview as approval or as a guarantee the
   database has not changed. Use a bounded batch size appropriate to database
   load. Progress counters are persisted in the migration-state table, while
   resume is based on rows that still need conversion; no contact values or
   cursors are logged.
Production conversion is a data mutation and requires documented, explicit
operator approval; no migration, deployment hook, or routine test should
invoke it implicitly.

### Interrupted work and rollback

If a batch or process fails, keep writers stopped. Inspect only the tool's
progress/status output and rerun verification or preview before resuming. Do
not manually edit ciphertext/indexes, restore plaintext from a stale backup,
or downgrade after conversion starts. The schema downgrade is safe only while
all encrypted values/indexes remain empty and no converted data exists; it
must refuse to drop populated encrypted/index data. If conversion or
authentication fails, preserve the current database and key material and
restore/recover through a reviewed, isolated procedure using the matching
backup and key versions. Never "roll back" by silently writing plaintext.

## Key and blind-index rotation

Rotation is available only after guarded contact cutover has completed. It is
also preview-first and must be run during a maintenance window with application
writers stopped. It reports progress and counts only.

For encryption-key rotation, provision a new independently generated key and
add it to `CONTACT_ENCRYPTION_KEYRING`, retaining all old key entries. Set
`CONTACT_ENCRYPTION_ACTIVE_KEY_ID` to the new ID before running the following
preview. The utility authenticates old records, re-encrypts them in bounded,
resumable batches using the active key, and verifies all converted values:

```bash
python scripts/contact_key_rotation.py preview --mode encryption
export CONTACT_ENCRYPTION_MAINTENANCE_WINDOW=1
python scripts/contact_key_rotation.py rotate --mode encryption \
  --confirm CONTACT_KEY_ROTATION
python scripts/contact_key_rotation.py verify --mode encryption
```

For blind-index-key rotation, keep the currently active
`CONTACT_BLIND_INDEX_KEY` unchanged and provision the proposed new key as the
temporary protected secret `CONTACT_BLIND_INDEX_NEXT_KEY`. Preview and rotate
while writers remain stopped, then verify all replacement indexes before
switching `CONTACT_BLIND_INDEX_KEY` to the new value and restarting compatible
workers:

```bash
python scripts/contact_key_rotation.py preview --mode index
python scripts/contact_key_rotation.py rotate --mode index \
  --confirm CONTACT_KEY_ROTATION
python scripts/contact_key_rotation.py verify --mode index
```

Include `--production-approval <change-ticket>` with each `rotate` command when
`ENVIRONMENT=production` or `REPLIT_DEPLOYMENT=1`. Do not place key values in
command arguments or logs. If a rotation is interrupted, keep both keys and
the maintenance window in place, preview the
partially rotated state, then resume; already converted rows are recognized
and skipped. The index utility accepts rows indexed by either the old or
proposed key so it can resume safely. If rollback is required, keep both
protected keys, restore the old active blind-index secret, set the former new
secret as the temporary `CONTACT_BLIND_INDEX_NEXT_KEY`, and preview/rebuild
back before resuming traffic.

For encryption-key rotation, new writes may use the new active key while
reads retain every old version. Existing envelopes are re-encrypted with fresh
nonces and the correct record/field binding. Blind-index values are replaced
in place only while the maintenance window is active; the old key is retained
in protected recovery storage until the replacement has been verified and
the coordinated switch is complete. Never use deterministic encryption or an
unkeyed digest as a replacement index.

Do not remove an old encryption or index key until verification proves there
are no remaining rows, replicas, or recoverable backup copies that depend on
it. If a key is suspected compromised or lost, preserve evidence and follow a
reviewed incident/recovery procedure; do not regenerate a key under an
existing ID.

## Encrypted development maintenance backup recovery

A development maintenance backup may be stored outside version control at
`.local/contact-encryption-backups/pre-contact-conversion.ecbackup`, with mode
`0600`. This wrapper contains a PostgreSQL custom archive encrypted with a
retained contact key. Its first line is a JSON header; the remaining bytes are
AES-GCM ciphertext. The exact header bytes are authenticated as additional
data. The header records the format, key ID, nonce, and backup identity, never
the key itself. Keep a protected copy outside the workspace and retain the
referenced key separately; do not assume an ignored local file is a durable
backup.

To recover that wrapper **offline in development**, use the retained protected
keys and write a new, access-restricted archive without overwriting another file:

```bash
umask 077
python - <<'PY'
import base64, json, os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import get_settings
from app.services.contact_encryption import _key_material

assert get_settings().ENVIRONMENT == "development"
assert os.environ.get("REPLIT_DEPLOYMENT") != "1"
source = Path("../.local/contact-encryption-backups/pre-contact-conversion.ecbackup")
header_bytes, ciphertext = source.read_bytes().split(b"\n", 1)
header = json.loads(header_bytes)
assert header["format"] == "equiconnected-contact-maintenance-backup-v1"
_, keys, _ = _key_material()
archive = AESGCM(keys[header["key_id"]]).decrypt(
    base64.b64decode(header["nonce"], validate=True), ciphertext, header_bytes
)
destination = "../.local/contact-encryption-backups/recovered.dump"
fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "wb") as output:
    output.write(archive)
PY
```

Run from `backend/`. Inspect archive readability with `pg_restore --list`
privately, and restore only into a separate empty disposable database first.
Missing keys or authentication failures must stop recovery. The recovered
pre-conversion archive contains legacy plaintext contacts: restrict its access,
do not publish it, and never reopen an application against a restored legacy
schema before applying and verifying the controlled conversion again.
Restoring production requires a separate approved recovery procedure; this
example is not a production rollback command.

## Operations checklist

- [ ] Confirm the maintenance window, complete writer inventory, and blocked
  old-version deployments.
- [ ] Verify the canonical schema revision, one Alembic head, and enabled guard
  triggers/functions through `preview` readiness; stop if any are absent.
  Confirm the independent protected database backup and recoverable key backup.
- [ ] Review a fresh preview and resolve all data/index conflicts.
- [ ] Record explicit production mutation approval outside the conversion
  command/log output.
- [ ] Convert in bounded batches; retain old key versions and resume from
  persisted progress if interrupted.
- [ ] Verify scalar and JSON raw storage, blind-index coverage/conflicts,
  ciphertext authentication, and zero remaining plaintext.
- [ ] Complete the guarded, DML-only cutover, retain a record of aggregate
  verification, and keep plaintext writers blocked.
- [ ] Treat older backups/WAL/logs/external mail copies as a separate retention
  and privacy task.