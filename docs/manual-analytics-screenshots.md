# Admin dashboard and analytics manual screenshots

These are captures of the shipped React pages, not designed or composited
mockups. Recreate them with:

```sh
python scripts/capture-manual-analytics.py
```

The capture script requires the already-running frontend host in
`REPLIT_DEV_DOMAIN`, Python `websockets`, `/repl/tools/bin/chromium`, and
`cwebp`. It starts a dedicated headless Chromium process on CDP port `9243`
with a new temporary user-data directory, selects a CDP target whose type is
`page`, and removes the browser and profile when finished. It does not start or
restart the application.

Before navigation, CDP Fetch interception is enabled for every URL containing
`/api/v1`. The capture fulfills authentication refresh with a synthetic
administrator identity; dashboard, calendar, and analytics reads with fixed
sample aggregates; traffic-write requests with an in-memory 204 response; and
CSV requests with a synthetic CSV body. All other `/api/v1` requests fail
closed with an explicit 599 fixture failure; none are continued to the
backend. Frontend JavaScript, styles, images, and other source modules continue
to load from the running app. No login form, real account, invitation, email,
approval, persisted record, or database is used. A visible
“SAMPLE DATA — demonstration only” badge is added to each captured page by
the browser DOM.

Names use the `Sample` prefix and the synthetic administrator address uses the
reserved `example.test` domain. Counts, dates, map markers, and visiting
calendar entries are fixture-only. Map markers are placed at synthetic
coordinates over an unlabeled open-water area; map tiles do not contain
provider or member records. Traffic charts contain aggregate counts only;
review/feedback images contain no people, contact details, messages, or notes.

## Asset provenance

