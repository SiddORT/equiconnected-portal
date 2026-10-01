# Admin analytics API contract

Provider-owned, privacy-minimal performance reporting is documented separately
in [Provider performance insights API](provider-insights-api.md). Provider
Insights is not an administrator analytics endpoint and does not accept an
administrator's listing filters or sitewide metrics.

This contract is shared by the analytics page and the backend report service.
All dates are calendar dates in the configured system timezone. Date ranges are
inclusive in requests and are converted to a UTC half-open interval internally.
The default range is `last_30_days`; `custom` requires both `date_from` and
`date_to`. `group_by` is `daily`, `weekly`, or `monthly`.

## Authorization and route registration

Every route below requires the existing administrator role. The router is
implemented in `backend/app/api/v1/analytics.py` and must be included from the
API v1 router at `/api/v1`; its own prefix is `/admin/analytics`.

## Shared query parameters

| Parameter | Values / meaning |
|---|---|
| `preset` | `today`, `yesterday`, `last_7_days`, `last_30_days` (default), `this_month`, `last_month`, `all`, `custom` |
| `date_from`, `date_to` | `YYYY-MM-DD`, inclusive system-timezone dates; required together for `custom` |
| `group_by` | `daily`, `weekly`, `monthly` |
| `provider_type` | `DOCTOR`, `CLINIC`, `HOSPITAL` |
| `provider_status` | `DRAFT`, `UNDER_REVIEW`, `ACTIVE`, `INACTIVE` |
| `publication_status` | `PUBLISHED`, `UNPUBLISHED` |
| `provider_id`, `specialization_id` | UUID filters |
| `provider_search` | Case-insensitive provider-name filter (max 100 characters) |
| `country`, `city` | Exact recorded provider-listing geography filters; never visitor geography |
| `member_role` | `horse_owner`, `stable_manager`, `both` |
| `member_verified` | Current verification state of the registration cohort |
| `member_active` | Current account state of the registration cohort |
| `application_status` | Provider application status |
| `invitation_status` | Invitation status |
| `review_status`, `rating` | Provider review state and 1–5 stars |
| `feedback_category`, `feedback_status` | Private feedback category and current state; `withdrawn` is a separate state |
| `enquiry_type`, `subscriber_type` | Stored enquiry/subscriber category |

Filters are applied only where the field has a real relationship to the metric.
Provider filters do not narrow sitewide traffic, member registrations, enquiries,
or subscribers. Member filters affect registration cohort metrics only.

## Routes

### `GET /api/v1/admin/analytics/summary`

Returns this top-level shape:

```json
{
  "timezone": "UTC",
  "period": {
    "preset": "last_30_days",
    "date_from": "2026-01-01",
    "date_to": "2026-01-30",
    "group_by": "daily"
  },
  "tracking_started_date": "2026-01-15",
  "coverage": {
    "traffic_page_views": {
      "from": "2026-01-15",
      "through": "2026-01-30",
      "available": true
    }
  },
  "refreshed_at": "2026-01-30T12:00:00+00:00",
  "sections": {
    "traffic": {
      "metrics": [
        {
          "key": "website_page_views",
          "value": 14,
          "unit": "views",
          "basis": "period",
          "available": true,
          "partial_coverage": true,
          "definition": "..."
        }
      ],
      "coverage": {
        "tracked_since": "2026-01-15",
        "available": true,
        "partial": true
      }
    }
  }
}
```

Coverage is provided by source (member registrations, provider applications,
invitations, provider reviews, platform feedback, contact enquiries, subscribers,
legacy homepage visits, tracked page views, tracked provider profiles, and
visitor estimates). Traffic dates before `tracking_started_date` are never
presented as zero. If a selected interval starts before rollout but continues
after it, traffic cards state that coverage is partial and series begin on the
first tracked date.

