# Stored Contact Data Inventory and Compatibility Map

**Audit scope:** the final contact-encryption implementation in the current
working tree: backend models, ORM/Core persistence boundaries, repositories,
services, APIs, Alembic storage migration, operator conversion/key-rotation
scripts, and reset/seed scripts. “Contact” here principally means an email
address or complete telephone number. A dialing code by itself is non-secret
metadata.

The implementation maps structured contact columns to authenticated encrypted
storage with keyed blind indexes, protects recognized contact leaves in four
JSON snapshots, and adds database guards against plaintext writes. The
schema-only migration and conversion utility are present, but this audit did
not apply migrations, run conversion/cutover, or perform any production
operation; actual database state therefore depends on whether an operator has
run and verified the documented process. See
`docs/contact-encryption-operations.md` for the operator/key lifecycle guide.

## Findings at a glance

- **Structured storage covered:** all direct contact columns in the inventory
  below are mapped through encrypted ORM storage and blind-index columns; the
  historical converter enumerates the same scalar fields. Provider profile
  snapshots, member-feedback action snapshots, and provider-review action
  snapshots encrypt recognized contact keys recursively. Existing generated
  email copies in display-name columns, exact email copies in provider-profile
  snapshot names, and contact-bearing audit metadata have explicit conversion
  handling. The source sweep found no additional modeled
  structured email/telephone field or current production contact writer outside
  this inventory.
- **Additional guard coverage:** new invitation drafts use “Invited provider”
  rather than copying recipient email into `providers.name`; member feedback
  and review actions use non-email name fallbacks. Database triggers reject
  plaintext writes to the structured fields/snapshots, contact-bearing audit
  metadata, and detectable email/phone strings in the generated display-name
  columns they guard.
- **Compatibility implemented:** exact comparisons and uniqueness use
  domain-separated blind indexes; supported substring search streams the
  complete eligible set and filters decrypted values before pagination;
  subscriber CSV output is streamed. Authorized API/SMTP paths continue to
  receive plaintext in application memory.
- **Member recovery:** the merged implementation adds a member-only recovery
  route/service and a token table containing a user ID, token hash, expiry, and
  use/invalidation timestamps—no email, phone, or raw token field. Delivery
  recipients use the existing encrypted `email_delivery_logs.recipient_email`.
  Account lookup and delivery cooldown use normalized exact equality through
  the encrypted-field blind-index comparator.
- **Provider contact insights:** contact-click events persist an allowlisted
  action, provider ID, and UUIDv7 retry key, not a complete email/phone,
  destination, or contact blind index. The UUIDv7 embeds event time and is not
  derived from a contact value. Durable reporting stores daily aggregates;
  short-lived receipts contain only the event UUID and timestamps.
- Private messaging remains separate: message bodies and the member
  contact/consent snapshot are encrypted using the independent messaging
  keyring. The contact keyring is not reused for that ciphertext.

## Persistent storage inventory

