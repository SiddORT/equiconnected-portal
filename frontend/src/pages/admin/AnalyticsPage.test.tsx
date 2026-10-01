import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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
      { key: 'estimated_visitor_days', value: 406, unit: 'visitor-days', basis: 'period', available: true, definition: 'Browser-deduplicated daily estimates.' },
    ] },
    registrations: { metrics: [{ key: 'public_member_registrations', value: 42, unit: 'accounts', basis: 'period', available: true, definition: 'Public member accounts.' }] },
    providers: { inventory: { total: 87, active: 61, active_published: 55, status: { DRAFT: 5, UNDER_REVIEW: 8, INACTIVE: 13 }, publication: { PUBLISHED: 55, UNPUBLISHED: 32 } } },
    applications: { metrics: [{ key: 'provider_applications', value: 8, unit: 'applications', basis: 'period', available: true, definition: 'New provider applications.' }] },
    reviews: { metrics: [{ key: 'provider_review_submissions', value: 12, unit: 'reviews', basis: 'period', available: true, definition: 'Initial submissions only.' }] },
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
  afterEach(cleanup);
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

  it('renders metric groups, accessible trends, timezone and aggregate-only definitions', async () => {
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Traffic & discovery' })).toBeTruthy();
    expect(screen.getByText('1,837')).toBeTruthy();
    expect(screen.getByText('America/Toronto')).toBeTruthy();
    expect(screen.getByRole('img', { name: /Website page views over time/ })).toBeTruthy();
    expect(screen.getByText(/Traffic tracking/)).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Overview' }).getAttribute('aria-selected')).toBe('true');
  });

  it('persists selected section and date preset in the URL and loads scoped reports', async () => {
    renderPage('/admin/analytics?preset=last_7_days');
    await screen.findByText('1,837');
    fireEvent.click(screen.getByRole('tab', { name: /^Registrations$/ }));
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('section=registrations'));
    expect(screen.getByTestId('location').textContent).toContain('preset=last_7_days');
    expect(await screen.findByText('New member registrations')).toBeTruthy();
    expect(api.getAnalyticsBreakdowns).toHaveBeenCalledWith('registrations', expect.objectContaining({ preset: 'last_7_days' }));
  });

  it('offers server-paginated provider ranking and accessible sortable headings', async () => {
    renderPage('/admin/analytics?section=providers');
    expect(await screen.findByRole('link', { name: 'Northfield Equine' })).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: /Period profile views/ })).toBeTruthy();
    expect(screen.getAllByText('144').length).toBeGreaterThan(0);
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

  it('scopes provider type to application and invitation breakdowns without leaking provider geography', async () => {
    renderPage('/admin/analytics?section=providers&provider_type=CLINIC&provider_status=ACTIVE&country=Canada&city=Calgary&application_status=APPROVED&invitation_status=PENDING');
    await waitFor(() => expect(api.getAnalyticsBreakdowns).toHaveBeenCalledTimes(3));

    const paramsFor = (domain: string) => api.getAnalyticsBreakdowns.mock.calls.find(([calledDomain]) => calledDomain === domain)?.[1];
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

  it('keeps the summary visible and reports partial chart failure with a retry', async () => {
    api.getAnalyticsSeries.mockRejectedValueOnce(new Error('Series service unavailable'));
    renderPage('/admin/analytics?section=traffic');
    expect(await screen.findByText('1,837')).toBeTruthy();
    expect(await screen.findByText(/report panel.*could not be loaded/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry reports' })).toBeTruthy();
  });

  it('maps nested provider inventory and registration-cohort groups to separate count charts', async () => {
    api.getAnalyticsBreakdowns.mockImplementation(async (domain: string) => ({
      domain, timezone: 'America/Toronto', period: sampleSummary.period, coverage: { available: true },
      groups: domain === 'providers' ? {
        current_inventory: { total: 6, status: { ACTIVE: 4, DRAFT: 2 }, type: { DOCTOR: 3, CLINIC: 2 }, publication: { PUBLISHED: 4, UNPUBLISHED: 2 }, active: 4, active_published: 4 },
      } : domain === 'registrations' ? {
        selected_cohort: { total: 9, roles: { horse_owner: 4, stable_manager: 3, both: 2 }, verified: { true: 6, false: 3 }, active: { true: 8, false: 1 }, role_assignments: { horse_owner: 5, stable_manager: 4 } },
      } : {},
    }));
    const providerView = renderPage('/admin/analytics?section=providers');
    expect(await screen.findByRole('img', { name: /Current provider inventory by status/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Current provider inventory by type/ })).toBeTruthy();
    expect(screen.getAllByText('ACTIVE').length).toBeGreaterThan(0);
    providerView.unmount();

    renderPage('/admin/analytics?section=registrations');
    expect(await screen.findByRole('img', { name: /Member cohort by exclusive role/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Registration cohort by current verification/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Registration cohort by current account state/ })).toBeTruthy();
  });

  it('renders review moderation/actions and provider leaders plus private feedback rating metrics', async () => {
    api.getAnalyticsBreakdowns.mockImplementation(async (domain: string) => ({
      domain, timezone: 'America/Toronto', period: sampleSummary.period, coverage: { available: true },
      definitions: { star_distribution: 'Eligible current ratings only.' },
      groups: domain === 'reviews' ? {
        star_distribution: [{ rating: 5, rating_count: 8 }, { rating: 4, rating_count: 3 }],
        active_moderation_status: { PENDING: 2, PUBLISHED: 8, HIDDEN: 1, REJECTED: 1 },
        submitted_cohort_current_status: { PENDING: 1, PUBLISHED: 2 },
        period_actions: { edited: 4, moderated: 3, deleted: 1 },
        top_reviewed_providers: [{ name: 'Pine Ridge', rating_count: 18 }],
        period_submission_leaders: [{ name: 'Oak Grove', review_submissions: 3 }],
      } : {
        categories: { 'Website / App': 3, Suggestion: 2 },
        submitted_cohort_current_status: { Pending: 1, Resolved: 2 },
        current_status: { Pending: 2, Resolved: 5 },
        ratings: { average: 4.2, count: 7, distribution: { 5: 4, 3: 3 } },
        withdrawn: { count: 1 },
      },
    }));
    renderPage('/admin/analytics?section=reviews');
    expect(await screen.findByRole('img', { name: /Active reviews by moderation status/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Selected-period review cohort · current moderation status/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Recorded review actions/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Pine Ridge: 18 eligible ratings/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Oak Grove: 3 submissions/ })).toBeTruthy();
    expect(screen.getByText('Average platform feedback rating')).toBeTruthy();
    expect(screen.getByText('Rated feedback responses')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Breakdown tables' })).toBeTruthy();
    expect(screen.getByText(/Edits and moderation actions recorded in the selected period/)).toBeTruthy();
  });

  it('maps contract-named application and invitation status reports', async () => {
    api.getAnalyticsBreakdowns.mockImplementation(async (domain: string) => ({
      domain, timezone: 'America/Toronto', period: sampleSummary.period, coverage: { available: true },
      groups: domain === 'applications' ? {
        submitted_cohort_current_status: { APPROVED: 3, REJECTED: 1 },
        all_current_status: { PENDING_REVIEW: 4, APPROVED: 12 },
      } : domain === 'invitations' ? {
        created_cohort_current_status: { PENDING: 5, COMPLETED: 2 },
        all_current_status: { PENDING: 7, ACCEPTED: 9 },
      } : {},
    }));
    renderPage('/admin/analytics?section=providers');
    expect(await screen.findByRole('img', { name: /Applications submitted in this period · current status/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /All applications · current status/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Invitations created in this period · current status/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /All invitations · current status/ })).toBeTruthy();
  });

  it('uses exact traffic and feedback breakdown groups while keeping rating average out of count charts', async () => {
    api.getAnalyticsBreakdowns.mockImplementation(async (domain: string) => ({
      domain, timezone: 'America/Toronto', period: sampleSummary.period, coverage: { available: true },
      definitions: domain === 'feedback' ? { ratings: 'Average and optional rating counts for non-withdrawn feedback.' } : { page_categories: 'Allowlisted public routes.' },
      groups: domain === 'traffic' ? {
        page_categories: { directory: 22, provider_profile: 13 },
        top_providers: [{ name: 'Willow Farm', profile_views: 18 }],
        visitor_days: 31,
      } : domain === 'feedback' ? {
        categories: { Suggestion: 2 },
        ratings: { average: 4.2, count: 4, distribution: { 5: 3, 2: 1 } },
      } : {},
    }));
    const trafficView = renderPage('/admin/analytics?section=traffic');
    expect(await screen.findByRole('img', { name: /Page views by public page category/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: /Willow Farm: 18 profile views/ })).toBeTruthy();
    trafficView.unmount();

    renderPage('/admin/analytics?section=reviews');
    expect(await screen.findByRole('img', { name: /Optional feedback ratings · response counts/ })).toBeTruthy();
    expect(screen.getByText('Average platform feedback rating')).toBeTruthy();
    expect(screen.getByText('Rated feedback responses')).toBeTruthy();
    expect(screen.queryByRole('img', { name: /4.2 stars/ })).toBeNull();
  });
});