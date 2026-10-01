export type AdminManualScreenshot = { src: string; alt: string; caption: string };

export const adminScreenshots: Record<string, AdminManualScreenshot[]> = {
  "admin-navigation": [
    { src: "/manual/admin-navigation.webp", alt: "Admin navigation", caption: "Admin navigation. Top-level admin navigation shows Dashboard and Registrations with the synthetic admin session." },
    { src: "/manual/admin-navigation-directory.webp", alt: "Directory Management menu", caption: "Directory Management menu. Actual Directory Management dropdown shows provider, application, catalog, invitation, and review destinations." },
    { src: "/manual/admin-navigation-enquiries.webp", alt: "Enquiries menu", caption: "Enquiries menu. Actual Enquiries dropdown lists subscribers, contact enquiries, and platform feedback." },
    { src: "/manual/admin-navigation-profile.webp", alt: "Profile menu and workspace links", caption: "Profile menu and workspace links. Admin profile menu open with safe Sample Admin identity. Actual admin navigation menu opened in the running React app." },
  ],
  "admin-registrations": [
    { src: "/manual/admin-registrations.webp", alt: "Registered accounts", caption: "Registered accounts. List shows two sample member registrations with different verification states." },
    { src: "/manual/admin-registrations-details.webp", alt: "Registration details", caption: "Registration details. Sample member detail dialog displays verification and registration information." },
  ],
  "provider-directory": [
    { src: "/manual/admin-provider-directory.webp", alt: "Provider directory", caption: "Provider directory. Directory shows sample clinic, doctor, and hospital with independent status/publication states." },
    { src: "/manual/provider-directory-filters.webp", alt: "Provider directory filters", caption: "Provider directory filters. Provider-type, services, status, and publication filters expanded." },
    { src: "/manual/provider-directory-actions.webp", alt: "Provider lifecycle actions", caption: "Provider lifecycle actions. Actual provider row action menu shows state-dependent management controls for a Published sample clinic." },
  ],
  "provider-lifecycle-publication": [
    { src: "/manual/admin-provider-lifecycle.webp", alt: "Status and publication controls", caption: "Status and publication controls. Provider list keeps Active/Inactive status distinct from Published/Unpublished directory visibility." },
  ],
  "provider-create": [
    { src: "/manual/provider-create.webp", alt: "Create provider wizard", caption: "Create provider wizard. First step of the actual create-provider wizard, with Sample data entered; no provider was submitted." },
    { src: "/manual/admin-provider-create-populated.webp", alt: "Create a doctor profile", caption: "Create a doctor profile. Doctor-specific form shows Sample identity, professional title, experience and biography; no provider is saved." },
    { src: "/manual/provider-create-review.webp", alt: "Review new provider", caption: "Review new provider. Review & create summary contains only synthetic Sample values; Create provider is not clicked." },
  ],
  "provider-edit": [
    { src: "/manual/provider-edit.webp", alt: "Edit provider wizard", caption: "Edit provider wizard. Actual edit wizard is pre-populated from the Sample Dr. Avery Field record; no fields are saved." },
  ],
  "provider-record-details": [
    { src: "/manual/provider-record-details.webp", alt: "Provider profile and detail sections", caption: "Provider profile and detail sections. Top of Sample Dr. Avery Field profile shows overview and reset-access controls. No email is sent." },
  ],
  "provider-portal-access-recovery": [
    { src: "/manual/provider-portal-access-recovery.webp", alt: "Provider portal access", caption: "Provider portal access. Doctor access panel shows Sample recipient, current reset status and the reset action. Nothing is sent." },
    { src: "/manual/provider-portal-access-setup-preview.webp", alt: "Setup request result preview", caption: "Setup request result preview. Fixture explicitly reports a setup-request preview; no email was sent." },
  ],
  "provider-profile-collections": [
    { src: "/manual/provider-profile-collections.webp", alt: "Doctor qualifications", caption: "Doctor qualifications. Sample doctor qualifications and the add/edit/remove controls." },
    { src: "/manual/provider-profile-qualification-form.webp", alt: "Qualification form", caption: "Qualification form. Actual qualification form filled with unsaved Sample values; Add qualification is not submitted." },
    { src: "/manual/provider-profile-locations.webp", alt: "Manage a provider location", caption: "Manage a provider location. Location editor is populated with sample address values; the location is not saved." },
  ],
  "provider-doctor-visits": [
    { src: "/manual/admin-doctor-visits.webp", alt: "Doctor visits", caption: "Doctor visits. Visiting availability with previous and upcoming synthetic visit periods." },
    { src: "/manual/provider-doctor-visits-add-form.webp", alt: "Schedule a future visit", caption: "Schedule a future visit. Visit-period form uses sample location/date values; Add return is not submitted." },
  ],
  "provider-visiting-calendar": [
    { src: "/manual/admin-provider-visiting-calendar.webp", alt: "Admin visiting-provider calendar", caption: "Admin visiting-provider calendar. Month calendar with a sample visit spanning the selected day and a provider-linked agenda card." },
  ],
  "provider-photo-management": [
    { src: "/manual/provider-photo-management.webp", alt: "Provider photos", caption: "Provider photos. Gallery displays safe local horse/stable sample imagery, alt text, profile-photo state, and management controls." },
    { src: "/manual/provider-photo-upload.webp", alt: "Stage provider photos", caption: "Stage provider photos. Actual upload panel documents supported photo formats, size limit, metadata fields and deferred upload." },
  ],
  "provider-applications": [
    { src: "/manual/admin-provider-applications.webp", alt: "Provider applications", caption: "Provider applications. Pending sample application appears in the actual review queue." },
    { src: "/manual/admin-application-details.webp", alt: "Inspect an application", caption: "Inspect an application. Application detail shows sample professional, contact, service, consent and verification fields." },
    { src: "/manual/admin-application-approval-confirm.webp", alt: "Approval confirmation", caption: "Approval confirmation. Confirmation explains staged-draft result; all action requests are fixture-only." },
    { src: "/manual/admin-application-staged-result.webp", alt: "Sample approval result", caption: "Sample approval result. The UI shows the sample application as reviewed and identifies the staged listing as a draft; the fixture has no live record or email." },
  ],
  "provider-profile-updates": [
    { src: "/manual/admin-provider-updates.webp", alt: "Provider updates queue", caption: "Provider updates queue. One pending sample profile update is available for comparison." },
    { src: "/manual/admin-provider-update-actions.webp", alt: "Provider update actions", caption: "Provider update actions. The actual profile-update row menu exposes Compare profiles." },
    { src: "/manual/admin-provider-update-comparison.webp", alt: "Compare profile and photos", caption: "Compare profile and photos. Actual comparison shows current/proposed sample values and an added photo with safe fixture images." },
    { src: "/manual/admin-provider-update-confirm.webp", alt: "Confirm update decision", caption: "Confirm update decision. Sample update decision confirmation remains entirely in the fixture browser." },
    { src: "/manual/admin-provider-update-result.webp", alt: "Sample update result", caption: "Sample update result. Fixture-only approved state appears in the real page; no live profile is changed." },
  ],
  "provider-invitations": [
    { src: "/manual/admin-invitations-statuses.webp", alt: "Invitation statuses", caption: "Invitation statuses. Sample invitations show Pending, Accepted, Expired, Cancelled, and Completed states." },
    { src: "/manual/admin-invitation-create.webp", alt: "Create invitation", caption: "Create invitation. Doctor invitation form is populated with Sample values; Send invitation is not clicked." },
  ],
  "specializations-catalog": [
    { src: "/manual/admin-specializations.webp", alt: "Specializations catalog", caption: "Specializations catalog. Specializations table and catalog actions use safe Sample entries." },
    { src: "/manual/admin-specialization-csv-upload.webp", alt: "CSV upload", caption: "CSV upload. Actual CSV dialog shows template link, format, and size constraints before file selection." },
    { src: "/manual/admin-specialization-csv-preview.webp", alt: "CSV preview", caption: "CSV preview. CSV preview shows one valid, one duplicate and one invalid Sample row; Import is not clicked." },
  ],
  "languages-catalog": [
    { src: "/manual/admin-languages.webp", alt: "Languages catalog", caption: "Languages catalog. Searchable language catalog shows fixture language names and codes." },
    { src: "/manual/admin-language-form.webp", alt: "Add a language", caption: "Add a language. Actual language dialog displays name and code fields without saving a catalog record." },
  ],
  "provider-reviews-moderation": [
    { src: "/manual/admin-reviews-moderation.webp", alt: "Review moderation queue", caption: "Review moderation queue. Sample pending provider review appears in the queue." },
    { src: "/manual/admin-review-details.webp", alt: "Review details and history", caption: "Review details and history. Sample comment, moderation history and actions appear in the real details view." },
    { src: "/manual/admin-review-publish-result.webp", alt: "Sample moderation result", caption: "Sample moderation result. Published state and synthetic moderation-history entry appear after an intercepted request." },
  ],
  "admin-subscribers": [
    { src: "/manual/admin-subscribers.webp", alt: "Subscribers", caption: "Subscribers. Sample subscriber records show synthetic emails, registration types and dates." },
  ],
  "admin-contact-enquiries": [
    { src: "/manual/admin-contact-enquiries.webp", alt: "Contact enquiries", caption: "Contact enquiries. Sample enquiry is visible in the inbox." },
    { src: "/manual/admin-contact-enquiry-detail.webp", alt: "Contact enquiry detail", caption: "Contact enquiry detail. Read-only sample message and sender details; no reply or outbound action is available." },
  ],
  "admin-platform-feedback": [
    { src: "/manual/admin-private-feedback.webp", alt: "Platform feedback inbox", caption: "Platform feedback inbox. One sample feedback entry with a private message." },
    { src: "/manual/admin-private-feedback-detail.webp", alt: "Private feedback detail", caption: "Private feedback detail. Synthetic feedback message, resolution state and notes; no public display or email." },
  ],
  "admin-activity-logs": [
    { src: "/manual/admin-activity-logs.webp", alt: "Activity log", caption: "Activity log. Synthetic Sample Admin events and reserved documentation IP addresses." },
    { src: "/manual/admin-activity-log-details.webp", alt: "Activity change details", caption: "Activity change details. Expanded activity entry shows the sample before/after review-status change." },
  ],
  "admin-email-logs": [
    { src: "/manual/admin-email-logs.webp", alt: "Email delivery logs", caption: "Email delivery logs. Read-only table shows synthetic Accepted by SMTP and Failed rows with date filters." },
    { src: "/manual/admin-email-logs-date-range.webp", alt: "Filter email logs by date range", caption: "Filter email logs by date range. Read-only view shows the selected custom period and synthetic accepted and failed rows." },
  ],
  "admin-settings": [
    { src: "/manual/admin-settings.webp", alt: "Admin settings", caption: "Admin settings. Actual settings fields show fixture timezone and formatting choices; nothing is saved." },
  ],
  "admin-sign-in-out": [
    { src: "/manual/admin-sign-in-out.webp", alt: "Admin sign-in form", caption: "Admin sign-in form. Signed-out admin login form contains a Sample .example.test address and an empty password field; no credentials are submitted." },
  ],
};
