# Approved provider direct saves: verification and UAT handoff

## Release behavior

- Existing approval/access rules admit approved registrations, completed eligible
  invitations and eligible explicit legacy/direct ownership. Publication and
  operational status are not evidence of account approval and are never changed
  by a profile save. Initial approval and disabled-account checks remain in place.
- Allowed owner edits update the canonical provider record in one transaction,
  including collections and validated new visits. Administrator detail, edit and
  list screens already read this record on load; no background synchronization
  or new admin refresh mechanism is required.
- No new profile review request is created. Old pending/rejected snapshots remain
  private and unchanged on reads. An explicit save validates the displayed draft,
  compares its normalized base with the current listing and refuses stale bases.
  An explicit discard reloads the latest canonical record.
- Saved legacy proposals become `SAVED_DIRECTLY`, not `APPROVED`. Original
  encrypted snapshots and any real earlier rejection/reviewer metadata remain as
  history; the audit records the provider's explicit save. Subsequent admin
  approve/reject actions cannot replay the proposal.

## Migration prerequisite

Run the normal Alembic upgrade in the target release process **before enabling
the new API code to retire drafts**. The additive enum migration
`8e6a1d4b2c90_retire_owner_saved_profile_drafts.py` changes no provider/draft data.
The transaction must commit before PostgreSQL can use the new enum label.
Downgrade intentionally refuses while owner-saved history exists rather than
misclassifying it as administrator approval. Do not delete or relabel history to
force a downgrade. No migration or provider repair was run on UAT for this work.

## Reproduced local evidence

- The former publication branch deliberately staged every published owner edit.
  This explained the approval banner and provider/admin discrepancy.
- Real FastAPI/PostgreSQL tests cover both approval journeys, legacy/direct
  ownership, published/unpublished and active/inactive listings, canonical
  administrator reads, protected fields, schedule/collection rollback, stale
  bases, retained history, preloaded admin decisions and provider-row locking.
- An opt-in Chromium test performs desktop (1440px) and mobile (390px) edits
  through the shipped form and the real isolated API/database, reloads the owner
  page, then opens the administrator detail page for the same saved record.
  All API traffic is intercepted into the pytest test schema; unknown requests
  fail closed. Session bootstrap is synthetic; this is not a live login test.
- Feedback returned HTTP 500 / `ContactCiphertextInvalid` when a synthetic
  review's member had incompatible contact storage. The query unnecessarily
  loaded the entire member row, including encrypted contact columns. It now
  selects only structured names for masking. A regression verifies HTTP 200,
  unchanged allowed review states, rating-only entries and masked identities.
  Contact decryption elsewhere remains strict; there is no plaintext fallback.
  Member/public review queries and visibility rules remain separate and unchanged.
- Browser checks cover feedback success, empty, denied/session-expired,
  transient failure and explicit retry, including narrow mobile widths.
  These feedback browser states use labelled synthetic fixtures; real feedback
  query/serialization and ownership are separately tested through FastAPI.

Reproduce from this workspace, with Frontend running:

```sh
cd backend
RUN_PROVIDER_BROWSER=1 python -m pytest \
  tests/test_provider_direct_saves.py tests/test_provider_direct_browser.py \
  tests/test_provider_draft_migration.py tests/test_provider_feedback.py -q
cd ..
python scripts/check-provider-feedback-browser.py
python scripts/check-provider-editing-browser.py
cd frontend
npm test -- --maxWorkers=2
npm run build
```

Do not run separate backend pytest processes concurrently: they share one
disposable schema. Browser evidence is synthetic and saved under ignored
`generated-artifacts/` or a printed temporary directory.

## Not established on UAT

The provided feedback screenshot contains a generic failure state, not the HTTP
status or server exception. This fork reports no attached published deployment
and no deployment logs. The local contact-storage failure is therefore **not a
verified diagnosis of the reported UAT incident**, and no deployed fix is claimed.
No real account sign-in, notification, production provider write or bulk draft
application was performed.

For the operator with authorized UAT access:

1. In the provider's browser Network panel, inspect
   `GET /api/v1/provider/portal/feedback?page=1&page_size=10`. Record only HTTP
   status, safe error code and timestamp. Never share authorization headers,
   cookies, member data, ciphertext, keys or an unredacted HAR.
2. Correlate the timestamp/path with sanitized server exception **class**.
   If the old query throws `ContactCiphertextInvalid` while hydrating review
   members, this release removes that unnecessary dependency. If failure occurs
   during current-account authentication instead, restore the original target
   environment's contact key configuration using the protected operations
   procedure; never regenerate keys or repair data speculatively.
3. A 404 requires checking that the intended backend release includes the
   `/api/v1/provider/portal/feedback` route and the proxy forwards `/api/v1`.
   A 401/403 requires checking session/account and explicit listing ownership,
   not granting wider access. Missing-column/relation failures require comparing
   the actual database revision with the intended release and applying the
   normal migration process, never automatically stamping history.
4. After an authorized release, verify feedback read-only with the affected
   account, including explicit retry. Use a dedicated synthetic UAT account for
   any provider-save/admin-read smoke check; obtain separate authorization before
   creating records or changing any provider. Do not test writes on the reporter's
   real listing or send real notifications.
5. Confirm the response contains only review id, rating, comment, masked name,
   timestamp and allowed moderation status. Private notes and member identity
   must remain absent. Escalate a different exception based on that evidence;
   do not treat this local regression as proof of every possible UAT failure.
