import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AnalyticsPage } from './AnalyticsPage';

const api = vi.hoisted(() => ({
  getAnalyticsSummary: vi.fn(),
  getAnalyticsSeries: vi.fn(),
  getAnalyticsBreakdowns: vi.fn(),
  getProviderRanking: vi.fn(),
  exportAnalytics: vi.fn(),
}));

vi.mock('@/api/analytics', () => api);

const sampleSummary = {
  timezone: 'America/Toronto',
  period: { preset: 'last_30_days', date_from: '2026-04-01', date_to: '2026-04-30', group_by: 'daily' },
  tracking_started_date: '2026-03-14',
  coverage: { traffic_page_views: { available: true, from: '2026-03-14', through: '2026-04-30' } },
  refreshed_at: '2026-04-30T15:00:00Z',
  sections: {
    traffic: { metrics: [
      { key: 'website_page_views', label: 'Website page views', value: 1837, unit: 'views', basis: 'period', available: true, partial_coverage: false, definition: 'Eligible routes only.', comparison: { available: true, previous_value: 1600, change_percent: 14.8 } },
      { key: 'provider_profile_views', label: 'Provider profile views', value: 239, unit: 'views', basis: 'period', available: true, definition: 'Successful provider profile views.' },
      { key: 'estimated_visitor_days', value: 406, unit: 'visitor-days', basis: 'period', available: true, definition: 'Browser-deduplicated daily estimates.' },
    ] },
    registrations: { metrics: [{ key: 'public_member_registrations', value: 42, unit: 'accounts', basis: 'period', available: true, definition: 'Public member accounts.' }] },
    providers: { inventory: { total: 87, active: 61, active_published: 55, status: { DRAFT: 5, UNDER_REVIEW: 8, INACTIVE: 13 }, publication: { PUBLISHED: 55, UNPUBLISHED: 32 } } },
    applications: { metrics: [{ key: 'provider_applications', value: 8, unit: 'applications', basis: 'period', available: true, definition: 'New provider applications.' }] },
    reviews: { metrics: [
      { key: 'provider_review_submissions', value: 12, unit: 'reviews', basis: 'period', available: true, definition: 'Initial submissions only.' },
      { key: 'eligible_review_rating_average', label: 'Current eligible average rating', value: 4.6, unit: 'stars', basis: 'current', available: true },
      { key: 'eligible_review_rating_count', label: 'Current eligible rating count', value: 11, unit: 'ratings', basis: 'current', available: true },
    ] },
    feedback: { metrics: [
      { key: 'platform_feedback_submissions', value: 5, unit: 'feedback', basis: 'period', available: true, definition: 'Private feedback submissions.' },
      { key: 'feedback_rating_average', label: 'Average platform feedback rating', value: 4.3, unit: 'stars', basis: 'current', available: true, definition: 'Mean of optional ratings received.' },
      { key: 'feedback_rated_response_count', label: 'Rated feedback responses', value: 7, unit: 'responses', basis: 'current', available: true, definition: 'Feedback responses that include an optional rating.' },
    ] },
    engagement: { metrics: [{ key: 'contact_enquiries', value: 9, unit: 'enquiries', basis: 'period', available: true, definition: 'Durably accepted records.' }, { key: 'new_subscribers', value: 3, unit: 'subscribers', basis: 'period', available: true, definition: 'Unique stored subscriptions.' }] },
  },
};

function LocationText() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}

function renderPage(initial = '/admin/analytics') {
  return render(<MemoryRouter initialEntries={[initial]}><LocationText /><AnalyticsPage /></MemoryRouter>);
}

