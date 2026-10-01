import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProviderInsightsPage } from './ProviderInsightsPage';
import * as insightsApi from '@/api/providerInsights';

vi.mock('@/api/providerInsights', () => ({ getProviderInsights: vi.fn() }));
vi.mock('@/components/layout/ProviderTopNav', () => ({ ProviderTopNav: () => <nav>Portal navigation</nav> }));
vi.mock('@/components/analytics/AnalyticsChart', () => ({
  AnalyticsChart: ({ title }: { title: string }) => <section>{title} chart</section>,
}));

const metric = (value: number | null) => ({
  value, definition: 'Successfully loaded member profile pages; revisits count again and are not a unique-person or appointment count.', coverage: { status: value === null ? 'unknown' as const : 'full' as const, from: '2025-01-01', note: '' },
  comparison: { change_percent: null, previous_value: null, reason: 'No meaningful comparison available.' },
});
const response = {
  provider_name: 'Willow Creek Equine', timezone: 'UTC', today: '2025-01-30',
  period: { date_from: '2025-01-01', date_to: '2025-01-30', preset: 'last_30_days' as const }, refreshed_at: '2025-01-30T10:00:00Z',
  metrics: { profile_views: metric(24), contact_clicks: metric(null), new_conversations: metric(3) },
  contact_breakdown: { phone: 2, email: 1, website: 0 },
  snapshot: { saved_members: 8, rating_count: 4, visible_review_count: 3, average_rating: 4.5 },
  trends: [{ date: '2025-01-01', profile_views: 2, contact_clicks: null }],
};

describe('ProviderInsightsPage', () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.clearAllMocks());
  it('loads a friendly period view with trends, snapshot and coverage-aware values', async () => {
    vi.mocked(insightsApi.getProviderInsights).mockResolvedValue(response);
    render(<MemoryRouter><ProviderInsightsPage /></MemoryRouter>);
    expect(screen.getByRole('status').textContent).toContain('Loading');
    await waitFor(() => expect(screen.getAllByRole('heading', { level: 1 }).length).toBe(1));
    expect(insightsApi.getProviderInsights).toHaveBeenCalledWith({ preset: 'last_30_days' }, expect.any(AbortSignal));
    expect(screen.getByText('24')).toBeTruthy();
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0);
    expect(screen.getByText('Current snapshot')).toBeTruthy();
    expect(screen.getByText('Profile visits chart')).toBeTruthy();
    expect(screen.getByText('Phone')).toBeTruthy();
    expect(screen.getByText('8')).toBeTruthy();
  });

  it('does not retry a failed request automatically and retries only on request', async () => {
    vi.mocked(insightsApi.getProviderInsights)
      .mockRejectedValueOnce(new Error('temporary'))
      .mockResolvedValueOnce(response);
    render(<MemoryRouter><ProviderInsightsPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/couldn’t load your insights/)).toBeTruthy());
    expect(insightsApi.getProviderInsights).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Willow Creek Equine'));
    expect(insightsApi.getProviderInsights).toHaveBeenCalledTimes(2);
  });

  it('clears previously loaded private data when the session expires', async () => {
    vi.mocked(insightsApi.getProviderInsights)
      .mockResolvedValueOnce(response)
      .mockRejectedValueOnce({ response: { status: 401 } });
    render(<MemoryRouter><ProviderInsightsPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Willow Creek Equine'));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh insights' }));
    await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' })).toBeTruthy());
    expect(screen.queryByText('Willow Creek Equine')).toBeNull();
  });

  it('rejects reversed, future and oversized custom ranges without requesting them', async () => {
    vi.mocked(insightsApi.getProviderInsights).mockResolvedValue(response);
    render(<MemoryRouter><ProviderInsightsPage /></MemoryRouter>);
    await screen.findByText('Willow Creek Equine');
    fireEvent.change(screen.getByLabelText('Show activity'), { target: { value: 'custom' } });
    const from = screen.getByLabelText('From');
    const to = screen.getByLabelText('To');
    fireEvent.change(from, { target: { value: '2025-01-20' } });
    fireEvent.change(to, { target: { value: '2025-01-19' } });
    fireEvent.click(screen.getByText('Apply dates'));
    expect(screen.getByRole('alert').textContent).toContain('start date on or before');
    fireEvent.change(to, { target: { value: '2025-01-31' } });
    fireEvent.click(screen.getByText('Apply dates'));
    expect(screen.getByRole('alert').textContent).toContain('Future dates');
    fireEvent.change(from, { target: { value: '2023-01-01' } });
    fireEvent.change(to, { target: { value: '2025-01-30' } });
    fireEvent.click(screen.getByText('Apply dates'));
    expect(screen.getByRole('alert').textContent).toContain('366 days');
    expect(insightsApi.getProviderInsights).toHaveBeenCalledTimes(1);
  });

  it('ignores late results from an aborted request after Strict Mode replay wins', async () => {
    let finishOlder!: (value: typeof response) => void;
    vi.mocked(insightsApi.getProviderInsights)
      .mockImplementationOnce(() => new Promise((resolve) => { finishOlder = resolve; }))
      .mockResolvedValueOnce({ ...response, provider_name: 'Latest report' });
    render(<StrictMode><MemoryRouter><ProviderInsightsPage /></MemoryRouter></StrictMode>);
    await screen.findByText('Latest report');
    expect(insightsApi.getProviderInsights).toHaveBeenCalledTimes(2);
    finishOlder({ ...response, provider_name: 'Outdated report' });
    await waitFor(() => expect(screen.queryByText('Outdated report')).toBeNull());
    expect(screen.getByText('Latest report')).toBeTruthy();
  });

  it('explains machine comparison reasons in plain English', async () => {
    vi.mocked(insightsApi.getProviderInsights).mockResolvedValue({
      ...response,
      metrics: {
        ...response.metrics,
        profile_views: { ...metric(0), comparison: { change_percent: null, previous_value: 0, reason: 'zero_previous_value' } },
      },
    });
    render(<MemoryRouter><ProviderInsightsPage /></MemoryRouter>);
    await screen.findByText('Willow Creek Equine');
    expect(screen.getByText(/previous period had no activity/)).toBeTruthy();
    expect(screen.queryByText('zero_previous_value')).toBeNull();
  });
});