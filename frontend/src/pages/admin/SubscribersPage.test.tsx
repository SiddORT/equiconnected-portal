import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
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
  const emptyResponse = {
    ...response,
    data: [],
    meta: { ...response.meta, total: 0, total_pages: 0 },
  };

  it('shows an empty state without pagination while keeping search, filters, and export available', async () => {
    vi.mocked(adminApi.listSubscribers).mockResolvedValue(emptyResponse);
    render(<MemoryRouter><SubscribersPage /></MemoryRouter>);

    expect(await screen.findByText('No subscribers yet')).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
    expect(screen.getByRole('searchbox', { name: 'Search subscribers' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Filters' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeTruthy();
  });

  it('hides pagination when search and type filters return no subscribers', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.listSubscribers).mockImplementation(async (params) =>
      params?.search || params?.registration_type ? emptyResponse : response
    );
    render(<MemoryRouter><SubscribersPage /></MemoryRouter>);

    expect(await screen.findByLabelText('Pagination')).toBeTruthy();
    await user.type(screen.getByRole('searchbox', { name: 'Search subscribers' }), 'missing');
    expect(await screen.findByText('No subscribers found')).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();

    await user.clear(screen.getByRole('searchbox', { name: 'Search subscribers' }));
    expect(await screen.findByLabelText('Pagination')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Filters' }));
    await user.click(screen.getByRole('button', { name: 'Vet' }));
    await waitFor(() => expect(adminApi.listSubscribers).toHaveBeenLastCalledWith(
      expect.objectContaining({ registration_type: 'VET', page: 1 }),
    ));
    expect(await screen.findByText('No subscribers found')).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
  });

  it('keeps pagination usable for populated results and hides it while reloading or on error', async () => {
    const user = userEvent.setup();
    let rejectNext!: (error: Error) => void;
    const pending = new Promise<typeof response>((_, reject) => { rejectNext = reject; });
    vi.mocked(adminApi.listSubscribers)
      .mockResolvedValueOnce({ ...response, meta: { ...response.meta, total: 30, total_pages: 2 } })
      .mockImplementationOnce(() => pending);
    render(<MemoryRouter><SubscribersPage /></MemoryRouter>);

    expect(await screen.findByText('Showing 1 to 25 of 30 entries')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Next/ }));
    await waitFor(() => expect(adminApi.listSubscribers).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2 }),
    ));
    expect(screen.queryByLabelText('Pagination')).toBeNull();
    rejectNext(new Error('Network unavailable'));
    expect(await screen.findByText('Failed to load subscribers')).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
  });

  it('does not restore pagination when an older populated search finishes after an empty search', async () => {
    let resolveOld!: (value: typeof response) => void;
    const oldSearch = new Promise<typeof response>((resolve) => { resolveOld = resolve; });
    vi.mocked(adminApi.listSubscribers).mockImplementation((params) =>
      params?.search === 'old' ? oldSearch : Promise.resolve(emptyResponse)
    );
    const user = userEvent.setup();
    render(<MemoryRouter><SubscribersPage /></MemoryRouter>);
    expect(await screen.findByText('No subscribers yet')).toBeTruthy();

    const search = screen.getByRole('searchbox', { name: 'Search subscribers' });
    await user.type(search, 'old');
    await waitFor(() => expect(adminApi.listSubscribers).toHaveBeenCalledWith(
      expect.objectContaining({ search: 'old' })
    ));
    await user.clear(search);
    await user.type(search, 'new');
    expect(await screen.findByText('No subscribers found')).toBeTruthy();

    await act(async () => {
      resolveOld(response);
      await oldSearch;
    });
    expect(screen.getByText('No subscribers found')).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
  });

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