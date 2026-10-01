# Provider performance insights API

Provider reports are available to authenticated provider accounts only at
`GET /api/v1/provider/portal/insights`. The report resolves the listing through
the same explicit `ProviderPortalService` ownership links used by the rest of
the provider portal: completed invitation, approved registration, or direct
portal access. No email matching or client-supplied provider ID selects the
listing. Missing and ambiguous account/listing links return HTTP 403.

## Date selection

Dates use the configured `SystemSettings.timezone` calendar. Requests accept
`preset=last_7_days|last_30_days|this_month|custom`; the default is
`last_30_days`. `custom` requires both inclusive `date_from=YYYY-MM-DD` and
`date_to=YYYY-MM-DD`. A range cannot be reversed, extend into the future, or
exceed 366 inclusive days. Explicit date parameters are rejected with a
non-custom preset. Invalid periods return HTTP 422.

## Report response

```json
{
  "provider_name": "Example Clinic",
  "timezone": "America/Toronto",
  "today": "2026-04-30",
  "period": {
    "date_from": "2026-04-01",
    "date_to": "2026-04-30",
    "preset": "this_month"
  },
  "refreshed_at": "2026-04-30T12:00:00+00:00",
  "metrics": {
    "profile_views": {
      "value": 12,
      "definition": "Successfully loaded member profile pages ...",
      "coverage": {
        "status": "full",
        "from": "2026-03-15",
        "note": "Collection is available for every date in this period."
      },
      "comparison": {
        "change_percent": 20.0,
        "previous_value": 10,
        "reason": null
      }
    },
    "contact_clicks": {},
    "new_conversations": {}
  },
  "contact_breakdown": {
    "phone": 4,
    "email": 3,
    "website": 1
  },
  "snapshot": {
    "saved_members": 8,
    "rating_count": 5,
    "visible_review_count": 4,
    "average_rating": 4.6
  },
  "trends": [
    {
      "date": "2026-04-01",
      "profile_views": 2,
      "contact_clicks": 1
    }
  ]
}
```

Each metric's `value` and comparison fields are numeric or `null`. Coverage is
source-specific:

- `full`: all selected dates are within the known collection boundary.
- `partial`: the range includes dates before collection, or the local rollout
  date itself, when instrumentation began partway through that day.
- `unavailable`: the selected period ends before collection began.
- `unknown`: no durable boundary exists, so zeroes and comparisons cannot be
  inferred.

`coverage.from` is the local date of the independently persisted source
boundary; it is not inferred from the earliest surviving event. If an available
range includes pre-rollout dates, counts include only the covered portion and
the metric is partial. The first rollout date is partial; dates beginning on
the next complete local day can be full. Trends use `null` before source
coverage and zero only for a covered date without events. The contact breakdown
is all `null` when its selected period is wholly unavailable or coverage is
unknown; once any part is covered it returns covered-period action totals.

Percent change compares equal-length adjacent periods and is returned only if
both periods are fully covered and the previous total is nonzero. A partial,
unknown, unavailable, or zero-baseline comparison returns `null` percent with
a concise `reason`.

Metric definitions:

- `profile_views`: successfully loaded, authorized, discoverable member
  provider-profile pages from the existing daily aggregate. Each deliberate
  revisit counts; this is not unique people or appointments.
- `contact_clicks`: activations of phone, email, or website links, from
  prospective aggregate collection only. These are not completed calls,
  emails, bookings, or leads.
- `new_conversations`: durable conversation creations. The query uses only the
  authorized current `provider_user_id`, listing ID, and conversation creation
  time. It does not read messages or contact snapshots. Previous owners'
  conversations are excluded.
- `contact_breakdown`: phone/email/website activations over the selected
  covered period.
- `snapshot.saved_members`: current saved-listing count.
- `snapshot.rating_count` and `snapshot.average_rating`: current, undeleted
  `PUBLISHED` or `HIDDEN` ratings, matching the existing provider portal rating
  predicate. Hidden ratings remain eligible; pending/rejected/deleted ratings
  are not.
- `snapshot.visible_review_count`: current undeleted, published, visible
  nonempty comments, matching the existing public review predicate.

The click and conversation tracking boundaries are separately persisted during
the migration rollout. Historical click data is not backfilled. The messaging
table predates this report and has no older coverage metadata, so conversation
insights begin at their explicit reporting rollout boundary rather than at the
earliest retained conversation. Its first local calendar day is partial.

## Contact activation ingestion

`POST /api/v1/member/providers/{provider_id}/contact-click` accepts a strict
body with no extra keys:

```json
{
  "action": "phone",
  "event_key": "0196..."
}
```

`action` is exactly `phone`, `email`, or `website`. `event_key` must be an RFC
UUIDv7. Its embedded millisecond timestamp is the activation time and supplies
the local aggregate date; no `occurred_at`, member ID, destination, URL, or
free-form data is sent. UUIDv7 also permits the API to reject old retries after
their receipt rows have expired, rather than counting an expired UUIDv4 replay
again. Events at least 48 hours old or more than five minutes in the future are
rejected. Frontends should generate one UUIDv7 per actual link activation and
reuse it only for retries of that same activation.

The endpoint requires an authenticated, email-verified public member and a
currently discoverable active/published listing. A short-lived IP rate limit
protects ingestion. A UUID-only receipt prevents concurrent/retried delivery
from incrementing twice; it expires at the event's 48-hour retry deadline.
Distinct event keys count separately. Receipt rows contain only the UUID and
created/expiry timestamps. Daily aggregates retain date, listing ID, allowlisted
action, and count, with no foreign key to member, no destination, and no
event-to-provider mapping. A rejected/failed tracking request must not be used
to block or change the native phone/email/website action.

An independent FastAPI lifespan cleanup worker purges at most 200 expired
contact receipts per minute, including during periods with no click ingestion.
It uses a separate database session and does not depend on messaging or email
delivery.

Error status: 401 unauthenticated, 403 ineligible/unverified member, 404
non-discoverable listing, 422 invalid schema/event key, 429 rate limited, or 503
temporarily unavailable tracking persistence.