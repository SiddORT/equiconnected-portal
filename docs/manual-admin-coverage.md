# Admin manual coverage audit

This checklist maps the shipped admin workflows covered by
`frontend/src/pages/admin/manual/adminTopics.ts` to the implementation source
files audited. Routes sit inside the admin-role `AuthGuard`; “Administrators”
in the topics means an authenticated account with the admin role. Dashboard
and Analytics workflows are intentionally excluded from this assigned area.

## Coverage checklist

| Audited shipped feature | Manual topic ID | Primary implementation sources |
| --- | --- | --- |
| Admin navigation groups and profile-menu entry points | `admin-navigation` | `frontend/src/components/layout/AdminTopNav.tsx`; `frontend/src/app/Router.tsx` |
| Registered account search, role and verification filters, pagination, read-only detail fields | `admin-registrations` | `frontend/src/pages/admin/UsersPage.tsx` |
| Provider directory search, type/stability/emergency/status/publication filters, columns, pagination, review links, row actions | `provider-directory` | `frontend/src/pages/admin/ProvidersPage.tsx`; `frontend/src/pages/admin/ProvidersPage.module.css` |
| Provider detail overview badges and fields, doctor-only professional sections, services, specializations, locations, doctor trips, photos, and edit entry point | `provider-record-details` | `frontend/src/pages/admin/ProviderDetailPage.tsx`; `frontend/src/components/admin/DoctorProfessionalSections.tsx` |
| Provider creation wizard, common and type-specific fields, catalog selections, doctor information, services, contacts, location, initial state, optional access, save/photo-failure handling | `provider-create` | `frontend/src/pages/admin/ProviderNewPage.tsx`; `frontend/src/components/admin/ProviderForm.tsx`; `frontend/src/components/admin/ProviderWizard.tsx`; `frontend/src/components/admin/MultiEmailField.tsx`; `frontend/src/components/admin/MultiPhoneField.tsx`; `frontend/src/components/invite/InvitationProfileFields.tsx` |
| Existing provider edit wizard, full profile fields, edit validation, contact/relationship diffs, primary location and separate lifecycle/publication writes | `provider-edit` | `frontend/src/pages/admin/ProviderEditPage.tsx`; `frontend/src/components/admin/ProviderForm.tsx`; `frontend/src/components/admin/ProviderWizard.tsx` |
| Provider contact collections, multiple locations, specializations/languages, qualification create/edit/delete | `provider-profile-collections` | `frontend/src/pages/admin/ProviderDetailPage.tsx`; `frontend/src/components/admin/DoctorProfessionalSections.tsx`; `frontend/src/components/admin/ProviderForm.tsx`; `frontend/src/components/admin/MultiEmailField.tsx`; `frontend/src/components/admin/MultiPhoneField.tsx` |
| Provider Under review approval, Active/Inactive lifecycle, Published/Unpublished directory visibility and approval-email retry distinction | `provider-lifecycle-publication` | `frontend/src/pages/admin/ProvidersPage.tsx`; `frontend/src/pages/admin/ProviderDetailPage.tsx`; `frontend/src/components/admin/ProviderForm.tsx` |
| Provider portal eligibility/status, email choice, setup/reset, retry, cancellation of pending access, invitation-owned access boundary | `provider-portal-access-recovery` | `frontend/src/pages/admin/ProviderDetailPage.tsx`; `frontend/src/pages/admin/ProvidersPage.tsx`; `frontend/src/pages/admin/InvitationsPage.tsx`; `frontend/src/api/providers.ts` |
| Doctor visit periods, optional initial visit, future return and amendment, date/location rules | `provider-doctor-visits` | `frontend/src/pages/admin/ProviderDetailPage.tsx`; `frontend/src/components/admin/ProviderForm.tsx`; `frontend/src/api/providers.ts` |
| Admin visiting-provider month/day calendar and profile links | `provider-visiting-calendar` | `frontend/src/pages/VisitingProviderCalendarPage.tsx`; `frontend/src/components/dashboard/VisitingProviderCalendar.tsx`; `frontend/src/api/admin.ts` |
| Initial photo, staged multi-photo uploads, metadata, profile thumbnail, deletion, supported types and size limits | `provider-photo-management` | `frontend/src/components/admin/ProviderForm.tsx`; `frontend/src/pages/admin/ProviderDetailPage.tsx`; `frontend/src/api/providers.ts` |
| New provider applications, verification/review filters, detail fields, approval/rejection confirmation and draft-unpublished result | `provider-applications` | `frontend/src/pages/admin/ProviderApplicationsPage.tsx`; `frontend/src/api/admin.ts` |
| Existing-provider profile update queue, complete current/proposed profile compare, photo comparison, visit additions, rejection feedback and scope boundary | `provider-profile-updates` | `frontend/src/pages/admin/ProviderApplicationsPage.tsx`; `frontend/src/components/admin/ProviderPhotoComparison.tsx`; `frontend/src/api/admin.ts` |
| Invitation creation, doctor/non-doctor fields, state-dependent actions, date/type/search filters, details, session-only link, resend/cancel and setup access | `provider-invitations` | `frontend/src/pages/admin/InvitationsPage.tsx`; `frontend/src/components/admin/CreateInvitationDialog.tsx`; `frontend/src/api/invitations.ts` |
| Specialization list, create/edit/status, export and CSV template/upload/preview/import/result/error report | `specializations-catalog` | `frontend/src/pages/admin/SpecializationsPage.tsx`; `frontend/src/components/admin/SpecializationForm.tsx`; `frontend/src/components/admin/CsvImportDialog.tsx`; `frontend/src/api/specializations.ts` |
| Language search, code/name create/edit, active state and deactivation | `languages-catalog` | `frontend/src/pages/admin/LanguagesPage.tsx`; `frontend/src/components/admin/LanguageForm.tsx`; `frontend/src/api/languages.ts` |
| Review list filters/provider scope, detail, status actions, separate member/internal notes, deleted-record read-only boundary and optimistic version conflict refresh | `provider-reviews-moderation` | `frontend/src/pages/admin/ReviewsPage.tsx`; `frontend/src/api/reviews.ts` |
| Subscriber search/type/date filters, matching list and scoped CSV export | `admin-subscribers` | `frontend/src/pages/admin/SubscribersPage.tsx`; `frontend/src/api/admin.ts` |
| Contact enquiry search/type/date filters, read-only full detail and filter-preserving return path | `admin-contact-enquiries` | `frontend/src/pages/admin/ContactEnquiriesPage.tsx`; `frontend/src/api/admin.ts` |
| Feedback search/status/category, detail, member response/internal note, withdraw read-only boundary, history and optimistic version conflict refresh | `admin-platform-feedback` | `frontend/src/pages/admin/PlatformFeedbackPage.tsx`; `frontend/src/api/adminFeedback.ts` |
| Activity date filters, actor/action/details and pagination | `admin-activity-logs` | `frontend/src/pages/admin/ActivityLogsPage.tsx`; `frontend/src/api/admin.ts` |
| Read-only email log date filters, pagination, and email-purpose/status/failure interpretation | `admin-email-logs` | `frontend/src/pages/admin/EmailLogsPage.tsx`; `frontend/src/api/admin.ts` |
| Current server settings, timezone/date/time options, live preview, save/reset, refreshed shared time context | `admin-settings` | `frontend/src/pages/admin/SettingsPage.tsx`; `frontend/src/app/TimeSettingsContext.tsx`; `frontend/src/api/admin.ts` |