describe('AnalyticsPage', () => {
  afterEach(() => { cleanup(); vi.useRealTimers(); });
  beforeEach(() => {
    vi.clearAllMocks();
    api.getAnalyticsSummary.mockResolvedValue(sampleSummary);
    api.getAnalyticsSeries.mockImplementation(async (metric: string) => ({
      metric, unit: 'views', timezone: 'America/Toronto',
      period: sampleSummary.period, coverage: { available: true }, available: true,
      partial_coverage: false, data: [{ bucket: 'Apr 1', value: 61 }, { bucket: 'Apr 30', value: 89 }],
    }));
    api.getAnalyticsBreakdowns.mockImplementation(async (domain: string) => ({ domain, timezone: 'America/Toronto', period: sampleSummary.period, coverage: { available: true }, groups: {} }));
    api.getProviderRanking.mockResolvedValue({
      data: [{ provider_id: 'abc', name: 'Northfield Equine', provider_type: 'CLINIC', provider_status: 'ACTIVE', publication_status: 'PUBLISHED', profile_views: 144, review_submissions: 3, average_rating: 4.7, rating_count: 15, saved_count: 26 }],
      meta: { page: 1, page_size: 10, total: 1, total_pages: 1 }, period: sampleSummary.period, timezone: 'America/Toronto', coverage: { available: true },
    });
  });

  it('renders only the six curated overview metrics and omits other supplied metrics', async () => {
    renderPage();
    expect(await screen.findByText('1,837')).toBeTruthy();
    const headlines = within(screen.getByRole('region', { name: 'Headline metrics' }));
    for (const label of [
      'Website page views',
      'Provider profile views',
      'New member registrations',
      'New provider applications',
      'Accepted enquiries',
      'New unique subscribers',
    ]) {
      expect(headlines.getByText(label)).toBeTruthy();
    }
    expect(headlines.queryByText('Estimated visitor-days')).toBeNull();
    expect(headlines.queryByText('Provider inventory')).toBeNull();
    expect(headlines.queryByText('Review submissions')).toBeNull();
    expect(headlines.queryByText('Private feedback submissions')).toBeNull();
    expect(headlines.queryByText('Average platform feedback rating')).toBeNull();
    expect(headlines.queryByText('Rated feedback responses')).toBeNull();
    expect(screen.getByText('America/Toronto')).toBeTruthy();
    expect(screen.getByText(/Traffic tracking/)).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Overview' }).getAttribute('aria-selected')).toBe('true');
  });

  it('omits overview metrics whose source key is missing', async () => {
    const summaryWithoutApplications = {
      ...sampleSummary,
      sections: {
        ...sampleSummary.sections,
        applications: { metrics: [] },
      },
    };
    api.getAnalyticsSummary.mockResolvedValue(summaryWithoutApplications);
    renderPage();
    expect(await screen.findByText('1,837')).toBeTruthy();
    const headlines = within(screen.getByRole('region', { name: 'Headline metrics' }));
    expect(headlines.queryByText('New provider applications')).toBeNull();
    expect(headlines.getByText('New member registrations')).toBeTruthy();
  });

  it('distinguishes supplied zero metrics from unavailable metrics without dropping any core key', async () => {
    const replaceMetric = (metrics: typeof sampleSummary.sections.traffic.metrics, key: string, value: number | null, available: boolean) =>
      metrics.map((metric) => metric.key === key ? { ...metric, value, available } : metric);
    const summaryWithZeroesAndUnavailable = {
      ...sampleSummary,
      sections: {
        ...sampleSummary.sections,
        traffic: { metrics: replaceMetric(sampleSummary.sections.traffic.metrics, 'website_page_views', 0, true)
          .map((metric) => metric.key === 'provider_profile_views' ? { ...metric, value: null, available: false } : metric) },
        registrations: { metrics: replaceMetric(sampleSummary.sections.registrations.metrics, 'public_member_registrations', 0, true) },
        applications: { metrics: replaceMetric(sampleSummary.sections.applications.metrics, 'provider_applications', null, false) },
        engagement: { metrics: sampleSummary.sections.engagement.metrics.map((metric) =>
          metric.key === 'contact_enquiries' ? { ...metric, value: 0, available: true }
            : { ...metric, value: null, available: false }) },
      },
    };
    api.getAnalyticsSummary.mockResolvedValue(summaryWithZeroesAndUnavailable);
    const view = renderPage();
    expect(await screen.findByRole('region', { name: 'Headline metrics' })).toBeTruthy();
    const headlines = within(screen.getByRole('region', { name: 'Headline metrics' }));
    expect(view.container.querySelectorAll('[class*="metricCard"]')).toHaveLength(6);
    const cardValue = (label: string) => {
      const card = headlines.getByText(label).parentElement?.parentElement;
      return card?.querySelector('strong')?.textContent?.trim();
    };
    expect(cardValue('Website page views')).toBe('0 views');
    expect(cardValue('New member registrations')).toBe('0 accounts');
    expect(cardValue('Accepted enquiries')).toBe('0 enquiries');
    expect(cardValue('Provider profile views')).toBe('Unavailable');
    expect(cardValue('New provider applications')).toBe('Unavailable');
    expect(cardValue('New unique subscribers')).toBe('Unavailable');
  });

  it('surfaces a partial-coverage warning for a supplied core traffic metric', async () => {
    api.getAnalyticsSummary.mockResolvedValue({
      ...sampleSummary,
      sections: {
        ...sampleSummary.sections,
        traffic: { metrics: sampleSummary.sections.traffic.metrics.map((metric) =>
          metric.key === 'website_page_views' ? { ...metric, partial_coverage: true } : metric) },
      },
    });
    renderPage('/admin/analytics?section=traffic');
    expect(await screen.findByText('Traffic is partial or unavailable for this period. Uncovered dates are not zero activity.')).toBeTruthy();
  });

  it('uses eligible review rating contract metrics and shows the eligible count on the average card', async () => {
    renderPage('/admin/analytics?section=reviews');
    const headlines = within(await screen.findByRole('region', { name: 'Headline metrics' }));
    const average = headlines.getByText('Current eligible average rating');
    expect(average).toBeTruthy();
    expect(average.parentElement?.parentElement?.textContent).toContain('11 rated responses');
    expect(headlines.getByText('Review submissions')).toBeTruthy();
  });

  it('uses stable tab IDs and supports arrow, Home and End keyboard navigation', async () => {
    renderPage();
    const expectedTabs: Array<[string, string]> = [
      ['Overview', 'overview'],
      ['Website traffic', 'traffic'],
      ['Members', 'registrations'],
      ['Providers', 'providers'],
      ['Reviews & feedback', 'reviews'],
      ['Enquiries & subscribers', 'engagement'],
    ];
    for (const [name, id] of expectedTabs) {
      expect(screen.getByRole('tab', { name }).id).toBe(`analytics-tab-${id}`);
    }

    const tablist = screen.getByRole('tablist', { name: 'Analytics sections' });
    fireEvent.keyDown(tablist, { key: 'ArrowRight' });
    expect(screen.getByRole('tab', { name: 'Website traffic' }).getAttribute('aria-selected')).toBe('true');
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('section=traffic'));

    fireEvent.keyDown(tablist, { key: 'Home' });
    expect(screen.getByRole('tab', { name: 'Overview' }).getAttribute('aria-selected')).toBe('true');
    await waitFor(() => expect(screen.getByTestId('location').textContent).not.toContain('section='));

    fireEvent.keyDown(tablist, { key: 'End' });
    expect(screen.getByRole('tab', { name: 'Enquiries & subscribers' }).getAttribute('aria-selected')).toBe('true');
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('section=engagement'));
  });

  it('persists selected section and date preset in the URL and loads scoped reports', async () => {
    renderPage('/admin/analytics?preset=last_7_days');
    await screen.findByText('1,837');
    fireEvent.click(screen.getByRole('tab', { name: 'Members' }));
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('section=registrations'));
    expect(screen.getByTestId('location').textContent).toContain('preset=last_7_days');
    expect(await within(await screen.findByRole('region', { name: 'Headline metrics' })).findByText('New member registrations')).toBeTruthy();
    expect(api.getAnalyticsBreakdowns).toHaveBeenCalledWith('registrations', expect.objectContaining({ preset: 'last_7_days' }));
  });

  it('keeps detail headline metrics scoped to the selected tab', async () => {
    const trafficView = renderPage('/admin/analytics?section=traffic');
    const trafficHeadlines = within(await screen.findByRole('region', { name: 'Headline metrics' }));
    expect(await trafficHeadlines.findByText('Website page views')).toBeTruthy();
    expect(trafficHeadlines.getByText('Provider profile views')).toBeTruthy();
    expect(trafficHeadlines.queryByText('New member registrations')).toBeNull();
    expect(trafficHeadlines.queryByText('Average platform feedback rating')).toBeNull();
    trafficView.unmount();

    renderPage('/admin/analytics?section=registrations');
    const memberHeadlines = within(await screen.findByRole('region', { name: 'Headline metrics' }));
    expect(await memberHeadlines.findByText('New member registrations')).toBeTruthy();
    expect(memberHeadlines.queryByText('Website page views')).toBeNull();
    expect(memberHeadlines.queryByText('Provider inventory')).toBeNull();
  });

  it('offers one provider search input, server-paginated ranking and sortable headings', async () => {
    renderPage('/admin/analytics?section=providers');
    expect(await screen.findByRole('link', { name: 'Northfield Equine' })).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: /Period profile views/ })).toBeTruthy();
    expect(screen.getAllByText('144').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('textbox', { name: 'Search providers' })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Sort by Provider' }));
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({ sort: 'name', sort_direction: 'desc' })));
    expect(screen.getByRole('combobox', { name: 'Rows per page' })).toBeTruthy();
  });

  it('uses the selected backend sort field for provider-ranking CSV exports', async () => {
    renderPage('/admin/analytics?section=providers');
    await screen.findByRole('link', { name: 'Northfield Equine' });
    fireEvent.click(screen.getByRole('button', { name: 'Sort by Provider' }));
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({ sort: 'name' })));

    fireEvent.click(screen.getByText('Export CSV'));
    fireEvent.click(screen.getByRole('button', { name: 'Provider ranking' }));
    await waitFor(() => expect(api.exportAnalytics).toHaveBeenCalledWith(expect.objectContaining({
      dataset: 'provider-ranking',
      sort: 'name',
      sort_direction: 'desc',
    })));
    const exportParams = api.exportAnalytics.mock.calls[api.exportAnalytics.mock.calls.length - 1]?.[0];
    expect(exportParams).not.toHaveProperty('sort_by');
  });

  it('omits provider filters from a sitewide traffic CSV export', async () => {
    renderPage('/admin/analytics?section=traffic&provider_type=CLINIC&provider_id=provider-uuid-123');
    expect(await screen.findByText('1,837')).toBeTruthy();

    fireEvent.click(screen.getByText('Export CSV'));
    fireEvent.click(screen.getByRole('button', { name: 'Time series · Website page views' }));
    await waitFor(() => expect(api.exportAnalytics).toHaveBeenCalledWith(expect.objectContaining({
      dataset: 'series',
      metric: 'website_page_views',
    })));
    const exportParams = api.exportAnalytics.mock.calls[api.exportAnalytics.mock.calls.length - 1]?.[0];
    expect(exportParams).not.toHaveProperty('provider_type');
    expect(exportParams).not.toHaveProperty('provider_id');
    expect(exportParams).not.toHaveProperty('specialization_id');
  });

  it('updates provider ranking pagination and resets to page one when its search is cleared', async () => {
    api.getProviderRanking.mockImplementation(async (params: { page?: number; page_size?: number }) => ({
      data: [{ provider_id: 'abc', name: 'Northfield Equine', provider_type: 'CLINIC', provider_status: 'ACTIVE', publication_status: 'PUBLISHED', profile_views: 144, review_submissions: 3, average_rating: 4.7, rating_count: 15, saved_count: 26 }],
      meta: { page: params.page ?? 1, page_size: params.page_size ?? 10, total: 30, total_pages: 3 },
      period: sampleSummary.period, timezone: 'America/Toronto', coverage: { available: true },
    }));
    renderPage('/admin/analytics?section=providers&page=2&provider_search=North');
    expect(await screen.findByRole('link', { name: 'Northfield Equine' })).toBeTruthy();
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({
      page: 2,
      provider_search: 'North',
    })));

    fireEvent.click(screen.getByRole('button', { name: 'Next →' }));
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('page=3'));
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({ page: 3 })));

    fireEvent.change(screen.getByRole('textbox', { name: 'Search providers' }), { target: { value: '' } });
    await waitFor(() => {
      const location = screen.getByTestId('location').textContent ?? '';
      expect(location).not.toContain('page=');
      expect(location).not.toContain('provider_search=');
    });
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 })));
    const lastParams = api.getProviderRanking.mock.calls[api.getProviderRanking.mock.calls.length - 1]?.[0];
    expect(lastParams).not.toHaveProperty('provider_search');
  });

  it('scopes provider type to application and invitation breakdowns without leaking provider geography', async () => {
    renderPage('/admin/analytics?section=providers&provider_type=CLINIC&provider_status=ACTIVE&country=Canada&city=Calgary&application_status=APPROVED&invitation_status=PENDING');
    await waitFor(() => {
      const requestedDomains = api.getAnalyticsBreakdowns.mock.calls.map(([domain]) => domain);
      expect(requestedDomains).toContain('applications');
      expect(requestedDomains).toContain('invitations');
      expect(requestedDomains).not.toContain('providers');
    });
    expect(screen.getByText('Current listed providers')).toBeTruthy();
    const initialSummaryCalls = api.getAnalyticsSummary.mock.calls.length;
    fireEvent.click(screen.getByText('View detailed reports'));
    await waitFor(() => expect(api.getAnalyticsBreakdowns.mock.calls.map(([domain]) => domain)).toContain('providers'));
    expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(initialSummaryCalls);

    const paramsFor = (domain: string) => api.getAnalyticsBreakdowns.mock.calls
      .filter(([calledDomain]) => calledDomain === domain)
      .slice(-1)[0]?.[1];
    const providerParams = paramsFor('providers');
    const applicationParams = paramsFor('applications');
    const invitationParams = paramsFor('invitations');

    expect(providerParams).toEqual(expect.objectContaining({
      provider_type: 'CLINIC', provider_status: 'ACTIVE', country: 'Canada', city: 'Calgary',
    }));
    expect(applicationParams).toEqual(expect.objectContaining({ provider_type: 'CLINIC', application_status: 'APPROVED' }));
    expect(invitationParams).toEqual(expect.objectContaining({ provider_type: 'CLINIC', invitation_status: 'PENDING' }));
    for (const params of [applicationParams, invitationParams]) {
      expect(params).not.toHaveProperty('country');
      expect(params).not.toHaveProperty('city');
      expect(params).not.toHaveProperty('provider_status');
    }
  });

  it('does not issue requests for a reversed custom date range', async () => {
    renderPage('/admin/analytics?section=traffic&preset=custom&date_from=2026-04-10&date_to=2026-04-02');
    expect(await screen.findByText('The start date must be on or before the end date. Correct the dates to run this report.')).toBeTruthy();
    expect(api.getAnalyticsSummary).not.toHaveBeenCalled();
    expect(api.getAnalyticsSeries).not.toHaveBeenCalled();
    expect(api.getAnalyticsBreakdowns).not.toHaveBeenCalled();
  });

  it('keeps trend selection singular and limits visible curated breakdown charts', async () => {
    api.getAnalyticsBreakdowns.mockImplementation(async (domain: string) => ({
      domain, timezone: 'America/Toronto', period: sampleSummary.period, coverage: { available: true },
      groups: domain === 'traffic' ? {
        page_categories: { directory: 22, provider_profile: 13 },
        top_providers: [{ name: 'Northfield Equine', profile_views: 18 }],
        visitor_days: 31,
      } : {},
    }));
    renderPage('/admin/analytics?section=traffic');

    expect(await screen.findByRole('img', { name: /Website page views over time/ })).toBeTruthy();
    const trendMetric = screen.getByRole('combobox', { name: 'Trend metric' });
    fireEvent.change(trendMetric, { target: { value: 'provider_profile_views' } });
    expect(await screen.findByRole('img', { name: /Provider profile views over time/ })).toBeTruthy();
    await waitFor(() => expect(api.getAnalyticsSeries).toHaveBeenCalledWith('provider_profile_views', expect.anything()));
    expect(screen.getAllByRole('img', { name: /over time/i })).toHaveLength(1);

    const breakdownCharts = screen.getAllByRole('img').filter((chart) => !/over time/i.test(chart.getAttribute('aria-label') ?? ''));
    expect(breakdownCharts.length).toBeLessThanOrEqual(2);
    expect(screen.queryByRole('img', { name: /top providers/i })).toBeNull();
    expect(screen.getByRole('region', { name: 'Provider popularity' })).toBeTruthy();

    const detailedReports = screen.getByText('View detailed reports').closest('details');
    expect(detailedReports).toBeTruthy();
    expect((detailedReports as HTMLDetailsElement).open).toBe(false);
    fireEvent.click(screen.getByText('View detailed reports'));
    expect((detailedReports as HTMLDetailsElement).open).toBe(true);
    await waitFor(() => expect(screen.getAllByRole('heading', { name: 'Breakdown tables' }).length).toBeGreaterThan(0));
    const individualReports = Array.from((detailedReports as HTMLDetailsElement).querySelectorAll('details'))
      .filter((report) => report !== detailedReports);
    expect(individualReports.length).toBeGreaterThan(0);
    expect(individualReports.every((report) => !report.open)).toBe(true);
  });

  it('hides advanced filters and exposes removable labels for deep-linked record filters', async () => {
    const providerId = 'provider-uuid-123';
    const specializationId = 'specialization-uuid-456';
    renderPage(`/admin/analytics?section=traffic&provider_id=${providerId}&specialization_id=${specializationId}`);
    expect(await screen.findByText('1,837')).toBeTruthy();

    const moreFilters = screen.getByText('More filters').closest('details');
    expect(moreFilters).toBeTruthy();
    expect((moreFilters as HTMLDetailsElement).open).toBe(false);
    expect(screen.queryByLabelText('Provider type')).toBeNull();
    const providerFilterChip = screen.getByRole('button', { name: 'Remove Provider record filter' });
    const specializationFilterChip = screen.getByRole('button', { name: 'Remove Specialization filter' });
    expect(providerFilterChip.textContent).toContain(`Provider record: ${providerId}`);
    expect(specializationFilterChip.textContent).toContain(`Specialization: ${specializationId}`);
    expect(screen.queryByRole('textbox', { name: /Provider ID|Specialization ID/i })).toBeNull();

    fireEvent.click(providerFilterChip);
    await waitFor(() => expect(screen.getByTestId('location').textContent).not.toContain('provider_id='));
    expect(screen.getByRole('button', { name: 'Remove Specialization filter' })).toBeTruthy();
    expect(api.getAnalyticsBreakdowns).toHaveBeenCalledWith('traffic', expect.objectContaining({ specialization_id: specializationId }));
  });

  it('exports the selected trend and selected breakdown with section-scoped filters', async () => {
    renderPage('/admin/analytics?section=traffic&provider_type=CLINIC');
    expect(await screen.findByText('1,837')).toBeTruthy();
    fireEvent.change(screen.getByRole('combobox', { name: 'Trend metric' }), { target: { value: 'provider_profile_views' } });
    await waitFor(() => expect(api.getAnalyticsSeries).toHaveBeenCalledWith('provider_profile_views', expect.anything()));

    const exportMenu = screen.getByText('Export CSV').closest('details') as HTMLDetailsElement;
    fireEvent.click(screen.getByText('Export CSV'));
    fireEvent.click(screen.getByRole('button', { name: 'Time series · Provider profile views' }));
    await waitFor(() => expect(api.exportAnalytics).toHaveBeenCalledWith(expect.objectContaining({
      dataset: 'series',
      metric: 'provider_profile_views',
      provider_type: 'CLINIC',
    })));

    if (!exportMenu.open) fireEvent.click(screen.getByText('Export CSV'));
    fireEvent.click(screen.getByRole('button', { name: 'Breakdown · Traffic' }));
    await waitFor(() => expect(api.exportAnalytics).toHaveBeenLastCalledWith(expect.objectContaining({
      dataset: 'breakdowns',
      domain: 'traffic',
      provider_type: 'CLINIC',
    })));
  });

  it('runs custom ranges only after both dates are supplied', async () => {
    renderPage('/admin/analytics?section=traffic&preset=custom');
    expect(await screen.findByText(/Choose both start and end dates/)).toBeTruthy();
    expect(api.getAnalyticsSummary).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-04-02' } });
    expect(api.getAnalyticsSummary).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Through'), { target: { value: '2026-04-10' } });
    await waitFor(() => expect(api.getAnalyticsSummary).toHaveBeenLastCalledWith(expect.objectContaining({
      preset: 'custom',
      date_from: '2026-04-02',
      date_to: '2026-04-10',
    })));
  });

  it('ignores stale responses after switching sections while a prior request is pending', async () => {
    let resolveFirst!: (summary: typeof sampleSummary) => void;
    let resolveSecond!: (summary: typeof sampleSummary) => void;
    const withPageViews = (value: number) => ({
      ...sampleSummary,
      sections: {
        ...sampleSummary.sections,
        traffic: { metrics: sampleSummary.sections.traffic.metrics.map((metric) =>
          metric.key === 'website_page_views' ? { ...metric, value } : metric) },
      },
    });
    api.getAnalyticsSummary
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));
    renderPage();
    await waitFor(() => expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('tab', { name: 'Website traffic' }));
    await waitFor(() => expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(2));

    await act(async () => { resolveSecond(withPageViews(2222)); });
    expect(await screen.findByText('2,222')).toBeTruthy();
    await act(async () => { resolveFirst(withPageViews(9999)); });
    await waitFor(() => expect(screen.queryByText('9,999')).toBeNull());
    expect(screen.getByText('2,222')).toBeTruthy();
  });

  it('reports summary errors with a retry action', async () => {
    api.getAnalyticsSummary.mockRejectedValueOnce(new Error('Summary service unavailable'));
    renderPage();
    expect((await screen.findByRole('alert')).textContent).toContain('Analytics could not be loaded.');
    api.getAnalyticsSummary.mockResolvedValue(sampleSummary);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('1,837')).toBeTruthy();
  });

  it('recovers from a failed CSV export when the same export is retried', async () => {
    api.exportAnalytics.mockRejectedValueOnce(new Error('Export service unavailable'));
    renderPage('/admin/analytics?section=traffic');
    expect(await screen.findByText('1,837')).toBeTruthy();

    const exportMenu = screen.getByText('Export CSV').closest('details') as HTMLDetailsElement;
    fireEvent.click(screen.getByText('Export CSV'));
    fireEvent.click(screen.getByRole('button', { name: 'Time series · Website page views' }));
    expect(await screen.findByText('CSV export failed. Try again.')).toBeTruthy();
    expect(api.exportAnalytics).toHaveBeenCalledTimes(1);

    api.exportAnalytics.mockResolvedValue(undefined);
    if (!exportMenu.open) fireEvent.click(screen.getByText('Export CSV'));
    fireEvent.click(screen.getByRole('button', { name: 'Time series · Website page views' }));
    expect(await screen.findByText('CSV downloaded.')).toBeTruthy();
    expect(api.exportAnalytics).toHaveBeenCalledTimes(2);
  });

  it('keeps the summary visible and reports partial chart failure with a retry', async () => {
    api.getAnalyticsSeries.mockRejectedValueOnce(new Error('Series service unavailable'));
    renderPage('/admin/analytics?section=traffic');
    expect(await screen.findByText('1,837')).toBeTruthy();
    expect(await screen.findByText(/report panel.*could not be loaded/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry reports' })).toBeTruthy();
  });

  it('refreshes the summary and report data on demand', async () => {
    api.getAnalyticsSummary
      .mockResolvedValueOnce(sampleSummary)
      .mockResolvedValueOnce({ ...sampleSummary, refreshed_at: '2026-04-30T16:00:00Z' });
    renderPage('/admin/analytics?section=traffic');
    expect(await screen.findByText('1,837')).toBeTruthy();
    const initialCalls = api.getAnalyticsSummary.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));
    await waitFor(() => expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(initialCalls + 1));
    await waitFor(() => expect(api.getAnalyticsBreakdowns).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenCalledTimes(2));
  });

  it.each(['providers', 'traffic'])('reloads only ranking for sort, page and page size in %s', async (section) => {
    api.getProviderRanking.mockImplementation(async (params) => ({
      data: [], meta: { page: params.page, page_size: params.page_size, total: 100, total_pages: 10 },
      period: sampleSummary.period, timezone: 'America/Toronto', coverage: { available: true },
    }));
    renderPage(`/admin/analytics?section=${section}&page=2&provider_type=CLINIC&preset=last_7_days`);
    await screen.findByRole('region', { name: 'Headline metrics' });
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenCalledTimes(1));
    const counts = [api.getAnalyticsSummary.mock.calls.length, api.getAnalyticsSeries.mock.calls.length, api.getAnalyticsBreakdowns.mock.calls.length];
    fireEvent.click(screen.getByRole('button', { name: 'Next →' }));
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({ page: 3 })));
    fireEvent.click(screen.getByRole('button', { name: 'Sort by Provider' }));
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, sort: 'name' })));
    fireEvent.change(screen.getByRole('combobox', { name: 'Rows per page' }), { target: { value: '25' } });
    await waitFor(() => expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, page_size: 25, provider_type: 'CLINIC', preset: 'last_7_days' })));
    expect([api.getAnalyticsSummary.mock.calls.length, api.getAnalyticsSeries.mock.calls.length, api.getAnalyticsBreakdowns.mock.calls.length]).toEqual(counts);
    expect(screen.queryByText('Updating reports for the applied filters…')).toBeNull();
    expect(screen.getByTestId('location').textContent).toContain('provider_type=CLINIC');
  });

  it('debounces typing, merges the latest URL filters and reloads only search-scoped panels', async () => {
    renderPage('/admin/analytics?section=providers&provider_type=CLINIC');
    await screen.findByRole('link', { name: 'Northfield Equine' });
    const breakdownCalls = api.getAnalyticsBreakdowns.mock.calls.length;
    const seriesCalls = api.getAnalyticsSeries.mock.calls.length;
    const rankingCalls = api.getProviderRanking.mock.calls.length;
    vi.useFakeTimers();
    const search = screen.getByRole('textbox', { name: 'Search providers' });
    fireEvent.change(search, { target: { value: 'N' } });
    await act(async () => { vi.advanceTimersByTime(200); });
    fireEvent.change(search, { target: { value: 'North' } });
    fireEvent.change(screen.getByLabelText('Group by'), { target: { value: 'weekly' } });
    await act(async () => { vi.advanceTimersByTime(299); });
    expect(api.getProviderRanking.mock.calls.slice(-1)[0]?.[0]).not.toHaveProperty('provider_search');
    expect((search as HTMLInputElement).value).toBe('North');
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(api.getProviderRanking).toHaveBeenLastCalledWith(expect.objectContaining({ provider_search: 'North', page: 1, provider_type: 'CLINIC', group_by: 'weekly' }));
    expect(api.getProviderRanking).toHaveBeenCalledTimes(rankingCalls + 2); // grouping, then committed search
    expect(api.getAnalyticsBreakdowns).toHaveBeenCalledTimes(breakdownCalls + 2); // grouping only
    expect(api.getAnalyticsSeries).toHaveBeenCalledTimes(seriesCalls + 1);
    expect(screen.getByTestId('location').textContent).toContain('provider_search=North');
    expect(screen.getByTestId('location').textContent).not.toContain('page=');
    vi.useRealTimers();
    fireEvent.click(screen.getByText('Export CSV'));
    fireEvent.click(screen.getByRole('button', { name: 'Provider ranking' }));
    await waitFor(() => expect(api.exportAnalytics).toHaveBeenCalledWith(expect.objectContaining({ provider_search: 'North', provider_type: 'CLINIC', group_by: 'weekly', sort: 'profile_views', sort_direction: 'desc' })));
  });

  it('reloads search-scoped traffic reports but reuses the sitewide trend', async () => {
    renderPage('/admin/analytics?section=traffic');
    await screen.findByRole('link', { name: 'Northfield Equine' });
    vi.useFakeTimers();
    fireEvent.change(screen.getByRole('textbox', { name: 'Search providers' }), { target: { value: 'North' } });
    await act(async () => { vi.advanceTimersByTime(300); });
    expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(2);
    expect(api.getAnalyticsBreakdowns).toHaveBeenLastCalledWith('traffic', expect.objectContaining({ provider_search: 'North' }));
    expect(api.getAnalyticsSeries).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
    fireEvent.change(screen.getByLabelText('Trend metric'), { target: { value: 'provider_profile_views' } });
    await waitFor(() => expect(api.getAnalyticsSeries).toHaveBeenLastCalledWith('provider_profile_views', expect.objectContaining({ provider_search: 'North' })));
    expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(2);
    expect(api.getProviderRanking).toHaveBeenCalledTimes(2);
  });

  it('keeps section reports visible while ranking is pending, and ignores stale ranking pages and errors', async () => {
    const initial = await api.getProviderRanking();
    api.getProviderRanking.mockClear();
    let resolveOld!: (value: typeof initial) => void;
    let rejectOld!: (reason: Error) => void;
    api.getProviderRanking.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }));
    renderPage('/admin/analytics?section=providers&page=2');
    expect(await screen.findByText('Current listed providers')).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Northfield Equine' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Sort by Provider' }));
    expect(await screen.findByRole('link', { name: 'Northfield Equine' })).toBeTruthy();
    await act(async () => { resolveOld({ ...initial, data: [{ ...initial.data[0], name: 'Stale provider' }], meta: { ...initial.meta, page: 2 } }); });
    expect(screen.queryByText('Stale provider')).toBeNull();
    expect(screen.getByTestId('location').textContent).not.toContain('page=2');
    api.getProviderRanking.mockImplementationOnce(() => new Promise((_, reject) => { rejectOld = reject; }));
    fireEvent.click(screen.getByRole('button', { name: 'Sort by Provider' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Rows per page' }), { target: { value: '25' } });
    await screen.findByRole('link', { name: 'Northfield Equine' });
    await act(async () => { rejectOld(new Error('Old failure')); });
    expect(screen.queryByText('Provider ranking unavailable')).toBeNull();
    expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(1);
  });

  it('retries ranking failures independently and preserves section failures on ranking changes', async () => {
    api.getProviderRanking.mockRejectedValueOnce(new Error('Ranking unavailable'));
    api.getAnalyticsSeries.mockRejectedValueOnce(new Error('Trend unavailable'));
    renderPage('/admin/analytics?section=traffic');
    await screen.findByText('Provider ranking unavailable');
    expect(screen.getByText(/report panel.*could not be loaded/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('link', { name: 'Northfield Equine' });
    expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(1);
    expect(api.getAnalyticsSeries).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/report panel.*could not be loaded/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry reports' }));
    await waitFor(() => expect(api.getAnalyticsSeries).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText(/report panel.*could not be loaded/)).toBeNull());
    expect(api.getProviderRanking).toHaveBeenCalledTimes(3);
  });

  it('cancels pending provider typing when leaving the section or resetting filters', async () => {
    renderPage('/admin/analytics?section=providers');
    await screen.findByRole('link', { name: 'Northfield Equine' });
    vi.useFakeTimers();
    fireEvent.change(screen.getByRole('textbox', { name: 'Search providers' }), { target: { value: 'North' } });
    fireEvent.click(screen.getByRole('tab', { name: 'Members' }));
    await act(async () => { vi.advanceTimersByTime(300); });
    expect(screen.getByTestId('location').textContent).not.toContain('provider_search');
    fireEvent.click(screen.getByRole('tab', { name: 'Providers' }));
    await act(async () => {});
    fireEvent.change(screen.getByRole('textbox', { name: 'Search providers' }), { target: { value: 'North' } });
    fireEvent.click(screen.getByText('More filters'));
    await act(async () => { vi.advanceTimersByTime(0); });
    fireEvent.click(screen.getByRole('button', { name: 'Reset filters' }));
    await act(async () => { vi.advanceTimersByTime(300); });
    expect(screen.getByTestId('location').textContent).not.toContain('provider_search');
    expect((screen.getByRole('textbox', { name: 'Search providers' }) as HTMLInputElement).value).toBe('');
  });
});