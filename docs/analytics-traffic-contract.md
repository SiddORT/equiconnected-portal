# Analytics traffic collection contract

This contract is for the protected analytics reporter and the traffic collector.
The collection is prospective only: the existing `PublicVisitDaily` homepage
counter remains independent and is never relabelled as sitewide traffic.

## Persisted reporter models

- `TrafficPageCategoryDaily` (`analytics_traffic_page_category_daily`): one row
  per system-calendar date and allowlisted page category, with atomic
  `page_views`.
- `TrafficProviderProfileDaily`
  (`analytics_traffic_provider_profile_daily`): one row per date and discoverable
  provider, with atomic `profile_views`. Its provider UUID is deliberately not a
  foreign key, so later provider deletion cannot erase or block retention of
  aggregate history. It contains no member/browser identity.
- `TrafficVisitorDaily` (`analytics_traffic_visitor_daily`): one row per date
  with an aggregate `estimated_visitors` count. This is a browser-deduplicated
  estimate, not a verified-person count.
- `TrafficTrackingMetadata` (`analytics_traffic_tracking_metadata`): singleton
  row (`id = 1`) with persistent UTC `tracking_started_at`. Reports should
  convert this timestamp into the configured system timezone for the displayed
  tracking-start date, and mark earlier traffic intervals unavailable rather
  than zero.
- `TrafficTrackingReceipt` (`analytics_traffic_tracking_receipts`): temporary
  UUID-only retry receipt with `created_at` and `expires_at`. It is globally
  unique, has no user, IP, route, category, provider, or visitor reference, and
  expires after 48 hours. Cleanup is bounded to at most 200 expired receipts
  during a tracking write.

Page category values are fixed and do not accept paths or URLs:
`home`, `animation`, `signup`, `provider_signup`, `terms`, `privacy`,
`provider_directory`, and `provider_profile`. Directory/profile counts are
verified-member traffic only. Profile views additionally require that the
provider is currently active and published/discoverable.

The six public categories map respectively to `/`, `/animation`, `/signup`,
`/provider/signup`, `/terms-of-service`, and `/privacy-policy`. Token-bearing
provider invitation routes, email-verification callbacks, all login/auth pages,
admin/provider-management pages, fallbacks/errors, and non-route filter or hash
changes are excluded. `/providers` is recorded only after its member directory
request succeeds; `/providers/:id` is recorded only after its authorized,
discoverable provider detail request succeeds. Eligible routes containing
token-, secret-, credential-, password-, authorization-, auth-, code-, or
JWT-like query/fragment parameter names are skipped entirely.

## Event and date semantics

`page_views` is the count of successful allowlisted route views from tracking
rollout onward. An intentional revisit, refresh, or navigation back to a
previously visited route is another view; React Strict Mode/effect replay,
rerenders, query-only filters, hash-only navigation, failed loads, and
automatically retried requests are not new views. The browser submits only a
fixed category, an opaque UUID retry key, and a boolean saying whether this
event is the browser's first eligible visit that local day. No URL, search
term, filter, token, member identifier, IP-derived value, coordinate, or
free-form content is submitted.

The browser keeps only a local calendar-date marker in local storage; it is not
sent to the server. The marker's date is computed in the configured system
timezone, fetched from the existing public system-settings endpoint, so browser
timezone differences do not shift the estimate into a different reporting day.
If that setting or browser storage is unavailable, the route view is still
recorded but the visitor estimate is not incremented. The server trusts the
marker's one-day indication and atomically increments `estimated_visitors` once
for the accepted first-view event. Storage resets/different devices may
overcount. Report a date's estimate as an estimate; do not sum daily estimates
and call the result unique people. A sum must be labelled `visitor-days`.

All aggregate dates are `SystemSettings.timezone` calendar dates at ingestion.
The idempotency receipt deduplicates same-key retries across all categories
without storing which event consumed it. A distinct key for a deliberate
navigation is counted again. Only UUID keys are accepted and receipts expire
after 48 hours; they are not a visit history. Ingestion is rate-limited using a
transient in-memory request window; client/network identifiers are not stored
with traffic aggregates or retry receipts.
