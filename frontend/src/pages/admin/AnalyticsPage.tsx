import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { exportAnalytics, getAnalyticsBreakdowns, getAnalyticsSeries, getAnalyticsSummary, getProviderRanking } from '@/api/analytics';
import { extractErrorMessage } from '@/api/client';
import { AnalyticsChart } from '@/components/analytics/AnalyticsChart';
import { AnalyticsBreakdownTables } from '@/components/analytics/AnalyticsBreakdownTables';
import { ProviderRankingTable } from '@/components/analytics/ProviderRankingTable';
import { Card } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageHeader } from '@/components/layout/PageHeader';
import type { AnalyticsBreakdowns, AnalyticsDomain, AnalyticsFilters, AnalyticsGroup, AnalyticsGrouping, AnalyticsMetric, AnalyticsPreset, AnalyticsSeries, AnalyticsSort, AnalyticsSummary, ProviderRankingResponse } from '@/types/analytics';
import styles from './AnalyticsPage.module.css';

const TABS = [
  { id: 'overview', label: 'Overview', domains: [] as AnalyticsDomain[] },
  { id: 'traffic', label: 'Website traffic', domains: ['traffic'] as AnalyticsDomain[] },
  { id: 'registrations', label: 'Members', domains: ['registrations'] as AnalyticsDomain[] },
  { id: 'providers', label: 'Providers', domains: ['providers', 'applications', 'invitations'] as AnalyticsDomain[] },
  { id: 'reviews', label: 'Reviews & feedback', domains: ['reviews', 'feedback'] as AnalyticsDomain[] },
  { id: 'engagement', label: 'Enquiries & subscribers', domains: ['enquiries', 'subscribers'] as AnalyticsDomain[] },
] as const;
type TabId = typeof TABS[number]['id'];
type PageStatus = 'loading' | 'success' | 'error';

const PRESETS: Array<[AnalyticsPreset, string]> = [
  ['today', 'Today'], ['yesterday', 'Yesterday'], ['last_7_days', 'Last 7 days'],
  ['last_30_days', 'Last 30 days'], ['this_month', 'This month'],
  ['last_month', 'Last month'], ['all', 'All available data'], ['custom', 'Custom range'],
];

const METRIC_LABELS: Record<string, string> = {
  website_page_views: 'Website page views', estimated_visitor_days: 'Estimated visitor-days',
  latest_daily_visitor_estimate: 'Latest daily visitor estimate', directory_views: 'Directory views',
  provider_profile_views: 'Provider profile views', legacy_homepage_visits: 'Legacy homepage visits',
  public_member_registrations: 'New member registrations', verified_registrations: 'Verified in selected cohort',
  provider_applications: 'New provider applications', provider_application_decisions: 'Recorded application decisions', application_approvals: 'Recorded approvals',
  application_rejections: 'Recorded rejections', provider_invitations_created: 'Invitations created',
  provider_invitations_sent: 'Invitations sent', contact_enquiries: 'Accepted enquiries',
  new_subscribers: 'New unique subscribers', provider_review_submissions: 'Review submissions',
  platform_feedback_submissions: 'Private feedback submissions', average_rating: 'Current eligible average',
  rating_count: 'Current eligible rating count', saved_count: 'Current saved-provider count',
  average_optional_rating: 'Average optional feedback rating',
  optional_rating_average: 'Average optional feedback rating',
  rated_response_count: 'Rated feedback responses',
  feedback_rating_average: 'Average platform feedback rating',
  feedback_rated_response_count: 'Rated feedback responses',
  eligible_review_rating_average: 'Current eligible average rating',
  eligible_review_rating_count: 'Current eligible rating count',
};
const SERIES_BY_TAB: Partial<Record<TabId, string[]>> = {
  overview: ['website_page_views'], traffic: ['website_page_views', 'estimated_visitor_days', 'directory_views', 'provider_profile_views', 'legacy_homepage_visits'],
  registrations: ['public_member_registrations'], providers: ['provider_applications', 'provider_application_decisions', 'provider_invitations_created', 'provider_invitations_sent'],
  reviews: ['provider_review_submissions', 'platform_feedback_submissions'], engagement: ['contact_enquiries', 'new_subscribers'],
};
const FILTER_KEYS = [
  'provider_type', 'provider_status', 'publication_status', 'provider_id', 'specialization_id',
  'provider_search', 'country', 'city', 'member_role', 'member_verified', 'member_active',
  'application_status', 'invitation_status', 'review_status', 'rating', 'feedback_category',
  'feedback_status', 'enquiry_type', 'subscriber_type',
] as const;
type FilterKey = typeof FILTER_KEYS[number];

function validTab(value: string | null): TabId {
  return TABS.find((tab) => tab.id === value)?.id ?? 'overview';
}

function getFilters(params: URLSearchParams): AnalyticsFilters {
  const presetValue = params.get('preset') as AnalyticsPreset | null;
  const grouping = params.get('group_by') as AnalyticsGrouping | null;
  const filters: AnalyticsFilters = {
    preset: PRESETS.some(([value]) => value === presetValue) ? presetValue! : 'last_30_days',
    group_by: ['daily', 'weekly', 'monthly'].includes(grouping ?? '') ? grouping! : 'daily',
  };
  for (const key of FILTER_KEYS) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  for (const key of ['date_from', 'date_to'] as const) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  return filters;
}

function queryFor(filters: AnalyticsFilters, tab: TabId): AnalyticsFilters {
  const next: AnalyticsFilters = { ...filters };
  const allowed = new Set<FilterKey>();
  if (tab === 'traffic' || tab === 'overview') {
    ['provider_id', 'provider_type', 'provider_search', 'specialization_id'].forEach((key) => allowed.add(key as FilterKey));
  }
  if (tab === 'registrations' || tab === 'overview') {
    ['member_role', 'member_verified', 'member_active'].forEach((key) => allowed.add(key as FilterKey));
  }
  if (tab === 'providers' || tab === 'overview') {
    ['provider_type', 'provider_status', 'publication_status', 'provider_id', 'specialization_id', 'provider_search', 'country', 'city', 'application_status', 'invitation_status'].forEach((key) => allowed.add(key as FilterKey));
  }
  if (tab === 'reviews' || tab === 'overview') {
    ['provider_type', 'provider_status', 'publication_status', 'provider_id', 'specialization_id', 'provider_search', 'review_status', 'rating', 'feedback_category', 'feedback_status'].forEach((key) => allowed.add(key as FilterKey));
  }
  if (tab === 'engagement' || tab === 'overview') ['enquiry_type', 'subscriber_type'].forEach((key) => allowed.add(key as FilterKey));
  FILTER_KEYS.forEach((key) => { if (!allowed.has(key)) delete next[key]; });
  return next;
}

