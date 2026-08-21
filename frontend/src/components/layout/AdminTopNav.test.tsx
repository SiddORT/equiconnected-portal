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
  });

  it('groups provider destinations in an active Provider menu and closes it with Escape', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/provider-applications']}>
        <AdminTopNav />
      </MemoryRouter>,
    );

    const navigation = screen.getByRole('navigation', { name: 'Admin navigation' });
    const providerMenuButton = within(navigation).getByRole('button', { name: 'Provider' });
    expect(within(navigation).queryByRole('link', { name: 'Provider applications' })).toBeNull();
    expect(providerMenuButton.className).toContain('link--active');

    await user.click(providerMenuButton);
    const providerMenu = screen.getByRole('menu', { name: 'Provider' });
    expect(within(providerMenu).getByRole('menuitem', { name: 'Providers' }).getAttribute('href')).toBe('/admin/providers');
    const applicationsLink = within(providerMenu).getByRole('menuitem', { name: 'Provider applications' });
    expect(applicationsLink.getAttribute('href')).toBe('/admin/provider-applications');
    expect(applicationsLink.getAttribute('aria-current')).toBe('page');

    await user.click(document.body);
    expect(screen.queryByRole('menu', { name: 'Provider' })).toBeNull();

    await user.click(providerMenuButton);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu', { name: 'Provider' })).toBeNull();
  });

  it('removes Profile and links Settings to the active admin settings route', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/settings']}>
        <AdminTopNav />
      </MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: 'Open profile menu' }));

    expect(screen.queryByRole('menuitem', { name: 'Profile' })).toBeNull();
    const settingsLink = screen.getByRole('menuitem', { name: 'Settings' });
    expect(settingsLink.getAttribute('href')).toBe('/admin/settings');
    expect(settingsLink.getAttribute('aria-current')).toBe('page');
  });
});
