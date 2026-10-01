# Illustrated portal manual: delivered coverage

The guide is at `/admin/user-manual` inside the existing admin layout and guard.
Its only new navigation entry is **User Manual**, directly below the profile
identity block. It does not add a public, member, or provider manual entry.

## Feature-to-topic checklist

Each task-oriented topic provides purpose, location, permitted role,
prerequisites, numbered instructions, expected result, and restrictions.
The detailed source-to-topic tables are the authoritative coverage audit:

- [x] [Admin workflows](manual-admin-coverage.md): sign-in/out and menus,
  registration inspection, shared table controls, provider creation/edit/detail,
  lifecycle/publication, contacts/locations/photos, services/specializations/
  languages, doctor qualifications/organizations/availability/trips, provider
  access/setup/recovery, application/profile-update review, invitations,
  catalog/CSV workflows, review moderation, subscribers, enquiries, private
  feedback, activity/email logs, and settings.
- [x] [Provider/member workflows](manual-roles-coverage.md): public entry and
  verification, provider registration and invitation draft/final submission,
  access prerequisites, setup/recovery/sign-in, profile tabs/collections,
  uploaded versus saved photos, pending changes and feedback/discard,
  eligible doctor trips, member account/profile/stable/horse management,
  directory filters/location permission/saves, provider contacts/photos/visits,
  review create/edit/delete and moderation, private feedback and history,
  member-initiated private conversations, provider replies, contact consent,
  unread/read state, inbox/history paging and notification limits.
- [x] Provider Insights: the linked provider's own period activity, presets and
  custom dates, comparison and coverage states, chart explanations/data tables,
  contact-link counts, refresh/errors and separate current snapshots.
- [x] [Dashboard and Analytics](manual-analytics-coverage.md): separate operational
  Dashboard widgets and all six reporting tabs; presets/custom inclusive dates,
  timezone/grouping, filter scope, refresh/reset, period/current-state bases,
  visitor estimates versus people, legacy homepage versus sitewide views,
  cohort states, coverage versus zero, comparisons, chart data/detail tables,
  provider ranking/sort/pagination/drill-through, all export choices and their
  aggregate-only 5,000-row ceiling.
- [x] Plain-language definitions and troubleshooting are included alongside
  the workflows, without adding unimplemented booking or recovery controls.

## Illustration checklist and provenance

The image mapping in `frontend/src/pages/admin/manual/screenshots.ts` combines
four provenance-backed capture sets:

- [x] [Admin screenshots](manual-admin-screenshots.md): actual forms, collection
  controls, table actions, confirmations, photo comparisons, access recovery,
  visit scheduling, and outcomes.
- [x] [Role screenshots](manual-role-screenshots.md): onboarding/verification,
  invitation draft/final, setup/recovery, profile/photo review states, trips,
  member discovery/profile/reviews/feedback/history.
- [x] [Dashboard and Analytics screenshots](manual-analytics-screenshots.md):
  populated operational widgets, all six tabs, custom controls, source/detail
  disclosures, data tables, rankings/pagination, and export selection/result.
- [x] [Getting-started screenshots](manual-public-screenshots.md): public entry,
  populated contact/subscription controls, and their confirmation states.
- [x] Captures use visibly labelled synthetic fixtures only. API requests,
  including writes, authentication, email actions and decisions, are intercepted
  before network continuation. Unknown application endpoints fail closed.
- [x] Images are local compressed WebP assets bundled by the production build,
  lazy-loaded in stable fitted previews, and enlargeable to original pixels.

## Usability and regression checks

- `UserManualPage.test.tsx`: section headings, full-text search, filtered/no-result
  contents, anchors, source step numbering, malformed hashes, native contents
  disclosure, image dialog, fit/full-size controls and Escape/focus restoration.
- `manual/manualContent.test.ts`: unique stable IDs, complete topic structure,
  separate dashboard/reporting coverage, valid topic mappings and deployed WebP
  asset existence.
- `AdminTopNav.test.tsx` and `Router.test.tsx`: first menu entry, active/closing
  behavior, and existing administrator access protection.
- `python scripts/check-manual-browser.py`: genuine desktop and 375px mobile
  device emulation, direct load/refresh, guarded roles, menu, search/no-results,
  section targets, image loading/full-size viewing, and keyboard focus return.
- Run frontend tests with constrained workers and `npm run build` after merging
  portal changes. Reconcile the source audit and regenerate affected captures
  when controls or permission boundaries change; do not adjust workflows merely
  to match the guide.