function queryForDomain(filters: AnalyticsFilters, domain: AnalyticsDomain): AnalyticsFilters {
  const next: AnalyticsFilters = { preset: filters.preset, date_from: filters.date_from, date_to: filters.date_to, group_by: filters.group_by };
  const provider = ['provider_type', 'provider_status', 'publication_status', 'provider_id', 'specialization_id', 'provider_search'];
  const include = domain === 'traffic' ? ['provider_type', 'provider_id', 'specialization_id', 'provider_search']
    : domain === 'providers' ? [...provider, 'country', 'city']
      : domain === 'reviews' ? [...provider, 'review_status', 'rating']
        : domain === 'feedback' ? ['feedback_category', 'feedback_status']
          : domain === 'registrations' ? ['member_role', 'member_verified', 'member_active']
            : domain === 'applications' ? ['provider_type', 'application_status']
              : domain === 'invitations' ? ['provider_type', 'invitation_status']
                : domain === 'enquiries' ? ['enquiry_type']
                  : domain === 'subscribers' ? ['subscriber_type'] : [];
  include.forEach((key) => {
    const value = filters[key as FilterKey];
    if (value) next[key as FilterKey] = value;
  });
  return next;
}

function queryForMetric(filters: AnalyticsFilters, metric: string): AnalyticsFilters {
  if (['website_page_views', 'estimated_visitor_days', 'legacy_homepage_visits'].includes(metric)) {
    return { preset: filters.preset, date_from: filters.date_from, date_to: filters.date_to, group_by: filters.group_by };
  }
  const metricDomain: AnalyticsDomain = metric === 'public_member_registrations' ? 'registrations'
    : metric.includes('application') ? 'applications'
      : metric.includes('invitation') ? 'invitations'
        : metric === 'contact_enquiries' ? 'enquiries'
          : metric === 'new_subscribers' ? 'subscribers'
            : metric.includes('review') ? 'reviews'
              : metric.includes('feedback') ? 'feedback'
                : metric === 'directory_views' || metric === 'provider_profile_views' ? 'traffic' : 'traffic';
  return queryForDomain(filters, metricDomain);
}

function displayLabel(key: string) {
  return METRIC_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function MetricCard({ metric, eligibleCount }: { metric: AnalyticsMetric; eligibleCount?: AnalyticsMetric }) {
  const value = metric.value === null || metric.available === false ? 'Unavailable' : metric.value.toLocaleString();
  const comparison = metric.comparison;
  return (
    <Card padding="md" shadow="sm" className={styles.metricCard}>
      <div className={styles.metricTop}>
        <span className={styles.metricLabel}>{METRIC_LABELS[metric.key] ?? metric.label ?? displayLabel(metric.key)}</span>
        <span className={metric.basis === 'current' ? styles.snapshotTag : styles.periodTag}>{metric.basis === 'current' ? 'Current' : 'Period'}</span>
      </div>
      <strong className={styles.metricValue}>{value}<small>{metric.value !== null && metric.available !== false ? ` ${metric.unit}` : ''}</small></strong>
      {eligibleCount && <span className={styles.metricLabel}>{eligibleCount.value === null || eligibleCount.available === false ? 'Eligible count unavailable' : `${eligibleCount.value.toLocaleString()} rated responses`}</span>}
      {metric.available !== false && metric.value !== null && comparison?.available && comparison.change_percent !== null && metric.basis === 'period' && (
        <span className={comparison.available && comparison.change_percent !== null ? styles.comparison : styles.comparisonMuted}>
          {comparison.available && comparison.change_percent !== null
            ? `${comparison.change_percent > 0 ? '+' : ''}${comparison.change_percent.toFixed(1)}% vs ${comparison.previous_value?.toLocaleString() ?? '—'} previous period`
            : `Comparison unavailable${comparison.unavailable_reason ? ` · ${comparison.unavailable_reason.replace(/_/g, ' ')}` : ''}`}
        </span>
      )}
      {metric.partial_coverage && <span className={styles.partial}>Partial coverage</span>}
      {metric.definition && <details className={styles.definition}><summary>Definition</summary><p>{metric.definition}</p></details>}
    </Card>
  );
}

const HEADLINES: Record<TabId, string[]> = {
  overview: ['website_page_views', 'provider_profile_views', 'public_member_registrations', 'provider_applications', 'contact_enquiries', 'new_subscribers'],
  traffic: ['website_page_views', 'directory_views', 'provider_profile_views'],
  registrations: ['public_member_registrations', 'verified_registrations'],
  providers: ['provider_applications', 'provider_invitations_created', 'provider_invitations_sent'],
  reviews: ['provider_review_submissions', 'platform_feedback_submissions', 'eligible_review_rating_average', 'feedback_rating_average'],
  engagement: ['contact_enquiries', 'new_subscribers'],
};

function headlineMetrics(summary: AnalyticsSummary, tab: TabId): AnalyticsMetric[] {
  const supplied = Object.values(summary.sections).flatMap((section) => section.metrics ?? []);
  const metrics = HEADLINES[tab].flatMap((key) => {
    const metric = supplied.find((item) => item.key === key);
    return metric ? [metric] : [];
  });
  if (tab === 'providers') {
    const total = summary.sections.providers?.inventory?.total;
    if (typeof total === 'number') metrics.push({
      key: 'listed_provider_total', label: 'Current listed providers', value: total,
      unit: 'providers', basis: 'current', definition: 'All current provider records, including unpublished and inactive listings; not selected-period additions.',
    });
  }
  return metrics;
}

function valueAtPath(source: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    const record = value as Record<string, unknown>;
    if (segment in record) return record[segment];
    const match = Object.keys(record).find((key) => key.toLowerCase().replace(/[-\s]/g, '_') === segment.toLowerCase().replace(/[-\s]/g, '_'));
    return match ? record[match] : undefined;
  }, source);
}

