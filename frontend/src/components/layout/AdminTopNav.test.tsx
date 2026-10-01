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
  it('shows Analytics only in the open profile menu, above Activity Logs', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AdminTopNav /><LocationProbe /></MemoryRouter>);
    const navigation = screen.getByRole('navigation', { name: 'Admin navigation' });
    expect(within(navigation).queryByRole('link', { name: 'Analytics' })).toBeNull();
    expect(screen.queryByText('Analytics')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Open profile menu' }));
    const menu = screen.getByRole('menu', { name: 'Profile options' });
    const analytics = within(menu).getByRole('menuitem', { name: 'Analytics' });
    expect(analytics.getAttribute('href')).toBe('/admin/analytics');
    expect(analytics.getAttribute('aria-current')).toBeNull();
    expect(analytics.className).not.toContain('dropdownItem--active');
    const labels = within(menu).getAllByRole('menuitem').map((item) =>
      Array.from(item.childNodes)
        .filter((node) => node.nodeType === Node.TEXT_NODE)
        .map((node) => node.textContent)
        .join('').trim(),
    );
    expect(labels.indexOf('Analytics') + 1).toBe(labels.indexOf('Activity Logs'));
    if (labels.includes('User Manual')) {
      expect(labels[0]).toBe('User Manual');
      expect(labels[1]).toBe('Analytics');
    }
    for (const name of ['Activity Logs', 'Email Logs', 'Settings', 'Logout']) {
      expect(within(menu).getByRole('menuitem', { name })).toBeTruthy();
    }

    await user.click(analytics);
    expect(screen.getByTestId('location').textContent).toBe('/admin/analytics');
    expect(screen.queryByRole('menu', { name: 'Profile options' })).toBeNull();
    expect(within(navigation).queryByRole('link', { name: 'Analytics' })).toBeNull();
  });

  it('marks Analytics active and closes on selection even at its existing URL', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/admin/analytics']}><AdminTopNav /></MemoryRouter>);
    await user.click(screen.getByRole('button', { name: 'Open profile menu' }));
    const analytics = screen.getByRole('menuitem', { name: 'Analytics' });
    expect(analytics.getAttribute('aria-current')).toBe('page');
    expect(analytics.className).toContain('dropdownItem--active');
    await user.click(analytics);
    expect(screen.queryByRole('menu', { name: 'Profile options' })).toBeNull();
  });

  it('supports keyboard activation of Analytics and profile-menu dismissal', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AdminTopNav /><LocationProbe /></MemoryRouter>);
    const trigger = screen.getByRole('button', { name: 'Open profile menu' });
    trigger.focus();
    await user.keyboard('{Enter}');
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    await user.tab();
    if (document.activeElement?.textContent?.includes('User Manual')) await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('menuitem', { name: 'Analytics' }));
    await user.keyboard('{Enter}');
    expect(screen.getByTestId('location').textContent).toBe('/admin/analytics');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');

    await user.click(trigger);
    await user.tab();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu', { name: 'Profile options' })).toBeNull();
    await user.click(trigger);
    await user.click(document.body);
    expect(screen.queryByRole('menu', { name: 'Profile options' })).toBeNull();
  });

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

  it('groups Subscribers and Contact Enquiries under an active Enquiries menu', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/admin/subscribers']}><AdminTopNav /></MemoryRouter>);
    const navigation = screen.getByRole('navigation', { name: 'Admin navigation' });
    const enquiriesTrigger = within(navigation).getByRole('button', { name: 'Enquiries' });
    expect(enquiriesTrigger.className).toContain('link--active');
    expect(within(navigation).queryByRole('link', { name: 'Subscribers' })).toBeNull();

    await user.click(enquiriesTrigger);
    const menu = screen.getByRole('menu', { name: 'Enquiries' });
    const subscribersLink = within(menu).getByRole('menuitem', { name: 'Subscribers' });
    expect(subscribersLink.getAttribute('href')).toBe('/admin/subscribers');
    expect(subscribersLink.getAttribute('aria-current')).toBe('page');
    expect(within(menu).getByRole('menuitem', { name: 'Contact Enquiries' }).getAttribute('href'))
      .toBe('/admin/contact-enquiries');
  });

  it('activates the Contact Enquiries child for detail routes and closes menus on navigation', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/contact-enquiries/enquiry-1?search=horse']}>
        <AdminTopNav />
        <LocationProbe />
      </MemoryRouter>
    );
    const navigation = screen.getByRole('navigation', { name: 'Admin navigation' });
    const enquiriesTrigger = within(navigation).getByRole('button', { name: 'Enquiries' });
    expect(enquiriesTrigger.className).toContain('link--active');
    await user.click(enquiriesTrigger);
    const contactLink = screen.getByRole('menuitem', { name: 'Contact Enquiries' });
    expect(contactLink.getAttribute('aria-current')).toBe('page');
    await user.click(contactLink);
    expect(screen.queryByRole('menu', { name: 'Enquiries' })).toBeNull();
    expect(screen.getByTestId('location').textContent).toBe('/admin/contact-enquiries');
  });

  it('keeps grouped menus mutually exclusive and dismisses Enquiries with outside click or Escape', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AdminTopNav /></MemoryRouter>);
    await user.click(screen.getByRole('button', { name: 'Directory Management' }));
    expect(screen.getByRole('menu', { name: 'Directory Management' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Enquiries' }));
    expect(screen.queryByRole('menu', { name: 'Directory Management' })).toBeNull();
    expect(screen.getByRole('menu', { name: 'Enquiries' })).toBeTruthy();

    await user.click(document.body);
    expect(screen.queryByRole('menu', { name: 'Enquiries' })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Enquiries' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu', { name: 'Enquiries' })).toBeNull();
  });

  it('groups provider destinations inside Directory Management and closes it with Escape', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/provider-applications']}>
        <AdminTopNav />
      </MemoryRouter>,
    );

    const navigation = screen.getByRole('navigation', { name: 'Admin navigation' });
    expect(within(navigation).queryByRole('button', { name: 'Provider' })).toBeNull();
    const directoryMenuButton = within(navigation).getByRole('button', { name: 'Directory Management' });
    expect(directoryMenuButton.className).toContain('link--active');

    expect(within(navigation).queryByRole('link', { name: 'Provider applications' })).toBeNull();
    await user.click(directoryMenuButton);
    const directoryMenu = screen.getByRole('menu', { name: 'Directory Management' });
    expect(within(directoryMenu).getByRole('menuitem', { name: 'Providers' }).getAttribute('href')).toBe('/admin/providers');
    const applicationsLink = within(directoryMenu).getByRole('menuitem', { name: 'Provider applications' });
    expect(applicationsLink.getAttribute('href')).toBe('/admin/provider-applications');
    expect(applicationsLink.getAttribute('aria-current')).toBe('page');
    expect(within(directoryMenu).getByRole('menuitem', { name: 'Specializations' })).toBeTruthy();

    await user.click(document.body);
    expect(screen.queryByRole('menu', { name: 'Directory Management' })).toBeNull();

    await user.click(directoryMenuButton);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu', { name: 'Directory Management' })).toBeNull();
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