For business-event tables, `coverage.from`/`coverage.through` are the first and
last retained event dates only; they are **not** claimed coverage bounds.
`coverage.coverage_start` is `null` and `coverage.coverage_known` is `false`
unless there is a documented complete-coverage boundary. Previous-period
comparisons are therefore unavailable with `unavailable_reason:
"coverage_unknown"` even when the first observed event predates the comparison
interval. Traffic sources instead use the known `coverage_start` from persistent
instrumentation metadata.

Each metric has a stable `key`, display label, numeric or `null` `value`, `unit`,
`basis` (`period` or `current`), and `definition`. Period metrics include
`comparison` with `available`, `previous_value`, `change_percent`, and
`unavailable_reason`; unavailable comparison percentages are `null`, never
infinite. A zero prior-period baseline has reason `zero_baseline`. Period metrics
also include source `coverage`. Snapshots do not include period comparisons.
Sections and their key objects:

- `traffic.metrics`: `website_page_views`, `estimated_visitor_days`,
  `latest_daily_visitor_estimate`, `directory_views`, `provider_profile_views`,
  and `legacy_homepage_visits`. Directory/profile filters apply only to the
  matching member metrics. The legacy value remains the separate
  `public_visit_daily` homepage-only total.
- `registrations.metrics`: `public_member_registrations` and
  `verified_registrations`. `cohort_current_state` contains `total`, exclusive
  `roles` (`horse_owner`, `stable_manager`, `both`), `verified` and `active`
  state counts, and potentially overlapping `role_assignments`.
- `providers.inventory`: `total`, `status`, `type`, `publication`, `active`,
  and `active_published`; the last means both ACTIVE and PUBLISHED.
- `applications.metrics`: new applications, recorded approval/rejection
  decisions, invitations created, and invitations sent.
  `current_status`/`invitation_status` are current snapshots;
  `submitted_cohort_status`/`invitation_cohort_status` describe selected-period
  cohorts by their current status. `legacy_compatible_invitation_totals`
  includes accepted (accepted + completed) and cancelled-or-expired values.
- `engagement.metrics`: `contact_enquiries` and `new_subscribers`, with
  `enquiry_types` and `subscriber_types` selected-period breakdowns.
- `reviews.metrics`: initial submission count, all-time/current eligible
  average rating and rating count. `current_status` excludes deleted rows;
  `retained_deleted_history` is separate; `star_distribution` is eligible
  published/hidden ratings only.
- `feedback.metrics`: private feedback submissions, average optional rating,
  and rated response count. Current states exclude withdrawn records;
  `withdrawn` is separate; `categories` contain counts only.

Period metrics cover website page views and visitor-days (not unique people),
directory/profile views, new public member registrations, applications,
durably stored enquiries, new unique subscriber records, initial review
submissions, and feedback submissions. Current snapshots cover provider
inventory/publication, eligible provider ratings, saved providers, and current
moderation/application/invitation/feedback states. Dual-role members count once
in member totals; a separate role-assignment breakdown may overlap. Withdrawn
feedback and retained deleted reviews are reported separately from active
moderation states.

### `GET /api/v1/admin/analytics/series?metric=<key>`

Supported `metric` keys are `website_page_views`, `estimated_visitor_days`,
`directory_views`, `provider_profile_views`, `public_member_registrations`,
`provider_applications`, `provider_invitations_created`,
`provider_invitations_sent`, `provider_application_decisions`,
`contact_enquiries`, `new_subscribers`, `provider_review_submissions`,
`platform_feedback_submissions`, and `legacy_homepage_visits`.
Returns `metric`, `unit`, `timezone`, `period`, `coverage`, boolean `available`,
boolean `partial_coverage`, and `data`, a zero-filled array of `{ bucket, value }`
points for the covered date range (or `null` when wholly outside source coverage).
Traffic points before instrumentation are omitted, not synthesized as zero.
Unsupported metric/filter combinations return HTTP 422 with a stable error
code. Daily browser estimates remain daily and are never summed or relabelled
as period-unique visitors.

### `GET /api/v1/admin/analytics/breakdowns?domain=<domain>`