| Storage location | Contact data and origin | Current constraints / copies | Read, output, and migration notes |
| --- | --- | --- | --- |
| `users.email`, `users.mobile_number` (`app/models/user.py`) | Account login/identity email and member/provider mobile. `UserRepository.create_user` writes both; `AuthService.register` and `register_provider` populate them; invitation/direct-access flows also create users. Profile edits update `mobile_number` through `ProfileService.update_personal`. `seed_admin.bootstrap_admin` creates the configured admin. | The mapped email/mobile columns are encrypted `TEXT`; private blind-index columns back normalized exact matching and email uniqueness. Email remains the login ID. `mobile_number` is nullable and non-unique. | ORM reads expose plaintext only in application memory. `UserRepository.get_by_email` uses the encrypted comparator. Admin registrant partial search filters decrypted candidates before pagination. `reset_non_admin_users.py` preserves email ordering in memory and still prints account emails in its operator report. |
| `providers.email`, `providers.phone`, `providers.emergency_contact_number` (`app/models/provider.py`) | Legacy scalar provider contacts. Provider create/update APIs and services write the scalar fields; invitation drafts and approval workflows write them; provider-portal edits mirror structured contact collections to these columns. Application approval copies `application.user.email` and `user.mobile_number` here and retains the source `users` values. | All three scalar columns now use encrypted `TEXT` mappings and companion blind indexes. There is no contact uniqueness. Legacy phone contains the full telephone value; emergency number is another full-value copy. | Provider schemas retain scalar fallback when no structured entry exists. Live writes and conversion cover these fields; do not remove the fallbacks without separate compatibility changes. Historical backfill migration `781951970595` once nulled email/phone, but later provider portal writers reactivated those scalar columns. |
| `provider_emails.email`, `provider_phones.number` (+ `country_code`) (`app/models/provider.py`) | Provider multi-contact collection rows, written by `ProviderRepository.add_email/add_phone`, provider subresource APIs, full-provider create/update, invitation submission, and provider-profile approval/application paths. | Email and phone values now use encrypted `TEXT` mappings and per-field blind indexes. Existing provider ID indexes and partial unique “one primary per provider” indexes remain; there is no value uniqueness. Phone is split: `country_code` is metadata, `number` stores the local part. | Provider display remains primary-first, then oldest-created, then ID (`schemas/provider.py::provider_contact_order`). Profile update collections retain deterministic canonicalization. The local number value is protected; do not copy/reconstruct a full number elsewhere. |
| `provider_registration_applications.emergency_contact_number` (`app/models/provider_registration.py`) | Provider registration intake via `AuthService.register_provider`; read in administrator application review; copied to `providers.emergency_contact_number` by `ProviderRegistrationService.approve`. | Encrypted `TEXT` plus blind index; one application per user and no phone uniqueness. The source and approved provider copy coexist. | Both source and approved copy appear in the conversion inventory and use encrypted writes. Administrator review still returns decrypted values to its authorized response. |
| `stable_profiles.contact_email`, `stable_profiles.contact_phone` (`app/models/profile.py`) | Member stable profile creation/edits through `ProfileService.update_stable` and `ProfileRepository.create_stable`. | Both fields now use encrypted `TEXT` plus blind indexes. One profile per user; no contact uniqueness. `contact_name` remains adjacent identifying metadata, not an email/telephone field. | Owner-authorized stable-profile responses decrypt on ORM load. Both fields appear in the conversion inventory. |
| `organization_requests.contact_email` (`app/models/organization_request.py`) | Invited doctor submits request through `OrganizationRequestService.create_request` and `OrganizationRequestRepository.create`. On approval, `OrganizationRequestService.approve` copies it to a new `providers.email`; the request remains stored. | Encrypted `TEXT` plus a blind index; no email uniqueness. Requests are listed by creation/status/type. | Request and approved provider copy are covered by encrypted writes/conversion. Admin request/detail responses continue to expose the decrypted value. There is no email search/sort. |
| `provider_invitations.recipient_email` (`app/models/invitation.py`) | `InvitationService` normalizes the draft recipient and writes the invitation; email edits/resends and final submission continue to use it. | Encrypted `TEXT`; exact lookup and partial unique `(provider_id, recipient_email_blind_index)` use keyed indexes. The new-provider advisory transaction lock uses a domain-separated blind index over provider type + normalized email. | Exact active-invitation checks, cancellation, setup identity, and approval use the encrypted comparator. `InvitationRepository.list` filters decrypted recipients and provider names across the eligible candidate set before pagination. API responses continue to contain decrypted recipient addresses. Service normalization is lowercase/trim. |
| `direct_provider_portal_access.recipient_email` (`app/models/provider.py`) | `DirectProviderAccessService.send` persists the chosen saved provider contact when it creates direct access; used by setup/recovery ownership checks. The linked `users.email` is a second identity copy. | Encrypted `TEXT` plus a blind index; `provider_id` is primary key and `user_id` unique. Recipient itself has no uniqueness constraint. | Access/setup/recovery ownership checks compare decrypted values; admin portal-access details may intentionally display the address. |
| `email_delivery_logs.recipient_email` (`app/models/email_delivery_log.py`) | `EmailDeliveryRepository.record` / `record_durable_attempt` persists recipients for invitation, account verification, provider portal access/recovery/approval, member password recovery, subscriber confirmation, contact confirmation/notification, SMTP test, and messaging notifications. Some are independent-session durable writes. | Encrypted `TEXT` plus a blind index; delivery records remain indexed/sorted by creation time + ID. Failure text is allow-listed. The purpose enum/check constraint includes `member_password_recovery`. | Account-verification, provider-recovery, subscriber cooldown, and member-recovery cooldown comparisons use exact encrypted-field comparisons. Admin log output intentionally returns the decrypted recipient; list filters only by date. |
| `contact_enquiries.email`, `contact_enquiries.phone` (`app/models/contact_enquiry.py`) | Public contact form is durably written by `ContactEnquiryRepository.create` before delivery (`ContactEnquiryService.submit`). Email and phone are then copied into the notification email sent to the configured team; the user's email is the separate confirmation recipient. | Both fields use encrypted `TEXT` and blind indexes; date/type indexes remain. `name` and `message` are adjacent submitted text. | Admin enquiry search streams the complete eligible set and applies the existing name/email/phone/message OR substring match to decrypted values before count/pagination. Admin detail/list intentionally show decrypted enquiry fields. Submitted message content remains arbitrary free text. |
| `subscribers.email` (`app/models/subscriber.py`) | Public subscriber request is normalized by `SubscriberRegistrationRequest`, then stored by `SubscriberRepository.create_or_get`; service sends confirmation and writes a delivery-log recipient. | Encrypted `TEXT`; unique constraint `uq_subscribers_email` now targets `email_blind_index`, retaining the concurrent de-duplication race boundary. The field is lowercased/trimmed by the request schema and blind-index normalization. | Exact lookup and integrity-conflict retry use the blind index. Admin search and CSV filter decrypted contacts in a streamed pass while preserving submitted-at descending + ID order; CSV yields plaintext only to the authorized export response. |
| `member_feedback.submitter_email` (`app/models/member_feedback.py`) | `MemberFeedbackRepository.create` uses PostgreSQL `insert(...).on_conflict_do_nothing(...).returning(...)` and explicit `prepare_contact_values` to copy `member.email` into historical feedback. | Encrypted `TEXT` plus blind index; feedback idempotency remains unique on `(member_id, idempotency_key)`. `submitter_name` now uses a non-email name/fallback. | Admin partial search filters decrypted submitter email and the existing text fields across all candidates before pagination. Member/admin responses continue to display decrypted email. The bulk insert's explicit persistence adapter preserves idempotency. |
| `member_feedback_actions.actor_email` (`app/models/member_feedback.py`) | `MemberFeedbackRepository.add_action` copies the acting user's email into immutable history for member edits/withdrawals and administrator moderation. | Encrypted `TEXT` plus blind index. `actor_name` uses a non-email fallback. JSON `content_snapshot` now uses protected snapshot storage; its subject/message/response/internal note remain arbitrary free text rather than structured contact keys. | Authorized action-history responses expose decrypted actor email. Both actor email and recognized structured contact leaves in the action snapshot are included in conversion. |
| `provider_review_actions.actor_email` (`app/models/provider_review_action.py`) | `ReviewRepository.record_action` copies the acting user's email to review history. | Encrypted `TEXT` plus blind index; `actor_name` now uses first/last name or a non-email fallback. `content_snapshot` uses protected snapshot storage. | Authorized review-action history exposes decrypted actor email. Recognized contact keys in snapshots are protected; user-authored review comments/notes remain free text. |
| `provider_profile_updates.base_profile`, `proposed_profile` JSONB (`app/models/provider.py`) | `ProviderPortalService` creates/replaces complete snapshots through `serialize_editable_profile` when a provider submits/edits a pending profile; both contain `email`, `phone`, `emergency_contact_number`, `emails[].email`, and `phones[].number` plus dialing-code metadata. They snapshot old and proposed contact state independently of live provider rows. | Both JSONB columns now use protected snapshot mappings. One update per provider; review status/submission-time indexes. | ORM load decrypts recognized contact leaves before comparison, canonicalization, authorized admin review, and applying an approved profile. The converter also replaces a known exact equality between snapshot `name` and an email leaf with `Invited provider`. The database JSON guard protects recognized contact keys, not arbitrary contacts embedded in `name` text. Legacy scalar-fallback snapshots remain supported. |

