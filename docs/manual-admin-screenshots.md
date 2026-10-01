# Admin manual screenshots

## Provenance and safety

These assets are screenshots of the shipped admin React application, not mockups. The reproducible capture script is `scripts/capture-manual-admin.py`. It launches a dedicated headless Chromium process with a unique user-data directory and connects to the `type: page` CDP target on port 9241. The signed-in display identity and every `/api/v1` response are synthetic fixtures fulfilled in the browser by CDP Fetch interception before the request can reach an application server.

- Every captured screen has a visible `SAMPLE DATA — demonstration only` DOM overlay.
- All synthetic person/provider names begin with `Sample`; all email addresses use the reserved `.example.test` domain.
- Example messages, locations, profile data, application decisions and mutation outcomes are fictional and stay in this browser fixture.
- Email Logs uses read-only fixture responses; invitation and provider-access actions shown elsewhere in the admin UI are intercepted. No login credentials, outbound email, invitation/setup link, external account, database record or backend write was used. Screens do not contain raw setup or invitation URL tokens.
- The sample horse and stable images are the existing local `frontend/public/horse-panel.jpg` and `frontend/public/stable-panel.jpg`; no identifying person or facility text appears in either image. Upload examples use no real files.
- Unknown `/api/v1` requests return an explicit `599 manual_fixture_missing` fixture error rather than being continued to the backend. The script fails at completion if an unknown request or handler error was observed.

The full admin capture used isolated CDP page target `668E1E84B178956E7E10EE11FE0CD1A9` (212 browser-fixture API replies, including 63 intercepted non-GET requests). The Email Logs images below were refreshed separately with `--only-email-logs` using target `535222FA8646F0568F57F3923C3F959B` (12 fixture replies, including 4 browser-only writes). All fixture responses were fulfilled in the browser, not sent to the backend.

## Captured screens

