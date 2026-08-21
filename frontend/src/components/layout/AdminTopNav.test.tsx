import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { AdminTopNav } from './AdminTopNav';

const mockLogout = vi.hoisted(() => vi.fn());

vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'admin-id',
      email: 'admin@example.com',
      first_name: 'Admin',
      last_name: 'User',
      full_name: 'Admin User',
      role: 'admin',
      roles: ['admin'],
      email_verified_at: null,
      is_active: true,
    },
    logout: mockLogout,
  }),
}));

afterEach(cleanup);

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

describe('AdminTopNav', () => {
  it('does not show a standalone logout control in the top bar', () => {
    render(<MemoryRouter><AdminTopNav /></MemoryRouter>);
    expect(screen.queryByRole('button', { name: 'Log out' })).toBeNull();
  });

  it('keeps logout in the profile menu and redirects after signing out', async () => {
    const user = userEvent.setup();
    mockLogout.mockResolvedValueOnce(undefined);
    render(
      <MemoryRouter>
        <AdminTopNav />
        <LocationProbe />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole('button', { name: 'Open profile menu' }));
    const logoutItem = screen.getByRole('menuitem', { name: 'Logout' });
    expect(logoutItem).toBeTruthy();
    await user.click(logoutItem);
    expect(mockLogout).toHaveBeenCalledOnce();
    expect(screen.getByTestId('location').textContent).toBe('/admin/login');
  });

  it('links the profile menu to the email delivery history', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AdminTopNav /></MemoryRouter>);
    await user.click(screen.getByRole('button', { name: 'Open profile menu' }));
    const link = screen.getByRole('menuitem', { name: 'Email Logs' });
    expect(link.getAttribute('href')).toBe('/admin/email-logs');
  });

  it('promotes Registrations to the top-level navigation with its existing destination', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <AdminTopNav />
      </MemoryRouter>
    );

    const navigation = screen.getByRole('navigation', { name: 'Admin navigation' });
    const registrationsLink = within(navigation).getByRole('link', { name: 'Registrations' });

    expect(registrationsLink.getAttribute('href')).toBe('/admin/users');
    expect(registrationsLink.getAttribute('aria-current')).toBe('page');
    expect(screen.queryByRole('menuitem', { name: 'Users' })).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Directory Management' }));

    expect(screen.queryByRole('menuitem', { name: 'Users' })).toBeNull();
    expect(screen.getByRole('menuitem', { name: 'Specializations' }).getAttribute('href')).toBe(
      '/admin/specializations'
    );
    expect(screen.getByRole('menuitem', { name: 'Providers' }).getAttribute('href')).toBe(
      '/admin/providers'
    );
    expect(screen.getByRole('menuitem', { name: 'Invitations' }).getAttribute('href')).toBe(
      '/admin/invitations'
    );
    expect(screen.getByRole('menuitem', { name: 'Reviews' }).getAttribute('href')).toBe(
      '/admin/reviews'
    );
  });
});