### Provider insights and contact-link event boundary

Provider contact-link instrumentation posts only `provider_id`, an
allowlisted action (`phone`, `email`, or `website`), and a UUIDv7 `event_key`
to `/api/v1/member/providers/{provider_id}/contact-click`. The action labels
identify a link type, not its phone number or email address; the request does
not include the link destination or any contact blind index. The UUIDv7
retry key is not a contact-derived identifier; its embedded timestamp is used
to choose a reporting day and reject out-of-window replays.

Durable contact-click data is limited to daily rows keyed by date, provider
UUID, and action with an aggregate count. Temporary retry receipts contain only
the event UUID and created/expiry timestamps and are cleaned up after the
48-hour retry window. Neither structure retains the member ID, destination,
full telephone/email value, IP address, URL, or an index of a contact value.
The `email` and `phone` action labels are categories only.

Provider Insights combines those click counts with existing daily profile-view
aggregates and counts of new `ProviderConversation` rows. Conversation metrics
do not copy or decrypt the messaging contact/consent snapshot or message body;
those remain in the separate messaging store/keyring described above.
Reported contact-link activations do not establish that a call, email, booking,
or lead was completed. The report fetches the provider display name, not its
structured email/phone fields; that name remains subject to the existing
free-text/historical-name boundary.