| Manual topic ID | Asset | Route and visible state | Source |
|---|---|---|---|
| `admin-navigation` | `frontend/public/manual/admin-navigation.webp` | `/admin/users` — Top-level admin navigation shows Dashboard and Registrations with the synthetic admin session. | Shipped AdminTopNav; authenticated Sample Admin fixture, no dashboard capture. |
| `admin-navigation` | `frontend/public/manual/admin-navigation-directory.webp` | `` — Actual Directory Management dropdown shows provider, application, catalog, invitation, and review destinations. | Shipped AdminTopNav dropdown with no data beyond the visible Sample Admin identity. |
| `admin-navigation` | `frontend/public/manual/admin-navigation-enquiries.webp` | `` — Actual Enquiries dropdown lists subscribers, contact enquiries, and platform feedback. | Shipped AdminTopNav dropdown with synthetic navigation-only session. |
| `admin-navigation` | `frontend/public/manual/admin-navigation-profile.webp` | `` — Admin profile menu open with safe Sample Admin identity. Actual admin navigation menu opened in the running React app. | Shipped AdminLayout menu; the browser-only admin session is supplied by this script. |
| `admin-registrations` | `frontend/public/manual/admin-registrations.webp` | `/admin/users` — List shows two sample member registrations with different verification states. | Shipped UsersPage; all user data is synthetic and supplied through intercepted requests. |
| `admin-registrations` | `frontend/public/manual/admin-registrations-details.webp` | `` — Sample member detail dialog displays verification and registration information. | Shipped UsersPage detail dialog, opened for Sample Taylor Owner. |
| `provider-directory` | `frontend/public/manual/admin-provider-directory.webp` | `/admin/providers` — Directory shows sample clinic, doctor, and hospital with independent status/publication states. | Shipped ProvidersPage and existing filter controls; three synthetic providers. |
| `provider-directory` | `frontend/public/manual/provider-directory-filters.webp` | `` — Provider-type, services, status, and publication filters expanded. | Shipped ProvidersPage filter drawer with sample directory rows. |
| `provider-directory` | `frontend/public/manual/provider-directory-actions.webp` | `` — Actual provider row action menu shows state-dependent management controls for a Published sample clinic. | Shipped ProvidersPage row ActionMenu with synthetic provider state. |
| `provider-lifecycle-publication` | `frontend/public/manual/admin-provider-lifecycle.webp` | `` — Provider list keeps Active/Inactive status distinct from Published/Unpublished directory visibility. | Shipped ProvidersPage with independent status and publication badges; row action menu is fixture-only. |
| `provider-create` | `frontend/public/manual/provider-create.webp` | `/admin/providers/new` — First step of the actual create-provider wizard, with Sample data entered; no provider was submitted. | Shipped ProviderForm; the API catalogs are intercepted synthetic values. |
| `provider-create` | `frontend/public/manual/admin-provider-create-populated.webp` | `` — Doctor-specific form shows Sample identity, professional title, experience and biography; no provider is saved. | Shipped ProviderForm create flow using synthetic inputs and fixture catalogs. |
| `provider-create` | `frontend/public/manual/provider-create-review.webp` | `` — Review & create summary contains only synthetic Sample values; Create provider is not clicked. | Shipped ProviderForm review step with unsaved browser-only sample input. |
| `provider-edit` | `frontend/public/manual/provider-edit.webp` | `/admin/providers/sample-doctor/edit` — Actual edit wizard is pre-populated from the Sample Dr. Avery Field record; no fields are saved. | Shipped ProviderEditPage and ProviderForm with browser-intercepted profile data. |
| `provider-record-details` | `frontend/public/manual/provider-record-details.webp` | `/admin/providers/sample-doctor` — Top of Sample Dr. Avery Field profile shows overview and reset-access controls. No email is sent. | Shipped ProviderDetailPage; sample profile and access status returned by the isolated fixture. |
| `provider-portal-access-recovery` | `frontend/public/manual/provider-portal-access-recovery.webp` | `` — Doctor access panel shows Sample recipient, current reset status and the reset action. Nothing is sent. | Shipped ProviderDetailPage portal-access panel with a fixture-only active account state. |
| `provider-profile-collections` | `frontend/public/manual/provider-profile-collections.webp` | `` — Sample doctor qualifications and the add/edit/remove controls. | Shipped DoctorProfessionalSections with sample doctor qualification records. |
| `provider-profile-collections` | `frontend/public/manual/provider-profile-qualification-form.webp` | `` — Actual qualification form filled with unsaved Sample values; Add qualification is not submitted. | Shipped DoctorProfessionalSections inline form; form data is not sent. |
| `provider-profile-collections` | `frontend/public/manual/provider-profile-locations.webp` | `` — Location editor is populated with sample address values; the location is not saved. | Shipped ProviderDetailPage location form with browser-only fixture input. |
| `provider-doctor-visits` | `frontend/public/manual/admin-doctor-visits.webp` | `` — Visiting availability with previous and upcoming synthetic visit periods. | Shipped ProviderDetailPage Doctor trips section; dates and locations are fixtures. |
| `provider-doctor-visits` | `frontend/public/manual/provider-doctor-visits-add-form.webp` | `` — Visit-period form uses sample location/date values; Add return is not submitted. | Shipped ProviderDetailPage visit editor with synthetic values only. |
| `provider-visiting-calendar` | `frontend/public/manual/admin-provider-visiting-calendar.webp` | `/admin/visiting-providers` — Month calendar with a sample visit spanning the selected day and a provider-linked agenda card. | Shipped AdminVisitingProviderCalendarPage and VisitingProviderCalendar with fixture month data. |
| `provider-photo-management` | `frontend/public/manual/provider-photo-management.webp` | `` — Gallery displays safe local horse/stable sample imagery, alt text, profile-photo state, and management controls. | Shipped ProviderDetailPage Photos section; images are the two existing, inspected local assets, with synthetic metadata. |
| `provider-photo-management` | `frontend/public/manual/provider-photo-upload.webp` | `` — Actual upload panel documents supported photo formats, size limit, metadata fields and deferred upload. | Shipped ProviderDetailPage upload panel opened; no file is uploaded. |
| `provider-portal-access-recovery` | `frontend/public/manual/provider-portal-access-setup-preview.webp` | `` — Fixture explicitly reports a setup-request preview; no email was sent. | Shipped ProviderDetailPage result state after an intercepted fixture-only action. |
| `provider-applications` | `frontend/public/manual/admin-provider-applications.webp` | `/admin/provider-applications` — Pending sample application appears in the actual review queue. | Shipped ProviderApplicationsPage with one synthetic pending application. |
| `provider-applications` | `frontend/public/manual/admin-application-details.webp` | `` — Application detail shows sample professional, contact, service, consent and verification fields. | Shipped ProviderApplicationsPage application detail modal. |
| `provider-applications` | `frontend/public/manual/admin-application-approval-confirm.webp` | `` — Confirmation explains staged-draft result; all action requests are fixture-only. | Shipped ProviderApplicationsPage decision confirmation dialog. |
| `provider-applications` | `frontend/public/manual/admin-application-staged-result.webp` | `` — The UI shows the sample application as reviewed and identifies the staged listing as a draft; the fixture has no live record or email. | Shipped ProviderApplicationsPage result handling; POST fulfilled by the isolated browser fixture. |
| `provider-profile-updates` | `frontend/public/manual/admin-provider-updates.webp` | `/admin/provider-applications?tab=updates` — One pending sample profile update is available for comparison. | Shipped ProviderApplicationsPage Updates view with a synthetic pending change. |
| `provider-profile-updates` | `frontend/public/manual/admin-provider-update-actions.webp` | `` — The actual profile-update row menu exposes Compare profiles. | Shipped ProviderApplicationsPage row ActionMenu using a synthetic pending update. |
| `provider-profile-updates` | `frontend/public/manual/admin-provider-update-comparison.webp` | `` — Actual comparison shows current/proposed sample values and an added photo with safe fixture images. | Shipped ProviderApplicationsPage comparison modal; both profile and photo data are synthetic. |
| `provider-profile-updates` | `frontend/public/manual/admin-provider-update-confirm.webp` | `` — Sample update decision confirmation remains entirely in the fixture browser. | Shipped ProviderApplicationsPage profile-update confirmation dialog. |
| `provider-profile-updates` | `frontend/public/manual/admin-provider-update-result.webp` | `` — Fixture-only approved state appears in the real page; no live profile is changed. | Shipped ProviderApplicationsPage update-result state after intercepted browser-only decision. |
| `provider-invitations` | `frontend/public/manual/admin-invitations-statuses.webp` | `/admin/invitations` — Sample invitations show Pending, Accepted, Expired, Cancelled, and Completed states. | Shipped InvitationsPage; entries, emails and dates are sample fixtures; no raw link is included. |
| `provider-invitations` | `frontend/public/manual/admin-invitation-create.webp` | `` — Doctor invitation form is populated with Sample values; Send invitation is not clicked. | Shipped CreateInvitationDialog; no invitation is generated or email sent. |
| `specializations-catalog` | `frontend/public/manual/admin-specializations.webp` | `/admin/specializations` — Specializations table and catalog actions use safe Sample entries. | Shipped SpecializationsPage and browser-intercepted catalog response. |
| `specializations-catalog` | `frontend/public/manual/admin-specialization-csv-upload.webp` | `` — Actual CSV dialog shows template link, format, and size constraints before file selection. | Shipped CsvImportDialog; no file or template request leaves the browser. |
| `specializations-catalog` | `frontend/public/manual/admin-specialization-csv-preview.webp` | `` — CSV preview shows one valid, one duplicate and one invalid Sample row; Import is not clicked. | Shipped CsvImportDialog preview; its preview endpoint is intercepted and no data is saved. |
| `languages-catalog` | `frontend/public/manual/admin-languages.webp` | `/admin/languages` — Searchable language catalog shows fixture language names and codes. | Shipped LanguagesPage with synthetic language records. |
| `languages-catalog` | `frontend/public/manual/admin-language-form.webp` | `` — Actual language dialog displays name and code fields without saving a catalog record. | Shipped LanguageForm in LanguagesPage; no mutation is submitted. |
| `provider-reviews-moderation` | `frontend/public/manual/admin-reviews-moderation.webp` | `/admin/reviews` — Sample pending provider review appears in the queue. | Shipped ReviewsPage with synthetic member, comment and provider details. |
| `provider-reviews-moderation` | `frontend/public/manual/admin-review-details.webp` | `` — Sample comment, moderation history and actions appear in the real details view. | Shipped ReviewsPage detail interaction and fixture response. |
| `provider-reviews-moderation` | `frontend/public/manual/admin-review-publish-result.webp` | `` — Published state and synthetic moderation-history entry appear after an intercepted request. | Shipped ReviewsPage; POST response updates only browser fixture state. |
| `admin-subscribers` | `frontend/public/manual/admin-subscribers.webp` | `/admin/subscribers` — Sample subscriber records show synthetic emails, registration types and dates. | Shipped SubscribersPage with synthetic .example.test addresses. |
| `admin-contact-enquiries` | `frontend/public/manual/admin-contact-enquiries.webp` | `/admin/contact-enquiries` — Sample enquiry is visible in the inbox. | Shipped ContactEnquiriesPage; the contact message is explicitly synthetic. |
| `admin-contact-enquiries` | `frontend/public/manual/admin-contact-enquiry-detail.webp` | `` — Read-only sample message and sender details; no reply or outbound action is available. | Shipped ContactEnquiriesPage detail route with synthetic text and an intercepted detail read. |
| `admin-platform-feedback` | `frontend/public/manual/admin-private-feedback.webp` | `/admin/feedback` — One sample feedback entry with a private message. | Shipped PlatformFeedbackPage with synthetic .example.test identity and text. |
| `admin-platform-feedback` | `frontend/public/manual/admin-private-feedback-detail.webp` | `` — Synthetic feedback message, resolution state and notes; no public display or email. | Shipped PlatformFeedbackDetailPage using only intercepted sample data. |
| `admin-activity-logs` | `frontend/public/manual/admin-activity-logs.webp` | `/admin/activity-logs` — Synthetic Sample Admin events and reserved documentation IP addresses. | Shipped ActivityLogsPage; all records are synthetic (RFC 5737 documentation-only IP range). |
| `admin-activity-logs` | `frontend/public/manual/admin-activity-log-details.webp` | `` — Expanded activity entry shows the sample before/after review-status change. | Shipped ActivityLogsPage change disclosure with fixture-supplied before/after content. |
| `admin-email-logs` | `frontend/public/manual/admin-email-logs.webp` | `/admin/email-logs` — Read-only table shows synthetic Accepted by SMTP and Failed rows with date filters. | Shipped EmailLogsPage; sample delivery rows are browser-only fixtures and no message is sent. |
| `admin-email-logs` | `frontend/public/manual/admin-email-logs-date-range.webp` | `/admin/email-logs?filter_mode=range&date_from=2026-10-01&date_to=2026-10-01` — Read-only view shows the selected custom period and synthetic accepted and failed rows. | Shipped EmailLogsPage custom-range filters; results are browser-only sample fixtures. |
| `admin-settings` | `frontend/public/manual/admin-settings.webp` | `/admin/settings` — Actual settings fields show fixture timezone and formatting choices; nothing is saved. | Shipped SettingsPage with a static synthetic settings response. |
| `admin-sign-in-out` | `frontend/public/manual/admin-sign-in-out.webp` | `` — Signed-out admin login form contains a Sample .example.test address and an empty password field; no credentials are submitted. | Shipped LoginPage after intercepted logout; login remains idle and no password or auth request is sent. |

The screenshot mapping is exported as `adminScreenshots` from `frontend/src/pages/admin/manual/adminScreenshots.ts`. Only topic IDs with at least one genuine capture are included.

## Reproduction

Run from the repository root with the frontend already available at port 5000 and the normal `REPLIT_DEV_DOMAIN` environment variable set:

```sh
python scripts/capture-manual-admin.py
```

To refresh only the Email Logs illustrations without rewriting the full screenshot mapping or provenance manifest:

```sh
python scripts/capture-manual-admin.py --only-email-logs
```

The script uses only standard Python modules plus the existing `websockets` package and Chromium from PATH; `cwebp` is used when available to compress final PNG captures as WebP. It creates and removes its own Chromium profile and does not start or restart the application.