| Asset | Shipped route and captured state | Fixture/source and manual topic |
| --- | --- | --- |
| `analytics-dashboard-overview.webp` | `/admin/dashboard` — inventory counters, invitation activity, registrations, seven system-timezone days of the legacy homepage-visit counter, and calendar link | Synthetic dashboard API; the seven-day legacy counter is the same measure Analytics can report separately from its sitewide route views |
| `analytics-dashboard-map-filter.webp` | `/admin/dashboard` — map with Clinic locations hidden; Hospital and Doctor toggles remain selected | Synthetic dashboard markers; dashboard documentation is separate from Analytics |
| `analytics-dashboard-calendar.webp` | `/admin/visiting-providers` — April 2026 calendar, April 14 selected, Sample Cedar Equine agenda card | Synthetic `/admin/dashboard/visits` response; dashboard documentation is separate from Analytics |
| `analytics-overview-comparison.webp` | `/admin/analytics?preset=last_30_days` — six curated metrics and previous-period comparisons | Synthetic analytics summary and series; `analytics-workspace-and-date-controls` |
| `analytics-traffic-trends.webp` | `/admin/analytics?section=traffic&preset=last_30_days` — traffic headline metrics and trend | Synthetic traffic summary and series; `analytics-website-traffic` |
| `analytics-traffic-composite.webp` | Same traffic route — taller 1,900px viewport showing filters, headline metrics, trend, category chart and popularity table | Synthetic traffic summary, series, breakdown and ranking; `analytics-website-traffic` |
| `analytics-traffic-category-breakdown.webp` | Same traffic route — page-category chart brought into view | Synthetic traffic breakdown; `analytics-website-traffic` |
| `analytics-traffic-data-table.webp` | Same traffic route — View data table replaces the trend with sample period/value rows | Synthetic traffic series; `analytics-trends-detail-tables-and-coverage` |
| `analytics-coverage-definitions.webp` | Traffic route — Definitions & source coverage expanded with observed dates and tracking notes | Synthetic analytics summary; `analytics-trends-detail-tables-and-coverage` |
| `analytics-traffic-custom-filters.webp` | `/admin/analytics?section=traffic&preset=custom&date_from=2026-04-10&date_to=2026-04-23&group_by=weekly&provider_type=CLINIC` — custom dates, weekly grouping and More filters open | Synthetic analytics responses; `analytics-workspace-and-date-controls` |
| `analytics-traffic-breakdowns.webp` | Traffic route — View detailed reports expanded and brought into view | Synthetic traffic breakdown; `analytics-trends-detail-tables-and-coverage` |
| `analytics-provider-ranking-details.webp` | Traffic route — provider ranking sorted by name with a Sample provider detail row open | Synthetic 23-row provider ranking; `analytics-website-traffic`, `analytics-provider-inventory-applications-invitations` |
| `analytics-provider-ranking-pagination.webp` | Traffic route — sorted provider ranking on page two | Synthetic paginated ranking response; `analytics-website-traffic`, `analytics-provider-inventory-applications-invitations` |
| `analytics-export-dataset-selection.webp` | Traffic route — Export CSV menu open with series, breakdown, and ranking choices | Synthetic export options; `analytics-csv-exports` |
| `analytics-export-complete.webp` | Traffic route — provider-ranking export completes and “CSV downloaded.” is displayed | Synthetic in-browser CSV response; `analytics-csv-exports` |
| `analytics-members-reports.webp` | `/admin/analytics?section=registrations&preset=last_30_days` — registration/cohort metrics and trend | Synthetic registration summary and series; `analytics-member-registration-cohorts` |
| `analytics-members-cohort-charts.webp` | Members route — exclusive-role and verification cohort charts in view | Synthetic registration breakdown; `analytics-member-registration-cohorts` |
| `analytics-members-details.webp` | Members route — member role, verification and account filters expanded | Synthetic registration summary; `analytics-member-registration-cohorts` |
| `analytics-members-cohort-details.webp` | Members route — expanded detailed reports with selected-cohort, role-assignment and account-state groups | Synthetic registration breakdown; `analytics-member-registration-cohorts`, `analytics-trends-detail-tables-and-coverage` |
| `analytics-members-cohort-details-table.webp` | Members route — selected-cohort account-state group expanded to show definition, category/count/basis rows | Synthetic registration breakdown; `analytics-member-registration-cohorts`, `analytics-trends-detail-tables-and-coverage` |
| `analytics-providers-reports.webp` | `/admin/analytics?section=providers&preset=last_30_days&provider_type=CLINIC` — period application/invitation measures and current listed-provider total | Synthetic provider, application, and invitation summary; `analytics-provider-inventory-applications-invitations` |
| `analytics-providers-composite.webp` | Providers route — taller 1,900px viewport showing period and current metrics, application and invitation charts, and the Provider popularity section | Synthetic provider, application, invitation and ranking fixtures; `analytics-provider-inventory-applications-invitations` |
| `analytics-providers-activity-charts.webp` | Providers route — application and invitation status charts | Synthetic application and invitation breakdowns; `analytics-provider-inventory-applications-invitations` |
| `analytics-providers-details.webp` | Providers route — detailed inventory, application, invitation, and ranking tables in view | Synthetic provider, application, invitation and ranking fixtures; `analytics-provider-inventory-applications-invitations`, `analytics-trends-detail-tables-and-coverage` |
| `analytics-reviews-reports.webp` | `/admin/analytics?section=reviews&preset=last_30_days` — review and feedback measures with period trend | Synthetic review and feedback summary/series; `analytics-reviews-and-private-feedback` |
| `analytics-reviews-aggregate-charts.webp` | Reviews route — eligible star distribution and private feedback category charts | Synthetic review and private-feedback breakdowns; `analytics-reviews-and-private-feedback` |
| `analytics-reviews-details.webp` | Reviews route — expanded source-aligned moderation, submissions, ratings and private-feedback detail groups | Synthetic review and feedback breakdowns with no message content; `analytics-reviews-and-private-feedback`, `analytics-trends-detail-tables-and-coverage` |
| `analytics-engagement-reports.webp` | `/admin/analytics?section=engagement&preset=last_30_days` — enquiry/subscriber measures and period trend | Synthetic engagement summary and series; `analytics-enquiries-and-subscribers` |
| `analytics-engagement-type-charts.webp` | Engagement route — enquiry and unique-subscriber type charts | Synthetic enquiry and subscriber breakdowns; `analytics-enquiries-and-subscribers` |
| `analytics-engagement-details.webp` | Engagement route — expanded enquiry and subscriber aggregate tables | Synthetic enquiry and subscriber breakdowns; `analytics-enquiries-and-subscribers`, `analytics-trends-detail-tables-and-coverage` |
| `analytics-workspace-and-date-controls.webp` | Byte-for-byte copy of `analytics-overview-comparison.webp` for the coordinated manual filename | `/admin/analytics?preset=last_30_days`; `analytics-workspace-and-date-controls` |
| `analytics-website-traffic.webp` | Byte-for-byte copy of `analytics-traffic-composite.webp` for the coordinated manual filename | Traffic route; `analytics-website-traffic` |
| `analytics-member-registration-cohorts.webp` | Byte-for-byte copy of `analytics-members-cohort-charts.webp` for the coordinated manual filename | Members route; `analytics-member-registration-cohorts` |
| `analytics-provider-inventory-applications-invitations.webp` | Byte-for-byte copy of `analytics-providers-composite.webp` for the coordinated manual filename | Providers route; `analytics-provider-inventory-applications-invitations` |
| `analytics-reviews-and-private-feedback.webp` | Byte-for-byte copy of `analytics-reviews-aggregate-charts.webp` for the coordinated manual filename | Reviews route; `analytics-reviews-and-private-feedback` |
| `analytics-enquiries-and-subscribers.webp` | Byte-for-byte copy of `analytics-engagement-type-charts.webp` for the coordinated manual filename | Engagement route; `analytics-enquiries-and-subscribers` |
| `analytics-trends-detail-tables-and-coverage.webp` | Byte-for-byte copy of `analytics-coverage-definitions.webp` for the coordinated manual filename | Traffic route; `analytics-trends-detail-tables-and-coverage` |
| `analytics-csv-exports.webp` | Byte-for-byte copy of `analytics-export-dataset-selection.webp` for the coordinated manual filename | Traffic route; `analytics-csv-exports` |

The screenshot metadata is exported by
`frontend/src/pages/admin/manual/analyticsScreenshots.ts`. Analytics screenshots
are keyed by the topic IDs in `frontend/src/pages/admin/manual/analyticsTopics.ts`.