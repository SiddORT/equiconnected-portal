export const roleScreenshots = {
  'member-create-account': [
    {
      src: '/manual/member-create-account.webp',
      alt: 'Member account creation page with name, email, mobile, location, role, and password fields.',
      caption: 'Registration form: select a member role and complete the account details before email verification.',
    },
    {
      src: '/manual/member-create-account-verification.webp',
      alt: 'Sample member signup confirmation showing the email-verification handoff.',
      caption: 'Verification handoff: the sample signup confirms the next step without sending email.',
    },
    {
      src: '/manual/member-create-account-verified.webp',
      alt: 'Member email verification success state with a sign-in next step.',
      caption: 'Verification result: the sample link confirms the member email and continues to sign-in.',
    },
  ],
  'provider-public-registration': [
    {
      src: '/manual/provider-public-registration.webp',
      alt: 'Provider signup form showing practice type and professional, contact, and service-location fields.',
      caption: 'Provider registration: applicants enter practice details, specialties, location, and portal credentials before review.',
    },
    {
      src: '/manual/provider-public-registration-verification.webp',
      alt: 'Provider application confirmation showing the email-verification handoff.',
      caption: 'Verification handoff: the sample application is saved for verification; no email is sent.',
    },
    {
      src: '/manual/provider-public-registration-verified.webp',
      alt: 'Provider email verification success state with a sign-in next step.',
      caption: 'Verification result: confirming an email does not itself publish a provider listing or grant portal access.',
    },
  ],
  'provider-invitation-draft-submit': [
    {
      src: '/manual/provider-invitation-draft-submit-profile.webp',
      alt: 'Prefilled sample clinic invitation form with provider identity, contact, language, and specialization fields.',
      caption: 'Invitation profile: review the sample details and complete the remaining fields before saving or submitting.',
    },
    {
      src: '/manual/provider-invitation-draft-submit-draft.webp',
      alt: 'Provider invitation form displaying the Draft saved confirmation.',
      caption: 'Draft result: the sample draft can be resumed with the same invitation; portal passwords are entered again at final submission.',
    },
    {
      src: '/manual/provider-invitation-draft-submit.webp',
      alt: 'Shipped invitation submission confirmation page stating the profile is under administrator review.',
      caption: 'Submission result: the sample profile enters administrator review; no account or email is created.',
    },
  ],
  'provider-password-access': [
    {
      src: '/manual/provider-password-access-setup.webp',
      alt: 'Provider portal initial password setup form with password and confirmation inputs.',
      caption: 'Password setup: enter and confirm a password using a synthetic one-time setup route.',
    },
    {
      src: '/manual/provider-password-access-setup-complete.webp',
      alt: 'Provider password setup success state with a route to provider sign-in.',
      caption: 'Setup result: the sample flow displays the shipped completion state.',
    },
    {
      src: '/manual/provider-password-access-recovery.webp',
      alt: 'Provider password recovery form with password and confirmation inputs.',
      caption: 'Recovery form: a provider uses an administrator-issued reset link; there is no self-service reset request.',
    },
    {
      src: '/manual/provider-password-access-recovery-complete.webp',
      alt: 'Provider password recovery success state.',
      caption: 'Recovery result: the sample reset flow confirms completion and returns to provider sign-in.',
    },
  ],
  'provider-sign-in': [
    {
      src: '/manual/provider-sign-in.webp',
      alt: 'Dedicated provider portal sign-in form.',
      caption: 'Provider sign-in: approved account holders use the provider portal rather than member sign-in.',
    },
    {
      src: '/manual/provider-sign-in-success.webp',
      alt: 'Signed-in provider workspace showing the submitted profile and editable basic details.',
      caption: 'Sign-in result: the sample provider session opens the provider profile workspace.',
    },
  ],
  'provider-profile-edit': [
    {
      src: '/manual/provider-profile-edit.webp',
      alt: 'Provider workspace Basic details panel with the sample clinic profile.',
      caption: 'Basic details: keep the member-facing profile identity current.',
    },
    {
      src: '/manual/provider-profile-edit-professional.webp',
      alt: 'Provider workspace Professional details tab with sample qualifications.',
      caption: 'Professional details: maintain experience and credentials in their own profile section.',
    },
    {
      src: '/manual/provider-profile-edit-services.webp',
      alt: 'Provider workspace Services tab with sample specialty and visit controls.',
      caption: 'Services: review the specialty, stable-visit, and emergency service controls.',
    },
    {
      src: '/manual/provider-profile-edit-pending-review.webp',
      alt: 'Provider profile displaying a notice that submitted changes are awaiting review.',
      caption: 'Pending result: published-profile changes are held for administrator review while members continue to see the approved version.',
    },
    {
      src: '/manual/provider-profile-edit-revision-requested.webp',
      alt: 'Provider profile displaying sample revision feedback after a declined update.',
      caption: 'Revision result: sample reviewer feedback is shown before the provider revises the proposal.',
    },
    {
      src: '/manual/provider-profile-edit-discarded.webp',
      alt: 'Provider profile displaying confirmation that the draft was discarded and the approved listing reloaded.',
      caption: 'Discard result: the sample proposal is cleared and the approved profile is restored.',
    },
  ],
  'provider-locations-contact': [
    {
      src: '/manual/provider-locations-contact.webp',
      alt: 'Provider contact and location section with sample business locations and primary contact selections.',
      caption: 'Locations and contacts: maintain business entries and identify which location and contact are primary.',
    },
  ],
  'provider-profile-photos': [
    {
      src: '/manual/provider-profile-photos.webp',
      alt: 'Provider Photos tab showing existing sample images and image metadata controls.',
      caption: 'Photo collection: review alt text, captions, thumbnail selection, and removal controls.',
    },
    {
      src: '/manual/provider-profile-photos-uploaded.webp',
      alt: 'Provider Photos tab displaying the Uploaded, not yet saved notice after a sample horse photo upload.',
      caption: 'Upload result: uploading is separate from saving the profile; published-photo changes await administrator review.',
    },
  ],
  'provider-visiting-schedule': [
    {
      src: '/manual/provider-visiting-schedule.webp',
      alt: 'Provider Visits tab grouping sample trips as previous, current, and upcoming, with proposed visits below.',
      caption: 'Visit history: recorded periods are read-only and distinct from proposed trips.',
    },
    {
      src: '/manual/provider-visiting-schedule-proposed-trip.webp',
      alt: 'Provider Visits tab showing the sample proposed-visit entry form.',
      caption: 'Propose a trip: enter visit dates and location details before saving the profile proposal.',
    },
  ],
  'provider-read-member-feedback': [
    {
      src: '/manual/provider-read-member-feedback.webp',
      alt: 'Provider workspace member-feedback drawer with sample rating summary and published review.',
      caption: 'Member feedback: the provider can read member-visible ratings and comments; the view is read-only.',
    },
  ],
  'member-sign-in': [
    {
      src: '/manual/member-sign-in.webp',
      alt: 'Member sign-in page with email and password fields.',
      caption: 'Member sign-in: verified members use the member route, separate from provider sign-in.',
    },
    {
      src: '/manual/member-sign-in-success.webp',
      alt: 'Member directory after a successful sample sign-in.',
      caption: 'Sign-in result: the sample member session opens the protected provider directory.',
    },
  ],
  'member-personal-profile': [
    {
      src: '/manual/member-personal-profile.webp',
      alt: 'Member profile readiness summary with personal contact and location sections.',
      caption: 'Personal profile: review readiness and the member’s contact and location details.',
    },
  ],
  'member-stable-profile': [
    {
      src: '/manual/member-stable-profile.webp',
      alt: 'Stable Manager profile section with sample stable location and contact fields.',
      caption: 'Stable profile: role-gated stable identity and contact information are maintained separately.',
    },
  ],
  'member-horse-profiles': [
    {
      src: '/manual/member-horse-profiles.webp',
      alt: 'Horse Owner profile section showing a sample horse record and its management controls.',
      caption: 'Horse records: manage individual horse profiles and their optional details.',
    },
  ],
  'member-provider-directory': [
    {
      src: '/manual/member-provider-directory.webp',
      alt: 'Member provider directory with filter controls and sample clinic, visiting doctor, and hospital results.',
      caption: 'Directory results: compare sample provider types, specialties, visit options, and saved status.',
    },
    {
      src: '/manual/member-provider-directory-filters.webp',
      alt: 'Member directory with optional provider, rating, emergency, and location filters expanded.',
      caption: 'Additional filters: expand optional controls only when you need them.',
    },
    {
      src: '/manual/member-provider-directory-location.webp',
      alt: 'Member directory showing synthetic distance results after a location option was selected.',
      caption: 'Location result: distance uses the browser’s synthetic sample location and is enabled only after an explicit choice.',
    },
  ],
  'member-save-providers': [
    {
      src: '/manual/member-save-providers.webp',
      alt: 'Member provider directory card showing a provider saved to the shortlist.',
      caption: 'Save a provider: the sample saved status updates on the directory card.',
    },
    {
      src: '/manual/member-save-providers-list.webp',
      alt: 'Saved providers view showing the sample clinic in the member’s shortlist.',
      caption: 'Saved list: revisit or remove providers from the member-only shortlist.',
    },
  ],
  'member-provider-profile-contact-photos': [
    {
      src: '/manual/member-provider-profile-contact-photos.webp',
      alt: 'Member-visible sample provider profile overview with specialties, rating, direct contact, and an enabled Message provider control.',
      caption: 'Provider profile: Message provider opens the private-message start form after availability is confirmed.',
    },
    {
      src: '/manual/member-provider-profile-contact-photos-gallery.webp',
      alt: 'Actual provider photo gallery displaying the shipped sample horse image and its caption.',
      caption: 'Photo gallery: view provider-shared images and close the gallery when finished.',
    },
    {
      src: '/manual/member-provider-profile-contact-photos-locations.webp',
      alt: 'Provider profile locations and scheduled visiting periods for the sample clinic.',
      caption: 'Locations and visits: these sample periods are informational, not appointment slots.',
    },
  ],
  'member-private-messages': [
    {
      src: '/manual/member-provider-profile-contact-photos.webp',
      alt: 'Sample provider detail with the Message provider action enabled.',
      caption: 'Entry point: select Message provider on an available listing to open the consent and contact-preview step.',
    },
    {
      src: '/manual/member-private-messages-inbox.webp',
      alt: 'Member Messages inbox with a populated synthetic provider conversation and unread indicator.',
      caption: 'Inbox: the member can select a provider conversation to read and reply.',
    },
    {
      src: '/manual/member-private-messages-start.webp',
      alt: 'Start-conversation form displaying labelled sample contact details, sharing consent, and a first-message field.',
      caption: 'Start: review the contact details shared with the linked provider account, agree to share them, and compose a plain-text message.',
    },
    {
      src: '/manual/member-private-messages-started.webp',
      alt: 'New member conversation showing the labelled synthetic first message in the thread.',
      caption: 'Start outcome: the sample first message appears in the member thread; the capture never contacts a real provider or email service.',
    },
    {
      src: '/manual/member-private-messages-thread.webp',
      alt: 'Member conversation displaying labelled synthetic messages from the member and provider with a reply composer.',
      caption: 'Thread: read the private exchange and compose a response.',
    },
    {
      src: '/manual/member-private-messages-replied.webp',
      alt: 'Member conversation showing the labelled synthetic reply appended to the thread.',
      caption: 'Reply outcome: the fixture adds the sample reply to the thread without sending email.',
    },
  ],
  'member-visiting-calendar': [
    {
      src: '/manual/member-visiting-calendar.webp',
      alt: 'Member visiting-provider calendar with a selected date and sample visit in the day agenda.',
      caption: 'Calendar agenda: select a date to review its sample visiting period and open the provider profile.',
    },
  ],
  'member-provider-reviews': [
    {
      src: '/manual/member-provider-reviews.webp',
      alt: 'Provider profile review form with rating and comment controls.',
      caption: 'Write a review: choose a rating and add an optional comment for moderation.',
    },
    {
      src: '/manual/member-provider-reviews-pending.webp',
      alt: 'Provider profile showing the sample member review awaiting publication.',
      caption: 'Review result: new text is pending moderation and is not yet visible to other members.',
    },
    {
      src: '/manual/member-provider-reviews-edit.webp',
      alt: 'Member review editor displaying a rejected sample review and moderation reminder.',
      caption: 'Edit a review: update an eligible review before resubmitting it for moderation.',
    },
    {
      src: '/manual/member-provider-reviews-resubmitted.webp',
      alt: 'Member review list showing the edited review returned to moderation.',
      caption: 'Revision result: a saved edit returns the review to pending moderation.',
    },
  ],
  'member-private-feedback': [
    {
      src: '/manual/member-private-feedback.webp',
      alt: 'Private feedback composer with category, optional rating, subject, and message controls.',
      caption: 'Private feedback: choose a category and write a note visible only to the member and EquiConnected team.',
    },
    {
      src: '/manual/member-private-feedback-submitted.webp',
      alt: 'Private feedback submission confirmation stating the note is private to the member and EquiConnected team.',
      caption: 'Submission result: the shipped confirmation appears after a sample-only feedback write.',
    },
  ],
  'provider-private-messages': [
    {
      src: '/manual/provider-private-messages-inbox.webp',
      alt: 'Provider Messages navigation and inbox with a populated labelled synthetic member conversation.',
      caption: 'Inbox: the provider account can select a member conversation and see its unread status.',
    },
    {
      src: '/manual/provider-private-messages-thread.webp',
      alt: 'Provider thread with labelled sample messages, the member contact snapshot, and reply composer.',
      caption: 'Thread: the linked provider account can read the exchange and view the contact details the member consented to share.',
    },
    {
      src: '/manual/provider-private-messages-replied.webp',
      alt: 'Provider thread showing the labelled synthetic provider reply appended to the conversation.',
      caption: 'Reply outcome: the sample provider response appears in the thread; no email is sent.',
    },
  ],
  'provider-insights': [
    {
      src: '/manual/provider-insights-overview.webp',
      alt: 'Provider Insights dashboard with synthetic profile visits, contact clicks, conversations, coverage notes, trends, contact breakdown, and current profile totals.',
      caption: 'Overview: review period activity alongside collection coverage and the independent current profile snapshot.',
    },
    {
      src: '/manual/provider-insights-filtered.webp',
      alt: 'Provider Insights custom date controls applied to a sample seven-day range, with populated trend data tables.',
      caption: 'Filter result: applying a custom range returns matching aggregate cards and daily tables; the data is labelled synthetic.',
    },
    {
      src: '/manual/provider-insights-refreshed.webp',
      alt: 'Provider Insights after Refresh with the updated sample reporting timestamp and filtered aggregates.',
      caption: 'Refresh result: a new fixture response updates the displayed timestamp without calling a live analytics API.',
    },
  ],
  'member-reviews-feedback-management': [
    {
      src: '/manual/member-reviews-feedback-management.webp',
      alt: 'My Reviews & Feedback showing a rejected provider review and its moderator note.',
      caption: 'Review management: a member can read feedback and edit or remove an eligible review.',
    },
    {
      src: '/manual/member-reviews-feedback-management-feedback.webp',
      alt: 'System feedback list showing the sample private note and its In Review status.',
      caption: 'System feedback: track private feedback status separately from provider reviews.',
    },
  ],
  'member-browsing-history': [
    {
      src: '/manual/member-browsing-history.webp',
      alt: 'Member browsing history list with a sample provider search and provider profile visit.',
      caption: 'Browsing history: restore the sample search or reopen an available provider profile.',
    },
  ],
  'troubleshoot-email-verification': [
    {
      src: '/manual/member-create-account-verification.webp',
      alt: 'Member signup confirmation showing the email-verification handoff.',
      caption: 'Verification handoff: the sample signup confirms the next step without sending email.',
    },
    {
      src: '/manual/member-create-account-verified.webp',
      alt: 'Member email verification success state with a sign-in next step.',
      caption: 'Member verification result: the synthetic link resolves without exposing its token.',
    },
    {
      src: '/manual/provider-public-registration-verification.webp',
      alt: 'Provider application confirmation showing the email-verification handoff.',
      caption: 'Provider verification handoff: the sample application is saved for verification; no email is sent.',
    },
    {
      src: '/manual/provider-public-registration-verified.webp',
      alt: 'Provider email verification success state with a sign-in next step.',
      caption: 'Provider verification result: administrator review still follows email verification.',
    },
  ],
  'troubleshoot-provider-portal-access': [
    {
      src: '/manual/troubleshoot-provider-portal-access.webp',
      alt: 'Provider workspace route returning an unauthenticated visitor to provider sign-in.',
      caption: 'Access guard: provider workspace access is separate from member sign-in.',
    },
    {
      src: '/manual/provider-password-access-setup.webp',
      alt: 'Provider portal initial password setup form.',
      caption: 'Setup link: use the authorized provider password-setup route.',
    },
    {
      src: '/manual/provider-password-access-recovery.webp',
      alt: 'Provider password recovery form.',
      caption: 'Recovery link: an administrator issues the provider reset email.',
    },
  ],
  'troubleshoot-provider-profile-review': [
    {
      src: '/manual/provider-profile-photos-uploaded.webp',
      alt: 'Provider Photos tab displaying the Uploaded, not yet saved notice.',
      caption: 'Upload status: uploaded photos are not part of the provider profile until Save profile is selected.',
    },
    {
      src: '/manual/provider-profile-edit-pending-review.webp',
      alt: 'Provider profile displaying a notice that submitted changes are awaiting review.',
      caption: 'Pending status: members continue to see the approved profile while changes are reviewed.',
    },
    {
      src: '/manual/provider-profile-edit-revision-requested.webp',
      alt: 'Provider profile displaying sample revision feedback after a declined update.',
      caption: 'Revision status: use the sample feedback to understand the revise-and-resubmit step.',
    },
  ],
  'troubleshoot-directory-location': [
    {
      src: '/manual/member-provider-directory-filters.webp',
      alt: 'Member directory with optional filters expanded.',
      caption: 'Filter controls: use non-location filters when location access is unavailable.',
    },
    {
      src: '/manual/member-provider-directory-location.webp',
      alt: 'Member directory showing synthetic distance results after a location choice.',
      caption: 'Distance result: a synthetic browser location is used only after the member selects a distance option.',
    },
  ],
} as const satisfies Record<string, { src: string; alt: string; caption: string }[]>;