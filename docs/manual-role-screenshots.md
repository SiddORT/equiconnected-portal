# Role and public-workflow screenshot provenance

These assets capture shipped EquiConnected UI from the already-running frontend.
The reproducible capture driver is `scripts/capture-manual-role.py`; the
topic-ID mapping is exported by
`frontend/src/pages/admin/manual/roleScreenshots.ts`.

## Capture provenance and safety

- The script connects to the configured running frontend using
  `REPLIT_DEV_DOMAIN`; it does not start or restart the app or backend.
- A dedicated headless Chromium instance uses CDP port `9242` and an isolated
  temporary profile. The script selects a CDP target with type `page`.
- Every `/api/v1/` request is intercepted before network continuation and
  answered from in-memory synthetic fixtures. Traffic writes, authentication,
  registration, invitations, profile changes, visits, feedback, reviews, and
  history are fixture-only. A route without a fixture receives an explicit
  `501 manual_fixture_missing` response; it is never passed through to the
  backend.
- The previous full role capture intercepted 281 application API requests,
  found no unknown routes, and refreshed the 59 then-mapped images.
- The latest provider-only refresh intercepted 52 application API requests,
  found no unknown routes, refreshed signed-in provider-navigation captures,
  and added three Insights images. The manual mapping now contains 62 images.
  Static React, CSS, and local public assets continued to load from the running
  frontend.
- Messaging availability, inbox, unread-count, start, thread, reply, and read
  receipt requests use in-memory response shapes matching
  `frontend/src/api/messages.ts`. The transcript and contact snapshot contain
  labelled synthetic values only; no message request or email is sent to a
  backend or SMTP service.
- Provider Insights requests to `/api/v1/provider/portal/insights` use response
  shapes matching `frontend/src/types/providerInsights.ts` and
  `frontend/src/api/providerInsights.ts`. Aggregate totals, trends, source
  coverage, custom date-filter results, and refresh timestamps are synthetic
  fixture values, not provider or member activity.
- `python3 scripts/capture-manual-role.py --provider-refresh` refreshes only
  signed-in provider navigation, account, Insights, and message captures. It
  avoids rerunning unchanged public and member workflows after provider
  navigation changes.
- Each captured viewport includes a browser-DOM
  “SAMPLE DATA — demonstration only” badge and a workflow caption. The capture
  driver saves viewport screenshots as WebP at quality 82. The provider photo
  upload uses only the shipped local `/horse-panel.jpg` image.
- Passwords, emails, and invitation / verification links used during capture
  are synthetic fixture values. Token-bearing routes below are represented
  without token values; the browser viewport does not expose browser chrome.

## Asset manifest

