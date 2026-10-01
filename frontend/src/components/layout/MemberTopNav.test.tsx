import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { MemberTopNav } from './MemberTopNav';
import { readFileSync } from 'node:fs';

const { logout, getProfile, getRecentMemberHistory } = vi.hoisted(() => ({
  logout: vi.fn(),
  getProfile: vi.fn(),
  getRecentMemberHistory: vi.fn(),
}));

vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'member-id',
      email: 'rider@example.com',
      first_name: 'Amina',
      last_name: 'Rider',
      full_name: 'amina rider',
      role: 'horse_owner',
      roles: ['horse_owner'],
      email_verified_at: '2026-08-21T00:00:00Z',
      last_successful_login_at: '2026-08-21T00:00:00Z',
      is_active: true,
    },
    logout,
  }),
}));
vi.mock('@/api/profile', () => ({ getProfile }));
vi.mock('@/api/memberFeedback', () => ({ getRecentMemberHistory, submitPlatformFeedback: vi.fn() }));
vi.mock('@/components/messaging/useMessageUnreadCount', () => ({ useMessageUnreadCount: () => 3 }));

beforeEach(() => {
  getProfile.mockResolvedValue({ horses: [{ id: 'horse-1' }] });
  getRecentMemberHistory.mockResolvedValue([{
    id: 'history-1', event_key: 'search:1', type: 'search', occurred_at: '2026-08-21T12:00:00Z',
    provider_id: null, provider_name: null, provider_available: null, filters: { name: 'field vet' },
  }]);
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('MemberTopNav', () => {
  it('keeps the account name visible and truncated at narrow mobile widths', () => {
    const css = readFileSync('src/components/layout/MemberTopNav.module.css', 'utf8');
    expect(css).toMatch(/@media\(max-width:460px\)\{[^]*?\.accountIdentity\{display:flex;/);
    expect(css).toMatch(/\.accountIdentity strong\{[^}]*text-overflow:ellipsis;white-space:nowrap/);
    expect(css).toContain('@media(max-width:360px){.brand small{display:none}.brand strong{max-width:95px;font-size:12px}.avatar{display:none}.accountIdentity{max-width:58px}');
  });

  it('provides member navigation, identity, and a visible logout control', () => {
    render(<MemoryRouter><MemberTopNav /></MemoryRouter>);

    expect(screen.getByRole('link', { name: 'Providers' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Profile' })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Messages/ }).getAttribute('href')).toBe('/member/messages');
    expect(screen.getByLabelText('3 unread messages')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Account menu for Amina Rider' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Logout' })).toBeNull();
    expect(screen.getByText('Amina Rider')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'EquiConnected home' }).querySelector('img')?.getAttribute('src')).toBe('/logo.png');
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

  it('opens an account menu with persisted profile details and recent member activity', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><MemberTopNav /></MemoryRouter>);
    await user.click(screen.getByRole('button', { name: 'Account menu for Amina Rider' }));
    expect(await screen.findByText('1 horse in your care')).toBeTruthy();
    expect(screen.getByText('Horse owner')).toBeTruthy();
    expect(await screen.findByText('Provider search')).toBeTruthy();
    expect(screen.getByRole('menuitem', { name: 'My Reviews & Feedback' }).getAttribute('href')).toBe('/my-reviews');
    expect(screen.getByRole('menuitem', { name: 'View all' }).getAttribute('href')).toBe('/history');
    expect(screen.getByRole('menuitem', { name: 'Profile' }).getAttribute('href')).toBe('/profile');
    expect(screen.getByRole('menuitem', { name: 'Reset password' }).getAttribute('href')).toBe('/forgot-password');
    expect(screen.getByRole('menuitem', { name: 'Sign out' })).toBeTruthy();
  });

  it('refreshes profile and history after member activity events and closes on Escape with focus return', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><MemberTopNav /></MemoryRouter>);
    const accountButton = screen.getByRole('button', { name: 'Account menu for Amina Rider' });
    await user.click(accountButton);
    await screen.findByText('Provider search');
    getProfile.mockClear();
    getRecentMemberHistory.mockClear();
    window.dispatchEvent(new Event('member-profile-changed'));
    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(1));
    expect(getRecentMemberHistory).toHaveBeenCalledTimes(1);
    await user.keyboard('{Escape}');
    expect(accountButton.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(accountButton);
  });

  it('supports arrow-key movement through the account menu and outside-click dismissal', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><MemberTopNav /></MemoryRouter>);
    const accountButton = screen.getByRole('button', { name: 'Account menu for Amina Rider' });
    await user.click(accountButton);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('menuitem', { name: 'View all' })));
    await user.keyboard('{ArrowDown}');
    expect(document.activeElement?.textContent).toContain('Provider search');
    await user.keyboard('{End}');
    expect(document.activeElement).toBe(screen.getByRole('menuitem', { name: 'Sign out' }));
    await user.keyboard('{Home}');
    expect(document.activeElement).toBe(screen.getByRole('menuitem', { name: 'View all' }));
    await user.tab();
    expect(document.activeElement?.textContent).toContain('Provider search');
    await user.click(screen.getByRole('link', { name: 'EquiConnected home' }));
    expect(accountButton.getAttribute('aria-expanded')).toBe('false');
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

    await user.click(screen.getByRole('button', { name: 'Account menu for Amina Rider' }));
    await user.click(await screen.findByRole('menuitem', { name: 'Sign out' }));
    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('Member sign-in')).toBeTruthy();
  });
});