import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { ProvidersPage } from './ProvidersPage';

vi.mock('@/api/providers', () => ({
  listProviders: vi.fn(),
  updateProviderPublication: vi.fn(),
  updateProviderStatus: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    settings: { timezone: 'UTC', date_format: 'month_day_year', time_format: '12_hour' },
    isLoading: false,
    error: null,
    formatTimestamp: (value: string) => value,
    formatDate: (value: string) => value,
    formatWeekday: (value: string) => value,
    refresh: vi.fn(),
  }),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ProvidersPage', () => {
  it('shows review summaries and links reviewed providers to scoped moderation', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      data: [
        {
          id: 'provider-reviewed',
          provider_type: 'CLINIC',
          name: 'Reviewed Clinic',
          email: null,
          phone: null,
          visit_stability: 'STABLE_VISIT',
          status: 'ACTIVE',
          publication_status: 'PUBLISHED',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          thumbnail_url: null,
          average_rating: 4,
          review_count: 2,
        },
        {
          id: 'provider-empty',
          provider_type: 'DOCTOR',
          name: 'No Reviews Doctor',
          email: null,
          phone: null,
          visit_stability: 'STABLE_VISIT',
          status: 'ACTIVE',
          publication_status: 'UNPUBLISHED',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          thumbnail_url: null,
          average_rating: null,
          review_count: 0,
        },
      ],
      meta: { page: 1, page_size: 10, total: 2, total_pages: 1 },
    });

    render(<MemoryRouter><ProvidersPage /></MemoryRouter>);

    expect(await screen.findByText('Reviewed Clinic')).toBeTruthy();
    expect(screen.getByText('★ 4.0')).toBeTruthy();
    expect(
      screen.getByRole('link', { name: 'View 2 reviews for Reviewed Clinic' }).getAttribute('href')
    ).toBe('/admin/reviews?provider_id=provider-reviewed');
    expect(screen.getByText('No Reviews Doctor')).toBeTruthy();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});