## Role and scope boundaries audited

- `frontend/src/app/Router.tsx` wraps every `/admin/*` workspace in
  `AuthGuard requiredRole="admin"` and the admin layout. Provider and member
  routes are separately guarded.
- Registration inspection, contact enquiries, activity logs, and email logs
  are read-only on their respective admin pages. Topics do not claim
  capabilities absent from those pages.
- Application decisions stage a draft unpublished listing. Profile-update
  decisions affect the submitted update only, not provider active status,
  publication, or account state.
- Provider active status and directory publication are separate controls.
  Portal setup/reset email handoff is not represented as guaranteed inbox
  delivery; canceling pending access invalidates the unactivated account/link.
- Review and feedback writes include expected-version handling. If another
  administrator changes a record concurrently, the UI refreshes the latest
  version for a fresh decision instead of intentionally overwriting stale
  content.
- Dashboard and Analytics are not covered by this file or `adminTopics`; the
  separate dashboard/analytics manual ownership remains unchanged.

## Delivered illustrations

- [x] All 25 admin topics have genuine captured illustrations, including the
  administrator sign-in/out topic added to this audit.
- [x] Provider wizard, collection, lifecycle/publication, access/recovery,
  photos, visiting trips/calendar, and decision outcomes are captured.
- [x] Catalog CSV preview/result, moderation, enquiries/feedback, logs and
  settings controls are captured with labelled sample data only.

See [the admin screenshot provenance manifest](manual-admin-screenshots.md)
for exact filenames, routes, states, and source files. The reader combines
`adminScreenshots.ts` through `manual/screenshots.ts`; images are deliberately
kept separate from task instructions so the same safe capture can illustrate
related concepts without duplicating asset files.