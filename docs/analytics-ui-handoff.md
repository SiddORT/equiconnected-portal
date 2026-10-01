# Analytics UI handoff for the portal manual

The reporting API, access rules, and operational Dashboard are unchanged. Update
the separately maintained portal manual with these Analytics interactions; this
handoff does not edit that manual.

## Section labels and existing links

| Visible label | Existing `section` query value |
| --- | --- |
| Overview | `overview` (or omitted) |
| Website traffic | `traffic` |
| Members | `registrations` |
| Providers | `providers` |
| Reviews & feedback | `reviews` |
| Enquiries & subscribers | `engagement` |

Existing date and filter deep links remain supported. Left/right arrows navigate
the section tabs; Home/End go to the first/last section.

## Default view and dates

- The default date range is Last 30 days.
- Overview selects only supplied website page views, provider profile views,
  new member registrations, new provider applications, accepted enquiries, and
  new unique subscribers. Missing keys are omitted; a supplied unavailable value
  is not displayed as zero.
- Overview has one website-page-views trend and links to detailed sections.
- Date range and grouping remain visible. Custom ranges require both dates,
  with start on or before end. Dates use the displayed reporting timezone.
- Refresh reloads the reports. Loading, partial failure, and retry messages
  distinguish an incomplete request from covered zero activity.

## Progressive disclosure

- More filters starts closed. Raw record-ID input fields are no longer shown.
  Existing record/specialization deep-link filters appear in removable active
  filter indicators. Filters not used by the selected section are marked as
  such; dataset-specific scope does not narrow unrelated metrics.
- Each detail section has explicit headline metrics, one Trend metric selector,
  and up to two curated breakdowns.
- View data table starts closed and replaces its chart when opened. Close the
  table to return to the chart.
- View detailed reports starts closed; its individual aggregate reports also
  start closed. Current provider inventory is fetched when requested.
- Definitions & source coverage and individual definitions start closed.
  Expand these for source observations, estimate limitations, and explanations
  of period activity versus current snapshots.
- Native disclosures support keyboard activation. Closing a disclosure removes
  its controls from keyboard navigation.

## Provider popularity and exports

- Provider popularity is the single primary popularity presentation, rather
  than duplicate leader charts.
- Default columns are provider, period profile views, period review submissions,
  and current average rating with eligible rating count.
- Provider names open provider records. Listing details, saves, and review
  links are disclosed per row. Additional sort options provides eligible rating
  count and current saves sorting; all primary columns remain sortable.
- There is one provider-name search, server pagination, and rows-per-page.
  Search/filter/sort changes reset pagination.
- Export CSV retains all existing time-series, domain-breakdown, and
  provider-ranking datasets, including secondary fields. Ranking exports match
  the selected backend sort and filters, but export the matching dataset rather
  than just the visible page.
- A failed CSV export displays a retryable error, not a success message.

## Interpretation to retain

Current listed-provider totals are catalogue snapshots, not new additions in
the selected period. Verified member counts describe the current state of the
selected registration cohort. Ratings retain their eligible counts and exclude
pending/rejected reviews. Feedback is private and separate from provider reviews.
Visitor-days are not unique visitors across a period. Partial/unavailable traffic
intervals are not zero activity. First/last retained business-event dates are
observations, not proof of complete collection coverage. Comparisons appear only
when supplied as supported; no conversion funnel has been introduced.

## Validation evidence

Frontend tests cover curated content, legacy filter links, disclosures, singular
trends, ranking sorting/pagination, scoped exports, zero/unavailable and partial
coverage, custom ranges, retry, and stale-request protection. Backend reporting
contract and ranking-scope regressions retain the existing reporting semantics.
Layout validation uses intercepted synthetic browser responses, not seeded live
records.