### Generated copies and remaining free-text boundary

- **Generated provider display name:** New invitation drafts now use the
  neutral `Invited provider` fallback rather than the recipient address.
  Conversion replaces the known historical exact or truncated recipient-email
  copies in `providers.name` and exact email copies in profile-snapshot `name`
  fields; a database trigger rejects detectable email or phone strings in
  new/changed `providers.name` values. Snapshot `name` is not itself a
  structured contact key and is not covered by that generic contact-key guard.
- **Generated feedback/review names:** Feedback submitter and feedback/review
  action writers now use first/last names or non-email fallbacks, not
  `User.full_name`'s email fallback. Conversion replaces known exact or
  truncated email copies in those name columns; database triggers reject
  detectable email or phone strings in new/changed values.
- **Audit metadata:** `AuditRepository` redacts contact-bearing metadata keys
  and change values, and strips recognizable email/phone strings from summaries.
  The converter also redacts historical contact-bearing metadata and summary
  strings before write guards enforce the same boundary.
- **User-authored or arbitrary text remains outside universal encryption:**
  `contact_enquiries.message`, feedback subject/message/responses/notes, review
  comments/notes, rejection reasons, provider descriptions, and profile
  snapshot `name` text can contain contacts typed by a user.
  `member_browsing_history.filters` persists bounded `name` and `region` text
  and can contain a contact value entered in a search box.
  `MemberFeedbackAction.content_snapshot` and
  `ProviderReviewAction.content_snapshot` duplicate some of that free text.
  `providers.name` and feedback/review name columns are guarded against
  recognizable patterns on future writes, but `contact_enquiries.name` and
  historical embedded or unrecognized contacts in these strings are not all
  discovered by conversion: generated-name cleanup only replaces known exact
  or truncated email copies. Arbitrary free-text detection/encryption is not
  claimed.
- `contact_enquiries.name`, `stable_profiles.contact_name`, and
  `providers.emergency_contact_name` are person-name fields adjacent to
  contact details. They are not email/telephone values; decide separately
  whether broader PII protection is required.

## Writers and persistence boundaries