`domain` is one of `traffic`, `registrations`, `providers`, `applications`,
`invitations`, `reviews`, `feedback`, `enquiries`, or `subscribers`. Returns
`domain`, `timezone`, `period`, `coverage`, `definitions`, and named `groups`.
Group values are JSON objects/arrays of aggregate values, rather than a universal
row schema; each group has a matching human-readable definition. In addition to
the summary breakdowns, review groups include period action counts,
top-reviewed-provider and selected-period-submission leaders. Feedback groups
include period submission categories/ratings and current backlog counts.
These are count breakdowns, not a conversion funnel. Rating averages/counts use
only undeleted `PUBLISHED` or `HIDDEN` provider reviews; pending/rejected reviews
are excluded and hidden approved ratings remain eligible.

### `GET /api/v1/admin/analytics/provider-ranking`

Returns a server-paginated `data` array and `meta` (`page`, `page_size`, `total`,
`total_pages`), plus period, timezone, and coverage. Rows include provider ID,
name/type, current provider/publication status, period profile views and initial
review submissions, current eligible rating average/count, and current saved
provider count. Includes matching providers with zero period views. Sort fields
are `profile_views`, `review_submissions`, `average_rating`, `rating_count`,
`saved_count`, and `name`. `sort_direction` is `asc` or `desc`; ties are resolved
deterministically by provider name and ID. Before profile-view coverage starts,
`profile_views_available` is false and each row's `profile_views` is `null`, not
an observed zero. Search/filter/sort/page-size changes should reset the requested page.
Only non-PII listing and aggregate fields are returned.

### `GET /api/v1/admin/analytics/export?dataset=<dataset>`

`dataset` is `series`, `breakdowns`, or `provider-ranking`. `metric` is required
for series; `domain` is required for breakdowns. It accepts the same filters and
metric/domain selection as the corresponding read route, and emits a UTF-8 CSV
attachment with a maximum of 5,000 data rows; an explicit notice row marks a
truncated export. Series columns are `bucket,value`; breakdown columns are
`section,metric,value`; provider-ranking columns are `provider_id,provider_name,
provider_type,provider_status,publication_status,profile_views,
review_submissions,average_rating,rating_count,saved_count`. Provider ranking
exports use the same filters/order as the table. Timezone, date bounds,
grouping, applied filters, definitions, and coverage are included as prefixed
metadata rows, padded so every CSV row has the same number of columns. CSV cells
are formula-injection safe. Exports never contain member/subscriber/enquirer contact details,
free-text feedback, internal notes, raw URLs, visitor identifiers, or member
browsing histories.

## Metric and coverage notes

- Legacy `public_visit_daily` remains the daily **homepage visits** counter; it
  is never combined with new route page views or called unique visitors.
- New traffic numbers begin at the traffic instrumentation rollout date.
  Earlier traffic dates are unavailable, not zero. No visitor identifiers or
  IP addresses are used in analytics.
- A visitor estimate is an aggregate browser-deduplicated daily count.
  Different devices/storage resets can overcount and unavailable storage can
  undercount; it is not a count of verified people. Multi-day totals are
  visitor-days.
- Directory/profile traffic counts only successful verified-member pages.
- New subscribers count inserted normalized subscriptions, not repeated form
  attempts. Enquiries count saved records regardless of email delivery.
- Review submissions use original creation time; edits and moderation changes
  are not submissions. Soft-deleted review history is separate from active
  review-state totals. Rating aggregates use undeleted published/hidden rows.
- Feedback submissions use `submitted_at`; withdrawn rows remain a separate
  count and are not counted in current pending/in-review/resolved/rejected
  backlogs. Feedback contents remain private.
- Provider inventory, status, publication, ratings, and saved-provider totals
  are current snapshots, not reconstructed historical states.
- Previous-period comparisons use an equal number of system-local calendar
  days. Comparisons are unavailable if source coverage does not span both
  periods or if a meaningful percentage cannot be calculated from a zero
  baseline.