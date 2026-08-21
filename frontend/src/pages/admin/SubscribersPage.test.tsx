import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { SubscribersPage } from './SubscribersPage';

vi.mock('@/api/admin', () => ({ listSubscribers: vi.fn() }));
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({ formatTimestamp: (value: string) => value }),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('SubscribersPage', () => {
  it('lists subscriber registrations and filters by registration type', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.listSubscribers).mockResolvedValue({
      data: [{
        id: 'subscriber-1',
        email: 'vet@example.com',
        registration_type: 'VET',
        submitted_at: '2026-08-21T12:00:00Z',
      }],
      meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
    });
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
});