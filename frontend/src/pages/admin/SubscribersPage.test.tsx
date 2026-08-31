import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { SubscribersPage } from './SubscribersPage';

vi.mock('@/api/admin', () => ({ listSubscribers: vi.fn(), exportSubscribers: vi.fn() }));
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({ formatTimestamp: (value: string) => value }),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('SubscribersPage', () => {
  const response = {
    data: [{
      id: 'subscriber-1',
      email: 'vet@example.com',
      registration_type: 'VET' as const,
      submitted_at: '2026-08-21T12:00:00Z',
    }],
    meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
  };

  it('lists subscriber registrations and filters by registration type', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.listSubscribers).mockResolvedValue(response);
    render(<MemoryRouter><SubscribersPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Subscribers' })).toBeTruthy();
    expect(screen.getByText('vet@example.com')).toBeTruthy();
    expect(screen.getByText('Vet')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Filters' }));
    await user.click(screen.getByRole('button', { name: 'Vet' }));
    await waitFor(() => expect(adminApi.listSubscribers).toHaveBeenLastCalledWith(
      expect.objectContaining({ registration_type: 'VET' }),
    ));
  });

  it('loads submitted-date filters from the URL and sends date changes as first-page requests', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.listSubscribers).mockResolvedValue({
      ...response,
      meta: { page: 3, page_size: 25, total: 75, total_pages: 3 },
    });
    render(
      <MemoryRouter initialEntries={['/?date_from=2026-08-01&date_to=2026-08-21&page=3']}>
        <SubscribersPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminApi.listSubscribers).toHaveBeenLastCalledWith(
      expect.objectContaining({
        date_from: '2026-08-01',
        date_to: '2026-08-21',
        page: 3,
      }),
    ));

    const fromDate = screen.getByLabelText('Submitted from');
    await user.clear(fromDate);
    await waitFor(() => expect(adminApi.listSubscribers).toHaveBeenLastCalledWith(
      expect.objectContaining({
        date_from: undefined,
        date_to: '2026-08-21',
        page: 1,
      }),
    ));
  });

  it('exports the exact active subscriber filters', async () => {
    vi.mocked(adminApi.listSubscribers).mockResolvedValue(response);
    vi.mocked(adminApi.exportSubscribers).mockResolvedValue();
    render(
      <MemoryRouter initialEntries={['/?search=vet&registration_type=VET&date_from=2026-08-01&date_to=2026-08-21']}>
        <SubscribersPage />
      </MemoryRouter>
    );

    await screen.findByText('vet@example.com');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Export CSV' }));
    await waitFor(() => expect(adminApi.exportSubscribers).toHaveBeenCalledWith({
      search: 'vet',
      registration_type: 'VET',
      date_from: '2026-08-01',
      date_to: '2026-08-21',
    }));
  });

  it('shows a clear in-page message when preparing an export fails', async () => {
    vi.mocked(adminApi.listSubscribers).mockResolvedValue(response);
    vi.mocked(adminApi.exportSubscribers).mockRejectedValue(new Error('network unavailable'));
    render(<MemoryRouter><SubscribersPage /></MemoryRouter>);

    await screen.findByText('vet@example.com');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Export CSV' }));
    expect((await screen.findByRole('alert')).textContent).toContain(
      'Unable to prepare the subscriber export. Please try again.'
    );
  });
});