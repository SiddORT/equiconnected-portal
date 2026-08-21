import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import type { AdminUser } from '@/types';
import { UsersPage } from './UsersPage';

vi.mock('@/api/admin', () => ({
  listAdminUsers: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => value,
  }),
}));

const user: AdminUser = {
  id: 'user-1',
  first_name: 'Amina',
  last_name: 'Rider',
  full_name: 'Amina Rider',
  email: 'amina@example.com',
  mobile_number: '+15551234567',
  country: 'United States',
  city: 'Austin',
  roles: ['horse_owner'],
  email_verified_at: '2026-08-21T12:00:00Z',
  created_at: '2026-08-21T12:00:00Z',
};

function response(data: AdminUser[], total = data.length) {
  return {
    data,
    meta: { page: 1, page_size: 10, total, total_pages: total === 0 ? 0 : 1 },
  };
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('UsersPage', () => {
  it('hides table controls for an unfiltered empty account collection', async () => {
    vi.mocked(adminApi.listAdminUsers).mockResolvedValue(response([]));

    render(<MemoryRouter><UsersPage /></MemoryRouter>);

    expect(await screen.findByText('No registered accounts yet')).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Filters/ })).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
    expect(screen.queryByLabelText('Rows per page')).toBeNull();
    expect(screen.queryByText('Showing 0 to 0 of 0 entries')).toBeNull();
    expect(screen.queryByRole('button', { name: /Previous/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /Next/ })).toBeNull();
  });

  it('hides table controls when active criteria return no accounts', async () => {
    vi.mocked(adminApi.listAdminUsers).mockResolvedValue(response([]));

    render(
      <MemoryRouter initialEntries={['/admin/users?search=missing@example.com']}>
        <UsersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('No accounts found')).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Filters/ })).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
    expect(screen.queryByLabelText('Rows per page')).toBeNull();
    expect(screen.queryByText('Showing 0 to 0 of 0 entries')).toBeNull();
  });

  it('shows normal table controls for a populated account collection', async () => {
    vi.mocked(adminApi.listAdminUsers).mockResolvedValue(response([user]));
    const event = userEvent.setup();

    render(<MemoryRouter><UsersPage /></MemoryRouter>);

    expect(await screen.findByText('Amina Rider')).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();
    const pageSize = screen.getByLabelText('Rows per page');
    expect(screen.getByText('Showing 1 to 1 of 1 entries')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Previous/ }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: /Next/ }).hasAttribute('disabled')).toBe(true);

    await event.selectOptions(pageSize, '25');
    await waitFor(() => expect(adminApi.listAdminUsers).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, page_size: 25 }),
    ));
  });
});