function namedGroup(groups: AnalyticsBreakdowns['groups'] | undefined, paths: string[]): AnalyticsGroup | undefined {
  for (const path of paths) {
    const value = valueAtPath(groups, path);
    if (Array.isArray(value) || (value && typeof value === 'object')) return value as AnalyticsGroup;
  }
  return undefined;
}

function chartRows(
  value: AnalyticsGroup | undefined,
  measureFields: string[] = ['value', 'count', 'total', 'views', 'submissions', 'review_submissions', 'rating_count'],
): AnalyticsGroup | undefined {
  if (!value) return undefined;
  if (Array.isArray(value)) {
    return value.map((row, index) => {
      const item = row as Record<string, unknown>;
      const label = item.label ?? item.name ?? item.provider_name ?? item.status ?? item.category ?? item.type ?? item.role ?? item.rating ?? item.bucket ?? `Item ${index + 1}`;
      const measure = measureFields.map((field) => item[field]).find((candidate) => typeof candidate === 'number' || candidate === null);
      return { label: String(label), value: measure ?? null };
    });
  }
  const object = value as Record<string, unknown>;
  const numericEntries = Object.values(object).some((item) => typeof item === 'number');
  if (numericEntries) return value;
  for (const wrapper of ['data', 'values', 'counts', 'items', 'rows', 'breakdown']) {
    const wrapped = object[wrapper];
    if (Array.isArray(wrapped) || (wrapped && typeof wrapped === 'object')) return chartRows(wrapped as AnalyticsGroup, measureFields);
  }
  return value;
}

interface ChartSpec {
  title: string;
  domain: AnalyticsDomain;
  path: string;
  group: AnalyticsGroup;
  unit: string;
  definition: string;
  kind: 'bars' | 'columns';
}

function makeChart(report: AnalyticsBreakdowns, title: string, paths: string[], unit: string, kind: ChartSpec['kind'], fields?: string[]): ChartSpec | null {
  const path = paths.find((candidate) => namedGroup(report.groups, [candidate]) !== undefined);
  if (!path) return null;
  const group = namedGroup(report.groups, [path]);
  if (!group) return null;
  return {
    title, domain: report.domain, path, group: chartRows(group, fields) ?? group, unit, kind,
    definition: report.definitions?.[path]
      ?? path.split('.').reverse().map((part) => report.definitions?.[part]).find(Boolean)
      ?? `${title}: ${unit} grouped by category.`,
  };
}

// Remove only the exact charted branch, not its siblings (for example,
// registration account state and overlapping roles still need optional detail).
function unchartedReport(report: AnalyticsBreakdowns, charts: ChartSpec[]): AnalyticsBreakdowns {
  const groups = structuredClone(report.groups);
  for (const chart of charts.filter((item) => item.domain === report.domain)) {
    const segments = chart.path.split('.');
    let parent: Record<string, unknown> = groups as Record<string, unknown>;
    for (const segment of segments.slice(0, -1)) {
      const child = parent[segment];
      if (!child || typeof child !== 'object' || Array.isArray(child)) break;
      parent = child as Record<string, unknown>;
    }
    delete parent[segments[segments.length - 1]];
  }
  // Popularity's primary presentation is the sortable/paginated record table.
  if (report.domain === 'traffic') delete (groups as Record<string, unknown>).top_providers;
  return { ...report, groups };
}

function domainTitle(domain: AnalyticsDomain) {
  return ({ traffic: 'Traffic', registrations: 'Registrations', providers: 'Provider inventory', applications: 'Applications', invitations: 'Invitations', reviews: 'Reviews', feedback: 'Private feedback', enquiries: 'Enquiries', subscribers: 'Subscribers' })[domain];
}

function domainSeries(tab: TabId) {
  return SERIES_BY_TAB[tab] ?? [];
}