| Flow | Writer(s) | Current encrypted storage / copies |
| --- | --- | --- |
| Public member/provider registration | `AuthService.register`, `AuthService.register_provider` → `UserRepository.create_user`; provider application repository/model create | Encrypted `users.email` and `users.mobile_number`; provider applications additionally store encrypted emergency contact; verification is sent only after account commit. |
| Personal/stable profile edits | `ProfileService.update_personal`, `update_stable` → `ProfileRepository` | Mutates encrypted `users.mobile_number`; creates/updates encrypted `stable_profiles.contact_email/contact_phone`. |
| Admin/provider listing create and edit | provider/admin APIs → `ProviderService` / `ProviderRepository`; phone/email subresource methods | Encrypted legacy scalar fields and provider contact child rows; admin-visible API payloads decrypt on read. |
| Application approval | `ProviderRegistrationService.approve` | Copies account email/mobile and application emergency phone into encrypted provider fields; application/user sources remain. |
| Invitations and direct portal access | `InvitationService` and `DirectProviderAccessService` | Encrypted invitation recipient, provider scalar/collection fields, setup-created user email, direct access recipient, and delivery-log recipient. New draft provider names do not copy recipient email. |
| Provider-owned profile editing/review | `ProviderPortalService` → profile update repository; `ProviderProfileUpdateService.approve` applies approved draft | Protected contact values in both JSON snapshots and encrypted live scalar/collection fields. The approved listing and snapshots coexist. |
| Organization request/approval | `OrganizationRequestService` / repository | Encrypted request contact email; approval creates provider with the same encrypted value. |
| Public enquiry | `ContactEnquiryService` / `ContactEnquiryRepository` | Encrypted enquiry email/phone; separate encrypted durable delivery recipient; raw enquiry text is included in external notification email. |
| Subscriber registration | `SubscriberService` / `SubscriberRepository` | Encrypted subscriber email plus one or more encrypted durable delivery-log copies. |
| Feedback and review history | Repository PostgreSQL inserts/ORM action constructors | Encrypted feedback submitter email and feedback/review actor emails, with non-email generated names. Bulk insert explicitly prepares contact values. |
| Member password recovery | `MemberPasswordRecoveryService` and `EmailDeliveryRepository` | Uses the account email in memory for lookup/delivery and writes the recipient through encrypted `email_delivery_logs.recipient_email`. Normalized account lookup and cooldown use exact encrypted-field comparisons. The recovery-token row contains no email/phone or raw token. |
| Provider contact insights | `record_contact_click` and `ProviderInsightsService` | Records only link category, provider UUID, UUIDv7 retry receipt, daily aggregate counts, and reporting metadata. It does not persist complete phone/email values or contact blind indexes; conversation reporting counts existing rows without copying their encrypted contact snapshot. |
| Operator bootstrap | `backend/scripts/seed_admin.py` → `bootstrap_admin` → `UserRepository` | Writes encrypted `users.email`; current command output and structured logging use an opaque account ID rather than the address. |
| Demo seed | `backend/scripts/seed_demo_data.py` | Current demo data creates no email/telephone contacts. It is not a current contact writer; preserve this fact rather than assuming every seed file writes contact data. |

`contact_text_column` / the protected JSON type mappings, `protect_model_contacts`,
and explicit `prepare_contact_values` for PostgreSQL bulk inserts form the
current application persistence boundary. They cover direct model
construction, independent delivery-log sessions, and seed-created identities;
the database triggers in the storage migration also reject raw plaintext
contact writes. The converter is separate from the schema-only Alembic
migration. API serialization and exports receive decrypted application values,
not ciphertext or blind-index bytes.

## SQL compatibility: implemented lookups, uniqueness, search, ordering

| Behavior | Current use / implementation |
| --- | --- | --- |
| Normalized exact equality and account uniqueness | `ContactEncryptedText` maps comparisons to domain-separated HMAC blind indexes; ciphertext is randomized and record/field-bound. This backs `UserRepository.get_by_email`, login/signup, verification, invitation/access ownership checks, and provider recovery eligibility. `users.email_blind_index` is unique. Email normalization is lowercase + trim. |
| Invitation concurrency and uniqueness | Active invitation checks and cancellation/invalidation use exact encrypted-field comparisons. The partial unique `(provider_id, recipient_email_blind_index)` index preserves pending/accepted uniqueness; the new-provider advisory lock key is a blind index over provider type and normalized email. There is no plaintext reservation/search shadow. |
| Subscriber de-duplication | Exact lookup maps to the unique `email_blind_index`; unique-conflict recovery and existing subscriber cooldown/SMTP behavior remain. |
| Delivery resend/cooldown comparisons | Delivery-log recipient equality for account verification, provider portal recovery, and subscriber confirmation uses blind indexes. The shared recipient storage is encrypted. |
| Member recovery lookup/cooldown | The service normalizes the input address and compares `User.email` and `EmailDeliveryLog.recipient_email` using exact equality; the encrypted comparator maps both to blind-index lookups. |
| Direct portal account discovery | `DirectProviderAccessService` matches user email against saved provider contacts using encrypted-field comparisons, then retains ownership checks against decrypted current values. |
| Case-insensitive substring search | `UserRepository.list_public_registrants`, `ProviderRegistrationRepository.list`, `InvitationRepository.list`, subscriber list/export, `ContactEnquiryRepository.list`, and `MemberFeedbackRepository.list_admin` stream the full database-eligible ordered candidate set and filter decrypted values with `matches_like_substring` / `page_filtered_candidates` before accurate count and pagination. Existing OR and SQL-LIKE wildcard behavior is retained; candidate scans trade database search efficiency for decryption. |
| Sorting | Contact-column sorting is not offered by public/admin queries. Search results preserve creation/submission-time + ID order; provider contacts retain primary-first, created-time, ID order. Profile snapshots decrypt before canonicalization/comparison. `reset_non_admin_users.py` sorts decrypted rows in application memory for its operator report. |
| Export | `/admin/subscribers/export` streams the complete match set in stable order; authorized CSV rows contain decrypted subscriber emails. |
| No recipient search | `/admin/email-logs` filters by date/day/month/year/range and sorts by `created_at,id`; it has no recipient sort/search. Contact enquiries are newest-first; there is no email sort. |

