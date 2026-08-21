import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { ProviderApplicationsPage } from './ProviderApplicationsPage';

vi.mock('@/api/admin', () => ({
  approveProviderApplication: vi.fn(),
  listProviderApplications: vi.fn(),
  rejectProviderApplication: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => value,
  }),
}));

const application = {
  id: 'application-1',
  user_id: 'user-1',
  provider_id: null,
  provider_type: 'CLINIC' as const,
  provider_name: 'Austin Equine Clinic',
  visit_stability: 'NOT_STABLE_VISIT' as const,
  review_status: 'PENDING_REVIEW' as const,
  first_name: 'Amina',
  last_name: 'Rider',
  full_name: 'Amina Rider',
  email: 'amina@example.com',
  mobile_number: null,
  country: 'United States',
  state_province: 'Texas',
  city: 'Austin',
  email_verified_at: '2026-08-21T12:00:00Z',
  reviewed_by_user_id: null,
  reviewed_by_name: null,
  reviewed_at: null,
  rejection_reason: null,
  created_at: '2026-08-21T12:00:00Z',
};

function response(data: typeof application[], total = data.length) {
  return {
    data,
    meta: { page: 1, page_size: 10, total, total_pages: total === 0 ? 0 : 1 },
  };
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ProviderApplicationsPage', () => {
  it('hides list controls for an unfiltered empty provider application collection', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([]));

    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    expect(await screen.findByText('No provider applications yet')).toBeTruthy();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Filters' })).toBeNull();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
    expect(screen.queryByLabelText('Rows per page')).toBeNull();
    expect(screen.queryByText('Showing 0 to 0 of 0 entries')).toBeNull();
  });

  it('shows list controls and pagination for a single provider application', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([application]));
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    expect(await screen.findByText('Austin Equine Clinic')).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Filters' })).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();
    const pageSize = screen.getByLabelText('Rows per page');
    expect(screen.getByText('Showing 1 to 1 of 1 entries')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Previous/ }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: /Next/ }).hasAttribute('disabled')).toBe(true);

    await user.selectOptions(pageSize, '25');
    await waitFor(() => expect(adminApi.listProviderApplications).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, page_size: 25 }),
    ));
  });

  it('keeps list controls available when active criteria return no provider applications', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([]));

    render(
      <MemoryRouter initialEntries={['/admin/provider-applications?search=missing@example.com']}>
        <ProviderApplicationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('No provider applications found')).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Filters' })).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();
    expect(screen.getByLabelText('Rows per page')).toBeTruthy();
  });
});