export function AnalyticsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = validTab(searchParams.get('section'));
  const filters = useMemo(() => getFilters(searchParams), [searchParams]);
  const requestFilters = useMemo(() => queryFor(filters, tab), [filters, tab]);
  const [status, setStatus] = useState<PageStatus>('loading');
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [series, setSeries] = useState<Record<string, AnalyticsSeries>>({});
  const [breakdowns, setBreakdowns] = useState<Record<string, AnalyticsBreakdowns>>({});
  const [ranking, setRanking] = useState<ProviderRankingResponse | null>(null);
  const [partialError, setPartialError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [sortBy, setSortBy] = useState<AnalyticsSort>('profile_views');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [providerSearch, setProviderSearch] = useState(filters.provider_search ?? '');
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [trendChoice, setTrendChoice] = useState('');
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [inventoryRequested, setInventoryRequested] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const requestSequence = useRef(0);
  const selectedTrend = domainSeries(tab).includes(trendChoice) ? trendChoice : domainSeries(tab)[0];
  const incompleteRange = filters.preset === 'custom' && (!filters.date_from || !filters.date_to);
  const reversedRange = filters.preset === 'custom' && !!filters.date_from && !!filters.date_to && filters.date_from > filters.date_to;

  useEffect(() => setProviderSearch(filters.provider_search ?? ''), [filters.provider_search]);

  const updateQuery = useCallback((updates: Record<string, string | undefined>, resetPage = true) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    if (resetPage) next.delete('page');
    setSearchParams(next, { replace: true });
    if (resetPage) setPage(1);
  }, [searchParams, setSearchParams]);

  const load = useCallback(async (isRefresh = false) => {
    const requestId = ++requestSequence.current;
    if (isRefresh) setRefreshing(true);
    else setStatus('loading');
    setError(null);
    setPartialError(null);
    setRanking(null);
    if (incompleteRange || reversedRange) {
      setSummary(null);
      setSeries({});
      setBreakdowns({});
      setRanking(null);
      setStatus('success');
      setRefreshing(false);
      return;
    }
    const currentTab = tab;
    const scoped = requestFilters;
    const domains = (TABS.find((item) => item.id === currentTab)?.domains ?? [])
      .filter((domain) => domain !== 'providers' || inventoryRequested);
    const metricKeys = selectedTrend ? [selectedTrend] : [];
    try {
      const summaryPromise = getAnalyticsSummary(scoped);
      const breakdownPromises = domains.map(async (domain) => [domain, await getAnalyticsBreakdowns(domain, queryForDomain(scoped, domain))] as const);
      const seriesPromises = metricKeys.map(async (metric) => [metric, await getAnalyticsSeries(metric, queryForMetric(scoped, metric))] as const);
      const rankingPromise = currentTab === 'providers' || currentTab === 'traffic'
        ? getProviderRanking({ ...queryForDomain(scoped, 'providers'), page: Number(searchParams.get('page') ?? page), page_size: pageSize, sort: sortBy, sort_direction: sortDirection })
        : Promise.resolve(null);
      const results = await Promise.allSettled([summaryPromise, ...breakdownPromises, ...seriesPromises, rankingPromise]);
      if (requestId !== requestSequence.current) return;
      const summaryResult = results[0];
      if (summaryResult.status === 'rejected') throw summaryResult.reason;
      const data = summaryResult.value as AnalyticsSummary;
      setSummary(data);
      const nextBreakdowns: Record<string, AnalyticsBreakdowns> = {};
      const nextSeries: Record<string, AnalyticsSeries> = {};
      let cursor = 1;
      breakdownPromises.forEach(() => {
        const result = results[cursor++];
        if (result.status === 'fulfilled') {
          const [domain, report] = result.value as readonly [AnalyticsDomain, AnalyticsBreakdowns];
          nextBreakdowns[domain] = report;
        }
      });
      seriesPromises.forEach(() => {
        const result = results[cursor++];
        if (result.status === 'fulfilled') {
          const [metric, report] = result.value as readonly [string, AnalyticsSeries];
          nextSeries[metric] = report;
        }
      });
      const rankingResult = results[cursor];
      if (rankingResult?.status === 'fulfilled') {
        const rankingData = rankingResult.value as ProviderRankingResponse | null;
        setRanking(rankingData);
        if (rankingData && rankingData.meta.page !== Number(searchParams.get('page') ?? page)) {
          setPage(rankingData.meta.page);
          const next = new URLSearchParams(searchParams);
          next.set('page', String(rankingData.meta.page));
          setSearchParams(next, { replace: true });
        }
      }
      else if ((currentTab === 'providers' || currentTab === 'traffic') && rankingResult?.status === 'rejected') setPartialError('Provider ranking could not be loaded. Other reporting panels may still be available.');
      const rejectedPanels = results.slice(1).filter((result) => result.status === 'rejected').length;
      if (rejectedPanels) setPartialError(`${rejectedPanels} report panel${rejectedPanels === 1 ? '' : 's'} could not be loaded. Retry to reload the affected data.`);
      setBreakdowns(nextBreakdowns);
      setSeries(nextSeries);
      setStatus('success');
    } catch (err) {
      if (requestId !== requestSequence.current) return;
      setError(extractErrorMessage(err, 'Analytics could not be loaded.'));
      setStatus('error');
    } finally {
      if (requestId === requestSequence.current) setRefreshing(false);
    }
  }, [page, pageSize, requestFilters, searchParams, setSearchParams, sortBy, sortDirection, tab, selectedTrend, incompleteRange, reversedRange, inventoryRequested]);

  useEffect(() => {
    void load();
    return () => { requestSequence.current += 1; };
  }, [load]);

  const selectedDomains = TABS.find((item) => item.id === tab)?.domains ?? [];
  const availableCharts = useMemo<ChartSpec[]>(() => Object.entries(breakdowns).flatMap(([domain, report]) => {
    const specs: Array<ChartSpec | null> = [];
    const add = (title: string, paths: string[], unit: string, kind: ChartSpec['kind'] = 'bars', fields?: string[]) => {
      specs.push(makeChart(report, title, paths, unit, kind, fields));
    };
    if (domain === 'providers') {
      add('Current provider inventory by status', ['providers.current_inventory.status', 'current_inventory.status', 'inventory.status', 'provider_status', 'status'], 'providers');
      add('Current provider inventory by type', ['providers.current_inventory.type', 'current_inventory.type', 'inventory.type', 'provider_type', 'type'], 'providers');
      add('Current publication state', ['providers.current_inventory.publication', 'current_inventory.publication', 'inventory.publication', 'publication_status', 'publication'], 'providers');
    }
    if (domain === 'registrations') {
      add('Member cohort by exclusive role', ['registrations.selected_cohort.roles', 'selected_cohort.roles', 'selected_cohort.exclusive_roles', 'selected_cohort.role_breakdown'], 'accounts');
      add('Registration cohort by current verification', ['registrations.selected_cohort.verification', 'selected_cohort.verification', 'selected_cohort.verified', 'selected_cohort.verification_state'], 'accounts');
      add('Registration cohort by current account state', ['registrations.selected_cohort.account_state', 'selected_cohort.account_state', 'selected_cohort.active', 'selected_cohort.account_status'], 'accounts');
    }
    if (domain === 'applications') {
      add('Applications submitted in this period · current status', ['submitted_cohort_current_status', 'applications.submitted_cohort_current_status'], 'applications');
      add('All applications · current status', ['all_current_status', 'applications.all_current_status'], 'applications');
      add('Recorded application decisions', ['period_decisions', 'applications.period_decisions'], 'decisions');
    }
    if (domain === 'invitations') {
      add('Invitations created in this period · current status', ['created_cohort_current_status', 'invitations.created_cohort_current_status'], 'invitations');
      add('All invitations · current status', ['all_current_status', 'invitations.all_current_status'], 'invitations');
    }
    if (domain === 'reviews') {
      add('Eligible ratings by star', ['reviews.star_distribution', 'star_distribution', 'eligible_star_distribution'], 'eligible ratings', 'columns');
      add('Active reviews by moderation status', ['active_moderation_status', 'reviews.active_moderation_status', 'moderation_status', 'moderation_states'], 'undeleted reviews');
      add('Selected-period review cohort · current moderation status', ['submitted_cohort_current_status', 'reviews.submitted_cohort_current_status'], 'reviews');
      add('Recorded review actions · edits and moderation are not submissions', ['reviews.period_actions', 'period_actions', 'review_actions', 'review_action_counts'], 'actions');
      add('Top-reviewed providers · current eligible ratings', ['reviews.top_reviewed_providers', 'top_reviewed_providers', 'top_reviewed_provider_leaders'], 'eligible ratings', 'bars', ['rating_count', 'count', 'value']);
      add('Top providers by review submissions in this period', ['reviews.period_submission_leaders', 'period_submission_leaders', 'selected_period_submission_leaders', 'top_review_submissions'], 'submissions', 'bars', ['review_submissions', 'submissions', 'count', 'value']);
    }
    if (domain === 'feedback') {
      add('Private feedback submissions by category', ['feedback.categories', 'categories', 'submission_categories', 'feedback_categories'], 'submissions');
      add('Selected-period feedback cohort · current status', ['submitted_cohort_current_status', 'feedback.submitted_cohort_current_status'], 'feedback records');
      add('Private feedback by current backlog status', ['current_status', 'feedback.current_status', 'current_backlog', 'feedback_status'], 'feedback records');
      add('Optional feedback ratings · response counts', ['ratings.distribution', 'feedback.ratings.distribution', 'rating_distribution', 'response_ratings'], 'rated responses', 'columns');
    }
    if (domain === 'traffic') {
      add('Page views by public page category', ['page_categories', 'traffic.page_categories', 'page_category_totals', 'page_views_by_category', 'traffic_categories'], 'page views');
    }
    if (domain === 'enquiries') add('Accepted enquiries by type', ['enquiry_type', 'enquiries.enquiry_type', 'enquiry_types', 'types'], 'accepted records');
    if (domain === 'subscribers') add('Unique stored subscribers by type', ['subscriber_type', 'subscribers.subscriber_type', 'subscriber_types', 'types'], 'subscriptions');
    return specs.filter((spec): spec is ChartSpec => spec !== null);
  }), [breakdowns]);

  const curatedTitles: Record<TabId, string[]> = {
    overview: [],
    traffic: ['Page views by public page category'],
    registrations: ['Member cohort by exclusive role', 'Registration cohort by current verification'],
    providers: ['Applications submitted in this period · current status', 'Invitations created in this period · current status'],
    reviews: ['Eligible ratings by star', 'Private feedback submissions by category'],
    engagement: ['Accepted enquiries by type', 'Unique stored subscribers by type'],
  };
  const curatedCharts = availableCharts.filter((chart) => curatedTitles[tab].includes(chart.title)).slice(0, 2);
  const metrics = summary ? headlineMetrics(summary, tab) : [];
  const eligibleCountFor = (metric: AnalyticsMetric) => {
    const key = metric.key === 'eligible_review_rating_average' ? 'eligible_review_rating_count'
      : metric.key === 'feedback_rating_average' ? 'feedback_rated_response_count' : null;
    return key ? Object.values(summary?.sections ?? {}).flatMap((section) => section.metrics ?? []).find((item) => item.key === key) : undefined;
  };
  const activeFilters = FILTER_KEYS.filter((key) => Boolean(filters[key]));
  const filterLabel = (key: FilterKey) => key === 'provider_id' ? 'Provider record' : key === 'specialization_id' ? 'Specialization' : displayLabel(key);
  const summaryDetails: AnalyticsBreakdowns[] = summary && tab !== 'overview' ? Object.entries(summary.sections)
    .filter(([key]) => (tab === 'providers' ? ['providers', 'applications', 'invitations'] : tab === 'reviews' ? ['reviews', 'feedback'] : tab === 'engagement' ? ['engagement'] : [tab]).includes(key))
    .map(([key, section]) => ({
      domain: (key === 'engagement' ? 'enquiries' : key) as AnalyticsDomain,
      timezone: summary.timezone, period: summary.period, coverage: section.coverage ?? { available: true },
      groups: {
        ...(section.legacy_compatible_invitation_totals ? { legacy_compatible_invitation_totals: section.legacy_compatible_invitation_totals } : {}),
        secondary_metrics: (section.metrics ?? []).filter((metric) => !HEADLINES[tab].includes(metric.key) && key !== 'providers').map((metric) => ({
          label: `${displayLabel(metric.key)} (${metric.unit}) · ${metric.basis === 'current' ? 'current snapshot' : 'selected period'}`,
          value: metric.available === false ? null : metric.value,
        })),
      },
    })) : [];

  const filterField = (key: FilterKey, label: string, options: Array<[string, string]>, supported: boolean) => supported && (
    <label className={styles.filterField} key={key}>{label}
      <select value={filters[key] ?? ''} onChange={(event) => updateQuery({ [key]: event.target.value || undefined })}>
        <option value="">All</option>{options.map(([value, optionLabel]) => <option key={value} value={value}>{optionLabel}</option>)}
      </select>
    </label>
  );
  const supportsProviders = ['traffic', 'providers', 'reviews'].includes(tab);
  const supportsMembers = tab === 'registrations';
  const supportsApplications = tab === 'providers';
  const supportsFeedback = tab === 'reviews';
  const supportsEngagement = tab === 'engagement';
  const currentTrendMetric = selectedTrend;
  const currentDomain = selectedDomains[0];
  const showProviderRanking = tab === 'providers' || tab === 'traffic';

  const exportClick = async (dataset: 'series' | 'breakdowns' | 'provider-ranking', requestedDomain = currentDomain, requestedMetric = currentTrendMetric) => {
    const metric = requestedMetric;
    setExporting(true);
    setExportMessage(null);
    try {
      const scoped = dataset === 'series' ? queryForMetric(requestFilters, metric)
        : queryForDomain(requestFilters, dataset === 'provider-ranking' ? 'providers' : requestedDomain!);
      await exportAnalytics({ ...scoped, dataset, ...(dataset === 'series' ? { metric } : {}), ...(dataset === 'breakdowns' ? { domain: requestedDomain } : {}), ...(dataset === 'provider-ranking' ? { sort: sortBy, sort_direction: sortDirection } : {}) });
      setExportMessage('CSV downloaded.');
    } catch (exportError) {
      setExportMessage(extractErrorMessage(exportError, 'CSV export failed. Try again.'));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className={styles.shell}>
      <PageHeader title="Analytics" subtitle="A measured view of discovery, operations and community activity." breadcrumbs={[{ label: 'Admin' }, { label: 'Analytics' }]} />
      <main className={styles.body}>
        <section className={styles.controlDeck} aria-label="Analytics controls">
          <div className={styles.controlsTop}>
            <div className={styles.scopeIntro}><span className={styles.eyebrow}>Reporting workspace</span><p>Date-scoped events stay separate from present-day snapshots.</p></div>
            <div className={styles.actions}>
              <button type="button" className={styles.secondaryButton} disabled={refreshing || status === 'loading'} onClick={() => void load(true)}>{refreshing ? 'Refreshing…' : '↻ Refresh'}</button>
              <details className={styles.exportMenu}><summary>{exporting ? 'Preparing CSV…' : 'Export CSV'}</summary><div className={styles.exportOptions}>
                {domainSeries(tab).map((metric) => <button type="button" key={metric} disabled={exporting} onClick={() => void exportClick('series', undefined, metric)}>Time series · {displayLabel(metric)}</button>)}
                {selectedDomains.map((domain) => <button type="button" key={domain} disabled={exporting} onClick={() => void exportClick('breakdowns', domain)}>Breakdown · {domainTitle(domain)}</button>)}
                <button type="button" disabled={!showProviderRanking || exporting} onClick={() => void exportClick('provider-ranking')}>Provider ranking</button>
              </div></details>
            </div>
          </div>
          {exportMessage && <p role="status" className={styles.exportStatus}>{exportMessage}</p>}
          <nav className={styles.tabs} aria-label="Analytics sections" role="tablist" onKeyDown={(event) => {
            if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const current = TABS.findIndex((item) => item.id === tab);
            const targetIndex = event.key === 'Home' ? 0 : event.key === 'End' ? TABS.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length;
            const target = TABS[targetIndex];
            (event.currentTarget.children[targetIndex] as HTMLButtonElement | undefined)?.focus();
            updateQuery({ section: target.id === 'overview' ? undefined : target.id });
          }}>
            {TABS.map((item) => <button key={item.id} id={`analytics-tab-${item.id}`} type="button" role="tab" aria-controls="analytics-panel" tabIndex={tab === item.id ? 0 : -1} aria-selected={tab === item.id} className={tab === item.id ? styles.activeTab : ''} onClick={() => updateQuery({ section: item.id === 'overview' ? undefined : item.id })}>{item.label}</button>)}
          </nav>
          <div className={styles.filterRow}>
            <label className={styles.filterField}>Date range<select value={filters.preset} onChange={(event) => updateQuery({ preset: event.target.value, date_from: undefined, date_to: undefined })}>{PRESETS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            {filters.preset === 'custom' && <>
              <label className={styles.filterField}>From<input type="date" value={filters.date_from ?? ''} onChange={(event) => updateQuery({ date_from: event.target.value || undefined })} /></label>
              <label className={styles.filterField}>Through<input type="date" value={filters.date_to ?? ''} onChange={(event) => updateQuery({ date_to: event.target.value || undefined })} /></label>
            </>}
            <label className={styles.filterField}>Group by<select value={filters.group_by} onChange={(event) => updateQuery({ group_by: event.target.value })}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label>
          </div>
          {activeFilters.length > 0 && <div className={styles.activeFilters} aria-label="Active filters">
            {activeFilters.map((key) => <button type="button" key={key} onClick={() => updateQuery({ [key]: undefined })} aria-label={`Remove ${filterLabel(key)} filter`}>
              {filterLabel(key)}: {filters[key]?.replace(/_/g, ' ')}{!requestFilters[key] ? ' (not used in this section)' : ''} <span aria-hidden="true">×</span>
            </button>)}
            <button type="button" onClick={() => updateQuery(Object.fromEntries(FILTER_KEYS.map((key) => [key, undefined])))}>Clear all filters</button>
            <p>Filters apply only to matching datasets, not unrelated metrics or sitewide traffic.</p>
          </div>}
          <details className={styles.disclosure} open={filtersOpen} onToggle={(event) => setFiltersOpen(event.currentTarget.open)}>
            <summary>More filters</summary>
            {filtersOpen && <div className={styles.filterRow}>
            {filterField('provider_type', 'Provider type', [['DOCTOR', 'Doctor'], ['CLINIC', 'Clinic'], ['HOSPITAL', 'Hospital']], supportsProviders)}
            {filterField('provider_status', 'Provider status', [['DRAFT', 'Draft'], ['UNDER_REVIEW', 'Under review'], ['ACTIVE', 'Active'], ['INACTIVE', 'Inactive']], ['providers', 'reviews'].includes(tab))}
            {filterField('publication_status', 'Publication', [['PUBLISHED', 'Published'], ['UNPUBLISHED', 'Unpublished']], ['providers', 'reviews'].includes(tab))}
            {tab === 'reviews' && <label className={styles.filterField}>Provider name<input maxLength={100} value={filters.provider_search ?? ''} placeholder="Search providers" onChange={(event) => updateQuery({ provider_search: event.target.value || undefined })} /></label>}
            {supportsProviders && <>
              {tab === 'providers' && <>
                <label className={styles.filterField}>Listing country<input value={filters.country ?? ''} placeholder="Recorded country" onChange={(event) => updateQuery({ country: event.target.value || undefined })} /></label>
                <label className={styles.filterField}>Listing city<input value={filters.city ?? ''} placeholder="Recorded city" onChange={(event) => updateQuery({ city: event.target.value || undefined })} /></label>
              </>}
            </>}
            {filterField('member_role', 'Member role', [['horse_owner', 'Horse owner'], ['stable_manager', 'Stable manager'], ['both', 'Both']], supportsMembers)}
            {filterField('member_verified', 'Verification', [['true', 'Verified'], ['false', 'Unverified']], supportsMembers)}
            {filterField('member_active', 'Account', [['true', 'Active'], ['false', 'Inactive']], supportsMembers)}
            {filterField('application_status', 'Application status', [['AWAITING_EMAIL_VERIFICATION', 'Awaiting verification'], ['PENDING_REVIEW', 'Pending review'], ['APPROVED', 'Approved'], ['REJECTED', 'Rejected']], supportsApplications)}
            {filterField('invitation_status', 'Invitation status', [['PENDING', 'Pending'], ['ACCEPTED', 'Accepted'], ['COMPLETED', 'Completed'], ['CANCELLED', 'Cancelled'], ['EXPIRED', 'Expired']], supportsApplications)}
            {filterField('review_status', 'Review moderation', [['PENDING', 'Pending'], ['PUBLISHED', 'Published'], ['HIDDEN', 'Hidden'], ['REJECTED', 'Rejected']], supportsFeedback)}
            {filterField('rating', 'Star rating', [1, 2, 3, 4, 5].map((value) => [String(value), `${value} star${value === 1 ? '' : 's'}`]), supportsFeedback)}
            {filterField('feedback_category', 'Feedback category', [['Website / App', 'Website / App'], ['Search & Matching', 'Search & Matching'], ['Provider Experience', 'Provider Experience'], ['Account / Profile', 'Account / Profile'], ['Technical Issue', 'Technical Issue'], ['Suggestion', 'Suggestion'], ['Other', 'Other']], supportsFeedback)}
            {filterField('feedback_status', 'Feedback state', [['Pending', 'Pending'], ['In review', 'In review'], ['Resolved', 'Resolved'], ['Rejected', 'Rejected'], ['withdrawn', 'Withdrawn']], supportsFeedback)}
            {filterField('enquiry_type', 'Enquiry type', [['general', 'General'], ['listing', 'Listing'], ['partnership', 'Partnership'], ['other', 'Other']], supportsEngagement)}
            {filterField('subscriber_type', 'Subscriber type', [['VET', 'Vet'], ['HORSE_OWNER', 'Horse owner'], ['HOSPITAL', 'Hospital'], ['CLINIC', 'Clinic'], ['STABLE_MANAGER', 'Stable manager'], ['OTHER', 'Other']], supportsEngagement)}
            {tab === 'overview' && <p className={styles.filterScope}>Choose a detailed section to add filters. Existing section filters affect matching reports only.</p>}
            <p className={styles.filterScope}>Provider filters affect provider-linked reports only. Member filters affect registration cohorts; they do not narrow sitewide traffic.</p>
            <button type="button" className={styles.resetButton} onClick={() => setSearchParams(new URLSearchParams(tab === 'overview' ? '' : `section=${tab}`), { replace: true })}>Reset filters</button>
            </div>}
          </details>
          {summary && <div className={styles.metaLine}><span>{summary.period.date_from} – {summary.period.date_to} · <strong>{summary.timezone}</strong></span><span>Last refreshed <strong>{new Date(summary.refreshed_at).toLocaleString(undefined, { timeZone: summary.timezone, timeZoneName: 'short' })}</strong></span></div>}
        </section>

        <div role="tabpanel" id="analytics-panel" aria-labelledby={`analytics-tab-${tab}`} tabIndex={0} aria-busy={status === 'loading'}>
        {status === 'loading' && !summary && <div className={styles.loading}><div className={styles.skeletonBlock} /><div className={styles.skeletonGrid}><i /><i /><i /><i /></div><LoadingSpinner size="lg" label="Loading analytics reports…" /></div>}
        {status === 'error' && !summary && <ErrorState title="Analytics unavailable" message={error ?? undefined} onRetry={() => void load()} />}
        {partialError && <div className={styles.partialNotice} role="status"><span>{partialError}</span><button type="button" onClick={() => void load(true)}>Retry reports</button></div>}
        {status === 'loading' && summary && <div className={styles.updateNotice} role="status">Updating reports for the applied filters…</div>}
        {incompleteRange && <div className={styles.partialNotice} role="status">Choose both start and end dates in {summary?.timezone ?? 'the configured system timezone'} to run this custom range.</div>}
        {reversedRange && <div className={styles.partialNotice} role="status">The start date must be on or before the end date. Correct the dates to run this report.</div>}
        {summary && <>
          {status === 'error' && <div className={styles.partialNotice} role="alert">{error} Showing the previous successful report, not updated results for the selected filters.<button type="button" onClick={() => void load(true)}>Retry summary</button></div>}
          <section className={styles.metricGroup} aria-label="Headline metrics"><div className={`${styles.metricGrid} ${tab === 'overview' ? styles.overviewMetrics : ''}`}>{metrics.map((metric) => <MetricCard key={metric.key} metric={metric} eligibleCount={eligibleCountFor(metric)} />)}</div></section>
          {tab === 'overview' && <nav className={styles.sectionLinks} aria-label="Detailed analytics">
            {TABS.filter((item) => item.id !== 'overview').map((item) => <Link key={item.id} to={`?${new URLSearchParams({ ...Object.fromEntries(searchParams), section: item.id, page: '1' })}`}>{item.label} →</Link>)}
          </nav>}
          {(tab === 'overview' || tab === 'traffic') && (summary.sections.traffic?.coverage?.partial || summary.sections.traffic?.coverage?.available === false || summary.sections.traffic?.metrics?.some((metric) => metric.available === false || metric.partial_coverage)) && <p className={styles.partialNotice} role="status">Traffic is partial or unavailable for this period. Uncovered dates are not zero activity.</p>}
          <details className={styles.disclosure}><summary>Definitions & source coverage</summary>
          <p className={styles.privacyNote}>Available does not guarantee complete history. First and last retained business-event dates below are observations, not guaranteed collection coverage. Traffic tracking {summary.tracking_started_date ? `started ${summary.tracking_started_date}` : 'boundary is unknown'}.</p>
          {Object.entries(summary.coverage ?? {}).map(([source, coverage]) => <p className={styles.coverageObservation} key={source}>{displayLabel(source)}: {coverage.available ? `${coverage.from ?? 'Start unknown'} – ${coverage.through ?? 'End unknown'}${coverage.partial ? ' · partial' : ''}` : 'Unavailable'}</p>)}
          {tab === 'traffic' && <p className={styles.privacyNote}>Estimated visitors are browser-deduplicated daily estimates, not verified people. Devices and storage resets may overcount; unavailable storage may undercount. Multi-day totals are visitor-days. Directory and profile views count successful member-page views only. Legacy homepage visits remain separate.</p>}
          {tab === 'providers' && <div className={styles.snapshotNotice}><strong>Inventory, publication, ratings and saved counts are current snapshots.</strong> Active and publicly discoverable (active + published) providers are distinct; historical provider states are not reconstructed. Invitation compatibility totals group accepted with completed; cancelled and expired invitations are not recipient rejections.</div>}
          {tab === 'registrations' && <div className={styles.snapshotNotice}>Registration totals count public member accounts once. The “Both” role is exclusive; role assignment totals may overlap. Provider applicants are reported separately.</div>}
          {tab === 'reviews' && <div className={styles.snapshotNotice}>Eligible public ratings include published and hidden approved reviews. Pending and rejected reviews do not affect ratings. Feedback is private and separate from provider reviews; messages and notes are never shown here.</div>}
          {tab === 'engagement' && <div className={styles.snapshotNotice}>Enquiries count durably accepted records, independent of email delivery. Subscribers count unique stored records, not repeated form attempts.</div>}
          <section className={styles.definitionFooter}><h2>Reading this report</h2><p>Period metrics count events in the selected inclusive calendar range. Current metrics are live snapshots, not historical populations. Comparison uses an equally long preceding period and is omitted when source coverage is incomplete or its baseline is zero. Analytics contain aggregate reporting only—no contact details, personal browsing records or private message content.</p></section>
          </details>
          {tab !== 'overview' && <label className={styles.trendSelector}>Trend metric<select value={selectedTrend} onChange={(event) => setTrendChoice(event.target.value)}>{domainSeries(tab).map((metric) => <option value={metric} key={metric}>{displayLabel(metric)}</option>)}</select></label>}
          <div className={styles.trendPanel}>
            {Object.entries(series).map(([metric, report]) => <div key={metric}>
              {report.available === false && <p role="status" className={styles.partialNotice}>{displayLabel(metric)} trend is unavailable for this period. Uncovered dates are not zero activity.</p>}
              <AnalyticsChart title={`${displayLabel(metric)} over time`} description={report.partial_coverage ? `Partial coverage · ${report.timezone} · uncovered dates are not zero activity.` : `${report.timezone} · ${filters.group_by} buckets`} points={report.data} kind="trend" unit={report.unit} />
            </div>)}
          </div>
          <div className={styles.chartsGrid}>
            {curatedCharts.map((chart) => <AnalyticsChart key={chart.title} title={chart.title} definition={chart.definition} group={chart.group} kind={chart.kind} unit={chart.unit} />)}
            {Object.keys(series).length === 0 && availableCharts.length === 0 && status === 'success' && <Card padding="md" shadow="sm" className={styles.coverageEmpty}><h3>No chartable reports in this selection</h3><p>Source coverage or filters may limit available breakdowns. Use the metric definitions above to interpret covered counts.</p></Card>}
          </div>
          {tab !== 'overview' && <details className={styles.disclosure} open={detailsOpen} onToggle={(event) => {
            setDetailsOpen(event.currentTarget.open);
            if (event.currentTarget.open && tab === 'providers') setInventoryRequested(true);
          }}>
            <summary>View detailed reports</summary>
            {detailsOpen && <>
              <AnalyticsBreakdownTables reports={Object.values(breakdowns).map((report) => unchartedReport(report, curatedCharts))} />
              <AnalyticsBreakdownTables reports={summaryDetails} title="Additional summary detail" variant="metrics" />
            </>}
          </details>}
          {showProviderRanking && <>
            {partialError && !ranking && <ErrorState title="Provider ranking unavailable" message={partialError} onRetry={() => void load(true)} />}
            {(ranking || status === 'loading') && <ProviderRankingTable report={ranking} loading={status === 'loading'} search={providerSearch} onSearch={(value) => { setProviderSearch(value); updateQuery({ provider_search: value || undefined }); setPage(1); }} sortBy={sortBy} sortDirection={sortDirection} onSort={(key) => { setSortDirection(sortBy === key && sortDirection === 'desc' ? 'asc' : 'desc'); setSortBy(key); setPage(1); updateQuery({ page: undefined }, false); }} page={ranking?.meta.page ?? page} pageSize={ranking?.meta.page_size ?? pageSize} onPage={(value) => { setPage(value); updateQuery({ page: String(value) }, false); }} onPageSize={(value) => { setPageSize(value); setPage(1); updateQuery({ page: '1' }, false); }} />}
          </>}
          {tab === 'registrations' && <p className={styles.drillLink}>Need the underlying account records? <Link to="/admin/users">Open registered users →</Link></p>}
          {tab === 'providers' && <p className={styles.drillLink}>Manage provider records <Link to="/admin/providers">Open provider directory →</Link> · <Link to="/admin/provider-applications">Review applications →</Link> · <Link to="/admin/invitations">Manage invitations →</Link></p>}
          {tab === 'reviews' && <p className={styles.drillLink}><Link to="/admin/reviews">Open review moderation →</Link> · <Link to="/admin/feedback">Open private feedback management →</Link></p>}
          {tab === 'engagement' && <p className={styles.drillLink}><Link to="/admin/contact-enquiries">Open enquiries →</Link> · <Link to="/admin/subscribers">Open subscribers →</Link></p>}
        </>}
        </div>
      </main>
    </div>
  );
}