Email-verification, provider-setup, provider-recovery, and member-recovery
token tables persist token hashes and user/provider foreign keys, not contact
strings. `member_password_recovery_tokens` contains a user ID, a unique
SHA-256 token hash, expiry, used/invalidation timestamps, and ordinary row
timestamps; it has no email/phone or raw-token column. Member recovery
generates a high-entropy token with `secrets.token_urlsafe(48)` and stores only
its hash. The raw token is placed in the email link fragment and is handled in
frontend memory before the URL is replaced; there is no additional
member-recovery encryption key or token secret configuration. The configurable
expiry is `MEMBER_PASSWORD_RECOVERY_EXPIRE_HOURS`. The recipient remains a
contact value in the existing encrypted delivery-log field.

## Authorized plaintext reads and delivery

Plaintext API output is intentional only at established boundaries, after
authorization and schema conversion: a user can receive their own profile;
admins can inspect public registrants, provider applications, contact
enquiries, invitations, subscribers, email history, profile drafts, and
feedback/review action history; published provider contact is included in
directory/detail responses selected by `selected_provider_contact`; provider
portal owners read/edit their authorized listing contacts. Current responses
receive decrypted values only. Never expose envelopes, key IDs,
authentication tags, or blind indexes in these response models.

`EmailService` needs actual recipient and message contacts in memory to hand
off SMTP. Delivery accounting stores each recipient independently. Failure
messages are allow-listed in `email_delivery_repository.py`. Contact-enquiry notifications intentionally transmit email,
phone, and submitted message to the configured team, while confirmation and
other workflows transmit email to SMTP. Database encryption does not protect
SMTP providers, recipient mailboxes, application memory, or authorized
responses.

## Audit, logging, and operator-script status

- Live `AuditRepository` writes redact metadata keys containing contact
  markers, restrict changed-field values, and remove recognizable email/phone
  strings from summaries. The converter applies corresponding cleanup to
  historical `audit_logs.metadata`; the database trigger rejects unredacted
  contact-bearing metadata writes. Arbitrary free-text fields in metadata are
  not a universal detection boundary.
- `AuthService.login` logs `login.failed.unknown_email` without the submitted
  address. `User.__repr__`, `ProviderEmail.__repr__`, and `ProviderPhone.__repr__`
  no longer include contact values. `Provider.__repr__` still includes its
  display name; the database guard rejects recognizable contacts in new or
  changed provider names, but the arbitrary/historical display-name limitation
  described above still applies.
- `main.py`'s unhandled-exception logger stores the exception class, not
  `str(exc)`, and removes invitation tokens from logged paths. Request
  validation omits rejected input from error output. `db/session.py` disables
  SQL echo and hides bind parameters.
- Member-recovery background and reset handlers log fixed event identifiers,
  not account addresses, raw recovery tokens, or exception payloads; recovery
  audit summaries are generic. The one-time token is nevertheless a bearer
  credential in the delivered link and must be protected at the mail/browser
  boundary.
