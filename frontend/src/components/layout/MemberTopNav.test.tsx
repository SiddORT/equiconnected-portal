import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { MemberTopNav } from './MemberTopNav';

const { logout } = vi.hoisted(() => ({
  logout: vi.fn(),
}));

vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'member-id',
      email: 'rider@example.com',
      first_name: 'Amina',
      last_name: 'Rider',
      full_name: 'Amina Rider',
      role: 'horse_owner',
      roles: ['horse_owner'],
      email_verified_at: '2026-08-21T00:00:00Z',
      last_successful_login_at: '2026-08-21T00:00:00Z',
      is_active: true,
    },
    logout,
  }),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('MemberTopNav', () => {
  it('provides member navigation, identity, and a visible logout control', () => {
    render(<MemoryRouter><MemberTopNav /></MemoryRouter>);

    expect(screen.getByRole('link', { name: 'Providers' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Profile' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Logout' })).toBeTruthy();
    expect(screen.getByText('Amina Rider')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Open member navigation' }).getAttribute('aria-expanded')).toBe('false');
  });

  it('opens an accessible small-screen menu and closes it after a member navigation choice', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/providers']}><MemberTopNav /></MemoryRouter>);

    const menu = screen.getByRole('button', { name: 'Open member navigation' });
    await user.click(menu);
    expect(menu.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('navigation', { name: 'Member navigation' })).toBeTruthy();

    await user.click(screen.getByRole('link', { name: 'Profile' }));
    expect(screen.getByRole('button', { name: 'Open member navigation' }).getAttribute('aria-expanded')).toBe('false');
  });

  it('logs the member out once and redirects to member sign-in', async () => {
    const user = userEvent.setup();
    logout.mockResolvedValue(undefined);
    render(
      <MemoryRouter initialEntries={['/providers']}>
        <Routes>
          <Route path="/providers" element={<MemberTopNav />} />
          <Route path="/login" element={<p>Member sign-in</p>} />
        </Routes>
      </MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: 'Logout' }));
    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('Member sign-in')).toBeTruthy();
  });
});