| Asset | Route and visible state | Shipped UI source |
| --- | --- | --- |
| `/manual/member-create-account.webp` | `/signup` — clean member account form and role choices | `frontend/src/pages/SignupPage.tsx`; `frontend/src/components/ui/PhoneInput.tsx`; `frontend/src/components/ui/LocationPicker.tsx` |
| `/manual/member-create-account-verification.webp` | `/signup` — sample account saved; verification handoff | `frontend/src/pages/SignupPage.tsx`; `frontend/src/api/auth.ts` |
| `/manual/member-create-account-verified.webp` | `/verify-email?token=<synthetic>` — verified member confirmation | `frontend/src/pages/VerifyEmailPage.tsx`; `frontend/src/api/auth.ts` |
| `/manual/member-sign-in.webp` | protected `/providers` redirects to `/login` — member sign-in form | `frontend/src/features/member/MemberAuthGuard.tsx`; `frontend/src/pages/MemberLoginPage.tsx` |
| `/manual/member-sign-in-success.webp` | `/providers` — signed-in member directory | `frontend/src/features/member/MemberAuthGuard.tsx`; `frontend/src/pages/ProviderDirectoryPage.tsx` |
| `/manual/provider-public-registration.webp` | `/provider/signup` — provider type and registration fields | `frontend/src/pages/ProviderSignupPage.tsx`; `frontend/src/pages/SignupMultiSelect.tsx`; `frontend/src/components/ui/LocationPicker.tsx` |
| `/manual/provider-public-registration-verification.webp` | `/provider/signup` — sample application saved; verification handoff | `frontend/src/pages/ProviderSignupPage.tsx`; `frontend/src/api/auth.ts` |
| `/manual/provider-public-registration-verified.webp` | `/verify-email?token=<synthetic>` — provider email verified | `frontend/src/pages/VerifyEmailPage.tsx`; `frontend/src/api/auth.ts` |
| `/manual/provider-password-access-setup.webp` | `/provider/setup-password?token=<synthetic>` — initial password form | `frontend/src/pages/ProviderPasswordSetupPage.tsx`; `frontend/src/api/auth.ts` |
| `/manual/provider-password-access-setup-complete.webp` | `/provider/setup-password?token=<synthetic>` — setup success | `frontend/src/pages/ProviderPasswordSetupPage.tsx`; `frontend/src/api/auth.ts` |
| `/manual/provider-password-access-recovery.webp` | `/provider/reset-password?token=<synthetic>` — recovery form | `frontend/src/pages/ProviderPasswordSetupPage.tsx`; `frontend/src/api/auth.ts` |
| `/manual/provider-password-access-recovery-complete.webp` | `/provider/reset-password?token=<synthetic>` — recovery success | `frontend/src/pages/ProviderPasswordSetupPage.tsx`; `frontend/src/api/auth.ts` |
| `/manual/troubleshoot-provider-portal-access.webp` | `/provider/account` redirects unauthenticated visitor to provider sign-in | `frontend/src/features/provider/ProviderAuthGuard.tsx`; `frontend/src/pages/ProviderLoginPage.tsx` |
| `/manual/provider-sign-in.webp` | `/provider/login` — separate provider sign-in form | `frontend/src/pages/ProviderLoginPage.tsx` |
| `/manual/provider-sign-in-success.webp` | `/provider/account` — signed-in provider workspace with Account, Insights, and Messages navigation | `frontend/src/features/provider/ProviderAuthGuard.tsx`; `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-invitation-draft-submit-profile.webp` | `/provider/invite/<synthetic-token>` — prefilled clinic invitation profile | `frontend/src/pages/InvitationPage.tsx`; `frontend/src/components/invite/InvitationProviderForm.tsx`; `frontend/src/components/admin/ProviderForm.tsx` |
| `/manual/provider-invitation-draft-submit-draft.webp` | `/provider/invite/<synthetic-token>` — saved-draft confirmation | `frontend/src/components/invite/InvitationProviderForm.tsx`; `frontend/src/components/admin/ProviderForm.tsx` |
| `/manual/provider-invitation-draft-submit.webp` | `/provider/invite/success` — submission received | `frontend/src/pages/SubmissionSuccessPage.tsx`; `frontend/src/components/invite/InvitationProviderForm.tsx` |
| `/manual/provider-profile-edit.webp` | `/provider/account` — Basic details tab with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/components/provider/ProviderProfileCollections.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-profile-edit-professional.webp` | `/provider/account` — Professional details and qualifications with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/components/provider/ProviderProfileCollections.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-profile-edit-services.webp` | `/provider/account` — Services and care options with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/components/provider/ProviderProfileCollections.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-locations-contact.webp` | `/provider/account` — Contact & location tab with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/components/provider/ProviderProfileCollections.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-profile-photos.webp` | `/provider/account` — Photos tab and existing safe sample imagery with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/components/provider/ProviderProfileCollections.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-profile-photos-uploaded.webp` | `/provider/account` — photo upload complete, not yet saved, with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/components/provider/ProviderProfileCollections.tsx`; `frontend/src/api/providers.ts`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-profile-edit-pending-review.webp` | `/provider/account` — profile proposal awaiting review with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/api/providers.ts`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-profile-edit-revision-requested.webp` | `/provider/account` — sample declined-update feedback with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/api/providers.ts`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-profile-edit-discarded.webp` | `/provider/account` — draft discarded and approved profile reloaded with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/api/providers.ts`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-read-member-feedback.webp` | `/provider/account` — read-only member-feedback drawer with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/components/reviews/ReviewCard.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-visiting-schedule.webp` | `/provider/account` — recorded history grouped previous/current/upcoming with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/api/providers.ts`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-visiting-schedule-proposed-trip.webp` | `/provider/account` — proposed-visit form with current provider navigation | `frontend/src/pages/ProviderAccountPage.tsx`; `frontend/src/api/providers.ts`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/provider-insights-overview.webp` | `/provider/insights` — populated aggregate cards, coverage notes, trends, contact breakdown, and profile snapshot | `frontend/src/pages/ProviderInsightsPage.tsx`; `frontend/src/components/analytics/AnalyticsChart.tsx`; `frontend/src/api/providerInsights.ts`; `frontend/src/types/providerInsights.ts` |
| `/manual/provider-insights-filtered.webp` | `/provider/insights` — applied custom seven-day range with both trend data tables | `frontend/src/pages/ProviderInsightsPage.tsx`; `frontend/src/components/analytics/AnalyticsChart.tsx`; `frontend/src/api/providerInsights.ts`; `frontend/src/types/providerInsights.ts` |
| `/manual/provider-insights-refreshed.webp` | `/provider/insights` — refreshed custom-range report with a new fixture timestamp | `frontend/src/pages/ProviderInsightsPage.tsx`; `frontend/src/api/providerInsights.ts`; `frontend/src/types/providerInsights.ts` |
| `/manual/member-provider-directory.webp` | `/providers` — sample directory results | `frontend/src/pages/ProviderDirectoryPage.tsx`; `frontend/src/components/member/SaveProviderButton.tsx` |
| `/manual/member-provider-directory-filters.webp` | `/providers` — advanced filters expanded | `frontend/src/pages/ProviderDirectoryPage.tsx` |
| `/manual/member-provider-directory-location.webp` | `/providers` — synthetic browser location and distance results | `frontend/src/pages/ProviderDirectoryPage.tsx`; `frontend/src/api/providers.ts` |
| `/manual/member-save-providers.webp` | `/providers` — sample provider saved on its card | `frontend/src/pages/ProviderDirectoryPage.tsx`; `frontend/src/components/member/SaveProviderButton.tsx` |
| `/manual/member-save-providers-list.webp` | `/providers?saved=true` — saved-provider list | `frontend/src/pages/ProviderDirectoryPage.tsx`; `frontend/src/components/layout/MemberTopNav.tsx` |
| `/manual/member-provider-profile-contact-photos.webp` | `/providers/sample-clinic-id` — member-visible provider overview with enabled Message provider action | `frontend/src/pages/MemberProviderDetailPage.tsx`; `frontend/src/api/messages.ts`; `frontend/src/components/reviews/ReviewCard.tsx` |
| `/manual/member-provider-profile-contact-photos-gallery.webp` | `/providers/sample-clinic-id` — open provider photo gallery | `frontend/src/pages/MemberProviderDetailPage.tsx` |
| `/manual/member-provider-profile-contact-photos-locations.webp` | `/providers/sample-clinic-id` — locations and recorded visits | `frontend/src/pages/MemberProviderDetailPage.tsx` |
| `/manual/member-private-messages-inbox.webp` | `/member/messages` — member inbox with a seeded synthetic conversation and unread state | `frontend/src/pages/PrivateMessagesPage.tsx`; `frontend/src/components/layout/MemberTopNav.tsx`; `frontend/src/components/messaging/useMessageUnreadCount.ts`; `frontend/src/api/messages.ts` |
| `/manual/member-private-messages-start.webp` | `/member/messages?provider_id=sample-clinic-id` — contact preview, consent, and initial composer | `frontend/src/pages/MemberProviderDetailPage.tsx`; `frontend/src/pages/PrivateMessagesPage.tsx`; `frontend/src/api/messages.ts` |
| `/manual/member-private-messages-started.webp` | `/member/messages/sample-started-conversation-1` — labelled sample initial message in the new thread | `frontend/src/pages/PrivateMessagesPage.tsx`; `frontend/src/api/messages.ts` |
| `/manual/member-private-messages-thread.webp` | `/member/messages/sample-private-conversation` — labelled member/provider transcript and reply composer | `frontend/src/pages/PrivateMessagesPage.tsx`; `frontend/src/api/messages.ts` |
| `/manual/member-private-messages-replied.webp` | `/member/messages/sample-private-conversation` — sample member reply appended to the thread | `frontend/src/pages/PrivateMessagesPage.tsx`; `frontend/src/api/messages.ts` |
| `/manual/provider-private-messages-inbox.webp` | `/provider/messages` — provider inbox with a seeded synthetic member conversation | `frontend/src/pages/PrivateMessagesPage.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx`; `frontend/src/components/messaging/useMessageUnreadCount.ts`; `frontend/src/api/messages.ts` |
| `/manual/provider-private-messages-thread.webp` | `/provider/messages/sample-private-conversation` — labelled transcript and synthetic member contact snapshot | `frontend/src/pages/PrivateMessagesPage.tsx`; `frontend/src/components/layout/ProviderTopNav.tsx`; `frontend/src/api/messages.ts` |
| `/manual/provider-private-messages-replied.webp` | `/provider/messages/sample-private-conversation` — sample provider reply appended to the thread with current provider navigation | `frontend/src/pages/PrivateMessagesPage.tsx`; `frontend/src/api/messages.ts`; `frontend/src/components/layout/ProviderTopNav.tsx` |
| `/manual/member-provider-reviews.webp` | `/providers/sample-clinic-id` — review form | `frontend/src/pages/MemberProviderDetailPage.tsx` |
| `/manual/member-provider-reviews-pending.webp` | `/providers/sample-clinic-id` — submitted review pending moderation | `frontend/src/pages/MemberProviderDetailPage.tsx`; `frontend/src/api/providers.ts` |
| `/manual/member-visiting-calendar.webp` | `/providers/visiting-calendar` — selected date and visit agenda | `frontend/src/pages/VisitingProviderCalendarPage.tsx`; `frontend/src/components/dashboard/VisitingProviderCalendar.tsx`; `frontend/src/api/providers.ts` |
| `/manual/member-personal-profile.webp` | `/profile` — personal profile readiness | `frontend/src/pages/ProfilePage.tsx`; `frontend/src/features/member/profileCompletion.ts` |
| `/manual/member-stable-profile.webp` | `/profile` — role-gated Stable Manager section | `frontend/src/pages/ProfilePage.tsx`; `frontend/src/features/member/MemberAddressFields.tsx` |
| `/manual/member-horse-profiles.webp` | `/profile` — Horse Owner records | `frontend/src/pages/ProfilePage.tsx`; `frontend/src/api/profile.ts` |
| `/manual/member-browsing-history.webp` | `/history` — sample search and provider entries | `frontend/src/pages/MemberHistoryPage.tsx`; `frontend/src/api/memberFeedback.ts` |
| `/manual/member-reviews-feedback-management.webp` | `/my-reviews` — rejected review and moderator feedback | `frontend/src/pages/MemberReviewsPage.tsx`; `frontend/src/api/memberFeedback.ts` |
| `/manual/member-provider-reviews-edit.webp` | `/my-reviews` — edit eligible review | `frontend/src/pages/MemberReviewsPage.tsx`; `frontend/src/api/memberFeedback.ts` |
| `/manual/member-provider-reviews-resubmitted.webp` | `/my-reviews` — edited review returned to moderation | `frontend/src/pages/MemberReviewsPage.tsx`; `frontend/src/api/memberFeedback.ts` |
| `/manual/member-reviews-feedback-management-feedback.webp` | `/my-reviews` — System feedback list and sample status | `frontend/src/pages/MemberReviewsPage.tsx`; `frontend/src/api/memberFeedback.ts` |
| `/manual/member-private-feedback.webp` | `/my-reviews` — open private-feedback composer and privacy notice | `frontend/src/components/member/FeedbackModal.tsx`; `frontend/src/pages/MemberReviewsPage.tsx` |
| `/manual/member-private-feedback-submitted.webp` | `/my-reviews` — private feedback submission confirmation | `frontend/src/components/member/FeedbackModal.tsx`; `frontend/src/api/memberFeedback.ts` |

The route parameters named `<synthetic-token>` in this manifest are isolated
fixture values, not live invitation or password URLs.

The public homepage, contact, and updates-subscription topics currently have no
image entries: no corresponding capture was delivered, so no placeholder image
references were added.