- `backend/scripts/seed_admin.py` writes through the encrypted user repository
  and reports an opaque account ID, not `ADMIN_EMAIL`; it also avoids arbitrary
  exception payloads. `contact_data_migration.py` and
  `contact_key_rotation.py` suppress SQL logging and emit operational counts,
  not cleartext contact values.
- `backend/scripts/reset_non_admin_users.py` is a delete/preview utility, not a
  contact writer. Its exception text is now bounded, but preview/result output
  still prints user emails and invitation-creator emails. This is an
  operator-output boundary that still contains plaintext contact values.
  `backend/scripts/reset_development_data.py` reports retained administrator
  IDs/roles rather than emails. It creates a full-content database backup with
  restrictive file permissions; the archive is still a copy of the database
  contents at backup time (and is not encrypted by this script), so a backup
  created before conversion can contain plaintext.
- `backend/scripts/seed_demo_data.py` currently creates no email/telephone
  contacts; it is not a current production contact writer.
- `781951970595_backfill_provider_contacts.py` historically copied legacy
  `providers.email` / `.phone` into child contact tables and nulled those
  scalars, but later provider portal code reactivated scalar writes.
  `a1523b656e74_add_provider_invitations.py` historically created plaintext
  invitation recipient storage/indexes. These historical migrations do not
  bypass the current runtime mappings or replace the separate conversion.
- Test factories/fixtures and PostgreSQL bulk inserts in `backend/tests` are
  test-only contact writers. Production bulk feedback insertion uses explicit
  contact preparation; conversion/rotation scripts are the intended
  maintenance writers.

## Member recovery and contact-storage compatibility

Member recovery is separate from provider portal recovery and is limited by
the service to active, verified public-member accounts with no provider-workflow
link. Anonymous requests receive a uniform acknowledgement; authenticated
requests derive the recipient from the session. Password reset stores no
contact copy on its token row, does not persist the raw token, and sends the
recipient through the existing encrypted delivery-log field. The current
service normalizes email before exact account lookup and delivery cooldown;
those direct equality predicates use the contact blind indexes and are
compatible with ciphertext-backed columns.

## Migration and operational status

The contact-storage Alembic revision `6c4e8a2f1b90` adds ciphertext-capable
columns, blind-index columns/constraints, migration state, and triggers that
reject plaintext writes to enumerated structured fields and guarded copies.
For scalar contacts, the trigger requires a well-formed blind index whenever
the encrypted value or its index is inserted or changed; unchanged legacy
plaintext rows remain compatible until conversion.
It follows the canonical merge revision `e352d353a901`, which preserves the
combined delivery-purpose check constraint, including member recovery and
contact-confirmation purposes. It is intentionally schema-only.
`backend/scripts/contact_data_migration.py`
provides the separate preview-first, batched conversion/verification path for
the migration's scalar inventory, recognized contact leaves in four JSON
snapshots, historical audit metadata, and known exact/truncated generated
email-name copies. The member recovery token table has no contact values to
convert; its delivery recipients are already part of the delivery-log scalar
inventory. Provider insights' click aggregates and UUID-only receipts likewise
contain no contact strings or contact indexes and are outside that conversion
inventory. `backend/scripts/contact_key_rotation.py` provides
preview-first key/index rotation. Conversion and cutover were not run as part
of this source audit, so the current database's actual ciphertext coverage is
not asserted here.

The converter and database guards cover structured fields and the named
generated-copy boundary; they do not discover arbitrary contacts embedded in
unstructured text. Historical database backups, WAL, SMTP systems, operator
reports/exports, application memory, and prior logs remain separate copies or
exposures. The reset-development backup contains whatever representation was
stored when it was made. The key lifecycle and operator sequence are described
in `docs/contact-encryption-operations.md`.

Blind indexes necessarily reveal equality/frequency for a given indexed
normalized value to a database reader with index access; keyed construction
prevents practical offline dictionary testing without the separate secret but
does not hide repeated identities. They do not support substring search.
Preserving current partial email/phone search therefore trades some database
search efficiency for streamed application-side decryption/filtering. The
current repository helpers scan the complete eligible result set to preserve
matching totals and pagination semantics.
