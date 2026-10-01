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
import type { AnalyticsBreakdowns, AnalyticsDomain, AnalyticsFilters, AnalyticsGroup, AnalyticsGrouping, AnalyticsPreset, AnalyticsSeries, AnalyticsSort, AnalyticsSummary, ProviderRankingResponse } from '@/types/analytics';
import styles from './AnalyticsPage.module.css';

const TABS = [
  { id: 'overview', label: 'Overview', domains: [] as AnalyticsDomain[] },
  { id: 'traffic', label: 'Traffic & Discovery', domains: ['traffic'] as AnalyticsDomain[] },
  { id: 'registrations', label: 'Registrations', domains: ['registrations'] as AnalyticsDomain[] },
  { id: 'providers', label: 'Providers & Applications', domains: ['providers', 'applications', 'invitations'] as AnalyticsDomain[] },
  { id: 'reviews', label: 'Reviews & Feedback', domains: ['reviews', 'feedback'] as AnalyticsDomain[] },
  { id: 'engagement', label: 'Enquiries & Subscribers', domains: ['enquiries', 'subscribers'] as AnalyticsDomain[] },
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
  public_member_registrations: 'New member registrations', verified_registrations: 'Verified registrations',
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

function MetricCard({ metric }: { metric: AnalyticsSummary['sections'][string]['metrics'] extends (infer T)[] | undefined ? T : never }) {
  const value = metric.value === null || metric.available === false ? 'Unavailable' : metric.value.toLocaleString();
  const comparison = metric.comparison;
  return (
    <Card padding="md" shadow="sm" className={styles.metricCard}>
      <div className={styles.metricTop}>
        <span className={styles.metricLabel}>{metric.label ?? displayLabel(metric.key)}</span>
        <span className={metric.basis === 'current' ? styles.snapshotTag : styles.periodTag}>{metric.basis === 'current' ? 'Snapshot' : 'Selected period'}</span>
      </div>
      <strong className={styles.metricValue}>{value}<small>{metric.value !== null && metric.available !== false ? ` ${metric.unit}` : ''}</small></strong>
      {comparison && metric.basis === 'period' && (
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

function countCards(value: unknown, prefix: string, basis: 'period' | 'current' = 'current'): Array<{
  key: string; label: string; value: number; unit: string; basis: 'period' | 'current'; definition: string;
}> {
  if (typeof value === 'number') return [{ key: prefix, label: displayLabel(prefix), value, unit: 'records', basis, definition: `${displayLabel(prefix)} aggregate count.` }];
  if (Array.isArray(value)) return value.flatMap((row, index) => {
    if (!row || typeof row !== 'object') return [];
    const item = row as Record<string, unknown>;
    const label = String(item.label ?? item.name ?? item.status ?? item.category ?? item.type ?? item.rating ?? `Item ${index + 1}`);
    const count = item.value ?? item.count ?? item.total;
    if (typeof count === 'number') return [{ key: `${prefix}_${label}`, label: `${displayLabel(prefix)} · ${label}`, value: count, unit: 'records', basis, definition: `${displayLabel(prefix)} breakdown count for ${label}.` }];
    return [];
  });
  if (value && typeof value === 'object') {
    const object = value as Record<string, unknown>;
    const namedCount = object.value ?? object.count ?? object.total;
    if (typeof namedCount === 'number') {
      const label = String(object.label ?? object.name ?? object.status ?? object.category ?? prefix);
      return [{ key: `${prefix}_${label}`, label: displayLabel(label), value: namedCount, unit: 'records', basis, definition: `${displayLabel(prefix)} aggregate count.` }];
    }
    return Object.entries(object).flatMap(([key, child]) => countCards(child, `${prefix}_${key}`, basis));
  }
  return [];
}

const OVERVIEW_PRIORITY_METRICS = new Set([
  'website_page_views', 'estimated_visitor_days', 'latest_daily_visitor_estimate',
  'directory_views', 'provider_profile_views', 'public_member_registrations',
  'provider_applications', 'contact_enquiries', 'new_subscribers',
  'provider_review_submissions', 'platform_feedback_submissions',
]);

function SectionCards({ summary, sectionKeys, compact = false }: { summary: AnalyticsSummary; sectionKeys: string[]; compact?: boolean }) {
  return <div className={styles.groups}>
    {sectionKeys.map((key) => {
      const section = summary.sections[key];
      if (!section) return null;
      const metrics = (section.metrics ?? []).filter((metric) => !compact || OVERVIEW_PRIORITY_METRICS.has(metric.key));
      const flatInventory = section.inventory && typeof section.inventory === 'object'
        ? Object.entries(section.inventory).flatMap(([name, value]) => {
          if (compact && !['total', 'active', 'active_published'].includes(name)) return [];
          if (typeof value === 'number') return [{ key: name, label: displayLabel(name), value, unit: 'providers', basis: 'current' as const, definition: `Current provider inventory snapshot: ${displayLabel(name).toLowerCase()}.` }];
          if (value && typeof value === 'object' && !Array.isArray(value)) {
            return Object.entries(value as Record<string, unknown>).filter(([, count]) => typeof count === 'number').map(([child, count]) => ({
              key: `${name}_${child}`,
              label: `${displayLabel(name)} · ${displayLabel(child)}`,
              value: count as number,
              unit: 'providers',
              basis: 'current' as const,
              definition: `Current provider inventory snapshot: ${displayLabel(child).toLowerCase()} ${displayLabel(name).toLowerCase()}.`,
            }));
          }
          return [];
        })
        : [];
      const cohortState = compact ? undefined : section.cohort_current_state;
      const cohortCards = cohortState ? [
        ...(typeof cohortState.total === 'number' ? countCards(cohortState.total, 'registration cohort total') : []),
        ...countCards(cohortState.roles, 'exclusive member role', 'current'),
        ...countCards(cohortState.verified, 'registration cohort verification state', 'current'),
        ...countCards(cohortState.active, 'registration cohort account state', 'current'),
        ...countCards(cohortState.role_assignments, 'role assignments · may overlap', 'current'),
      ] : [];
      const statusCards = compact ? [] : [
        ...countCards(section.current_status, 'current status'),
        ...countCards(section.submitted_cohort_status, 'selected-period application cohort status', 'period'),
        ...countCards(section.invitation_status, 'current invitation status'),
        ...countCards(section.invitation_cohort_status, 'selected-period invitation cohort status', 'period'),
        ...countCards(section.legacy_compatible_invitation_totals, 'legacy-compatible invitation summary'),
        ...countCards(section.enquiry_types, 'period enquiry type', 'period'),
        ...countCards(section.subscriber_types, 'period subscriber type', 'period'),
        ...countCards(section.categories, 'period feedback category', 'period'),
        ...countCards(section.star_distribution, 'eligible ratings by star'),
        ...countCards(section.retained_deleted_history, 'retained deleted review history'),
      ];
      const allMetrics = [...metrics, ...flatInventory, ...cohortCards, ...statusCards];
      if (!allMetrics.length) return null;
      return <section key={key} className={styles.metricGroup} aria-labelledby={`group-${key}`}>
        <div className={styles.groupHeading}><h2 id={`group-${key}`}>{sectionTitle(key)}</h2><span>{metrics.some((m) => m.basis === 'current') || flatInventory.length ? 'Current state and period activity' : 'Selected date range'}</span></div>
        <div className={styles.metricGrid}>{allMetrics.map((metric) => <MetricCard key={metric.key} metric={metric} />)}</div>
      </section>;
    })}
  </div>;
}

function sectionTitle(key: string) {
  return ({ traffic: 'Traffic & discovery', registrations: 'Member registrations', providers: 'Provider inventory', applications: 'Applications & invitations', reviews: 'Provider reviews', feedback: 'Private platform feedback', engagement: 'Enquiries & subscribers' } as Record<string, string>)[key] ?? key.replace(/_/g, ' ');
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
    title, group: chartRows(group, fields) ?? group, unit, kind,
    definition: report.definitions?.[path]
      ?? path.split('.').reverse().map((part) => report.definitions?.[part]).find(Boolean)
      ?? `${title}: ${unit} grouped by category.`,
  };
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
  const requestSequence = useRef(0);

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
    isRefresh ? setRefreshing(true) : setStatus('loading');
    setError(null);
    setPartialError(null);
    setRanking(null);
    if (filters.preset === 'custom' && (!filters.date_from || !filters.date_to)) {
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
    const domains = TABS.find((item) => item.id === currentTab)?.domains ?? [];
    const metricKeys = domainSeries(currentTab);
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
      breakdownPromises.forEach((_promise, index) => {
        const result = results[cursor++];
        if (result.status === 'fulfilled') {
          const [domain, report] = result.value as readonly [AnalyticsDomain, AnalyticsBreakdowns];
          nextBreakdowns[domain] = report;
        }
      });
      seriesPromises.forEach((_promise, index) => {
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
  }, [filters, page, pageSize, requestFilters, searchParams, sortBy, sortDirection, tab]);

  useEffect(() => {
    void load();
    return () => { requestSequence.current += 1; };
  }, [load]);

  const allSections = tab === 'overview'
    ? ['traffic', 'registrations', 'providers', 'applications', 'reviews', 'feedback', 'engagement']
    : tab === 'traffic' ? ['traffic']
      : tab === 'registrations' ? ['registrations']
        : tab === 'providers' ? ['providers', 'applications']
          : tab === 'reviews' ? ['reviews', 'feedback']
            : ['engagement'];
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
      add('Top providers by profile views', ['top_providers', 'traffic.top_providers'], 'profile views', 'bars', ['profile_views', 'views', 'count', 'value']);
    }
    if (domain === 'enquiries') add('Accepted enquiries by type', ['enquiry_type', 'enquiries.enquiry_type', 'enquiry_types', 'types'], 'accepted records');
    if (domain === 'subscribers') add('Unique stored subscribers by type', ['subscriber_type', 'subscribers.subscriber_type', 'subscriber_types', 'types'], 'subscriptions');
    return specs.filter((spec): spec is ChartSpec => spec !== null);
  }), [breakdowns]);

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
  const hasSegmentFilters = FILTER_KEYS.some((key) => Boolean(filters[key]));
  const currentTrendMetric = domainSeries(tab)[0];
  const currentDomain = selectedDomains[0];
  const showProviderRanking = tab === 'providers' || tab === 'traffic';

  const exportClick = async (dataset: 'series' | 'breakdowns' | 'provider-ranking', requestedDomain = currentDomain, requestedMetric = currentTrendMetric) => {
    const metric = requestedMetric;
    setExporting(true);
    setExportMessage(null);
    try {
      await exportAnalytics({ ...requestFilters, dataset, ...(dataset === 'series' && metric ? { metric, ...queryForMetric(requestFilters, metric) } : {}), ...(dataset === 'breakdowns' && requestedDomain ? { domain: requestedDomain, ...queryForDomain(requestFilters, requestedDomain) } : {}), ...(dataset === 'provider-ranking' ? { ...queryForDomain(requestFilters, 'providers'), sort: sortBy, sort_direction: sortDirection } : {}) });
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
            {filterField('provider_type', 'Provider type', [['DOCTOR', 'Doctor'], ['CLINIC', 'Clinic'], ['HOSPITAL', 'Hospital']], supportsProviders)}
            {filterField('provider_status', 'Provider status', [['DRAFT', 'Draft'], ['UNDER_REVIEW', 'Under review'], ['ACTIVE', 'Active'], ['INACTIVE', 'Inactive']], ['providers', 'reviews'].includes(tab))}
            {filterField('publication_status', 'Publication', [['PUBLISHED', 'Published'], ['UNPUBLISHED', 'Unpublished']], ['providers', 'reviews'].includes(tab))}
            {supportsProviders && <label className={styles.filterField}>Provider name<input maxLength={100} value={filters.provider_search ?? ''} placeholder="Search providers" onChange={(event) => updateQuery({ provider_search: event.target.value || undefined })} /></label>}
            {supportsProviders && <>
              <label className={styles.filterField}>Provider ID<input value={filters.provider_id ?? ''} placeholder="Select by ID" onChange={(event) => updateQuery({ provider_id: event.target.value || undefined })} /></label>
              <label className={styles.filterField}>Specialization ID<input value={filters.specialization_id ?? ''} placeholder="Specialization ID" onChange={(event) => updateQuery({ specialization_id: event.target.value || undefined })} /></label>
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
            {tab === 'overview' && hasSegmentFilters && <p className={styles.filterScope}>Section filters remain applied to matching reports only. Reset them here or return to their section to edit.</p>}
            <p className={styles.filterScope}>Provider filters affect provider-linked reports only. Member filters affect registration cohorts; they do not narrow sitewide traffic.</p>
            <button type="button" className={styles.resetButton} onClick={() => setSearchParams(new URLSearchParams(tab === 'overview' ? '' : `section=${tab}`), { replace: true })}>Reset filters</button>
          </div>
          {summary && <div className={styles.metaLine}><span>Timezone <strong>{summary.timezone}</strong></span><span>Traffic tracking <strong>{summary.tracking_started_date ? `Since ${summary.tracking_started_date}` : 'Coverage varies by source'}</strong></span><span>Sources available <strong>{Object.values(summary.coverage ?? {}).filter((source) => source.available).length} / {Object.keys(summary.coverage ?? {}).length || '—'}</strong></span><details className={styles.coverageDetails}><summary>Coverage by source</summary><p className={styles.coverageNote}>Availability does not imply complete historical coverage; date ranges and partial flags are source-specific.</p><div>{Object.entries(summary.coverage ?? {}).map(([source, coverage]) => <p key={source}><span>{displayLabel(source)}</span><strong>{coverage.available ? `${coverage.from || coverage.through ? `${coverage.from ?? 'Start unknown'}${coverage.through ? ` – ${coverage.through}` : ''}` : 'Available · interval unknown'}${coverage.partial ? ' · partial' : ''}` : 'Unavailable'}</strong></p>)}</div></details><span>Last refreshed <strong>{new Date(summary.refreshed_at).toLocaleString(undefined, { timeZone: summary.timezone, timeZoneName: 'short' })}</strong></span></div>}
        </section>

        <div role="tabpanel" id="analytics-panel" aria-labelledby={`analytics-tab-${tab}`} tabIndex={0} aria-busy={status === 'loading'}>
        {status === 'loading' && !summary && <div className={styles.loading}><div className={styles.skeletonBlock} /><div className={styles.skeletonGrid}><i /><i /><i /><i /></div><LoadingSpinner size="lg" label="Loading analytics reports…" /></div>}
        {status === 'error' && !summary && <ErrorState title="Analytics unavailable" message={error ?? undefined} onRetry={() => void load()} />}
        {partialError && <div className={styles.partialNotice} role="status"><span>{partialError}</span><button type="button" onClick={() => void load(true)}>Retry reports</button></div>}
        {status === 'loading' && summary && <div className={styles.updateNotice} role="status">Updating reports for the applied filters…</div>}
        {filters.preset === 'custom' && (!filters.date_from || !filters.date_to) && <div className={styles.partialNotice} role="status">Choose both start and end dates in {summary?.timezone ?? 'the configured system timezone'} to run this custom range.</div>}
        {summary && <>
          {status === 'error' && <div className={styles.partialNotice} role="alert">{error}<button type="button" onClick={() => void load(true)}>Retry summary</button></div>}
          <SectionCards summary={summary} sectionKeys={allSections} compact={tab === 'overview'} />
          {tab === 'traffic' && <p className={styles.privacyNote}>Estimated visitors are browser-deduplicated daily estimates, not verified people. Devices and storage resets may overcount; unavailable storage may undercount. Multi-day totals are visitor-days. Directory and profile views count successful member-page views only. Legacy homepage visits remain separate.</p>}
          {tab === 'providers' && <div className={styles.snapshotNotice}><strong>Inventory, publication, ratings and saved counts are current snapshots.</strong> Active and publicly discoverable (active + published) providers are distinct; historical provider states are not reconstructed. Invitation compatibility totals group accepted with completed; cancelled and expired invitations are not recipient rejections.</div>}
          {tab === 'registrations' && <div className={styles.snapshotNotice}>Registration totals count public member accounts once. The “Both” role is exclusive; role assignment totals may overlap. Provider applicants are reported separately.</div>}
          {tab === 'reviews' && <div className={styles.snapshotNotice}>Eligible public ratings include published and hidden approved reviews. Pending and rejected reviews do not affect ratings. Feedback is private and separate from provider reviews; messages and notes are never shown here.</div>}
          {tab === 'engagement' && <div className={styles.snapshotNotice}>Enquiries count durably accepted records, independent of email delivery. Subscribers count unique stored records, not repeated form attempts.</div>}
          <div className={styles.chartsGrid}>
            {Object.entries(series).map(([metric, report]) => <AnalyticsChart key={metric} title={`${displayLabel(metric)} over time`} description={report.partial_coverage ? `Available from ${report.coverage.from ?? summary.tracking_started_date ?? 'instrumentation start'}; earlier dates are unavailable.` : `${report.timezone} · ${filters.group_by} buckets`} points={report.data} kind="trend" unit={report.unit} />)}
            {sortBy === 'profile_views' && ranking?.meta.page === 1 && ranking.data.some((row) => row.profile_views_available !== false && row.profile_views !== null) ? <AnalyticsChart title="Top providers by profile views" description={`Selected period · ${ranking.timezone}`} group={ranking.data.filter((row) => row.profile_views_available !== false && row.profile_views !== null).map((row) => ({ label: row.name, value: row.profile_views }))} kind="bars" unit="profile views" /> : null}
            {availableCharts.map((chart) => <AnalyticsChart key={chart.title} title={chart.title} description={chart.unit} definition={chart.definition} group={chart.group} kind={chart.kind} unit={chart.unit} />)}
            {Object.keys(series).length === 0 && availableCharts.length === 0 && status === 'success' && <Card padding="md" shadow="sm" className={styles.coverageEmpty}><h3>No chartable reports in this selection</h3><p>Source coverage or filters may limit available breakdowns. Use the metric definitions above to interpret covered counts.</p></Card>}
          </div>
          <AnalyticsBreakdownTables reports={Object.values(breakdowns)} />
          {showProviderRanking && <>
            {partialError && !ranking && <ErrorState title="Provider ranking unavailable" message={partialError} onRetry={() => void load(true)} />}
            <ProviderRankingTable report={ranking} loading={status === 'loading'} search={providerSearch} onSearch={(value) => { setProviderSearch(value); updateQuery({ provider_search: value || undefined }); setPage(1); }} sortBy={sortBy} sortDirection={sortDirection} onSort={(key) => { setSortDirection(sortBy === key && sortDirection === 'desc' ? 'asc' : 'desc'); setSortBy(key); setPage(1); updateQuery({ page: undefined }, false); }} page={ranking?.meta.page ?? page} pageSize={ranking?.meta.page_size ?? pageSize} onPage={(value) => { setPage(value); updateQuery({ page: String(value) }, false); }} onPageSize={(value) => { setPageSize(value); setPage(1); updateQuery({ page: '1' }, false); }} />
          </>}
          {tab === 'registrations' && <p className={styles.drillLink}>Need the underlying account records? <Link to="/admin/users">Open registered users →</Link></p>}
          {tab === 'providers' && <p className={styles.drillLink}>Manage provider records <Link to="/admin/providers">Open provider directory →</Link> · <Link to="/admin/provider-applications">Review applications →</Link> · <Link to="/admin/invitations">Manage invitations →</Link></p>}
          {tab === 'reviews' && <p className={styles.drillLink}><Link to="/admin/reviews">Open review moderation →</Link> · <Link to="/admin/feedback">Open private feedback management →</Link></p>}
          {tab === 'engagement' && <p className={styles.drillLink}><Link to="/admin/contact-enquiries">Open enquiries →</Link> · <Link to="/admin/subscribers">Open subscribers →</Link></p>}
          <section className={styles.definitionFooter}><h2>Reading this report</h2><p>Period metrics count events in the selected inclusive calendar range. Current metrics are live snapshots, not historical populations. Comparison uses an equally long preceding period and is omitted when source coverage is incomplete or its baseline is zero. Analytics contain aggregate reporting only—no contact details, personal browsing records or private message content.</p></section>
        </>}
        </div>
      </main>
    </div>
  );
}