import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '@/app/AuthContext';
import { AboutPage } from './AboutPage';

vi.mock('@/app/AuthContext', () => ({ useAuth: vi.fn() }));

const guest = () => ({
  user: null, isAuthenticated: false, isLoading: false, login: vi.fn(), logout: vi.fn(),
});
const member = {
  id: 'sample-member', email: 'sample@example.test', full_name: 'Sample Rider',
  first_name: 'Sample', last_name: 'Rider', role: 'horse_owner', roles: ['horse_owner'],
  is_active: true, email_verified_at: '2026-09-01', last_successful_login_at: null,
};
const renderPage = () => render(<MemoryRouter><AboutPage /></MemoryRouter>);

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue(guest());
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('AboutPage', () => {
  it('renders structured reference sections in order and restores the title', () => {
    const title = document.title;
    const view = renderPage();
    expect(document.title).toBe('About EquiConnected | EquiConnected');
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' });
    expect(screen.getByRole('heading', { level: 1, name: 'Made by horse people, for horse people.' })).toBeTruthy();
    expect(Array.from(document.querySelectorAll('main > section')).map((el) => el.id)).toEqual([
      'about-hero', 'about-mission', 'about-story', 'about-promises',
      'about-review', 'about-community', 'about-join',
    ]);
    expect(within(document.getElementById('about-promises')!).getAllByRole('article')).toHaveLength(4);
    const community = within(document.getElementById('about-community')!);
    for (const name of ['Riders & owners', 'Stable managers', 'Vets', 'Hospitals & clinics']) {
      expect(community.getByRole('heading', { name })).toBeTruthy();
    }
    expect(screen.getByRole('link', { name: /Scroll to discover/ }).getAttribute('href')).toBe('#about-mission');
    expect(document.getElementById('about-review')!.textContent).not.toContain('Every profile is checked');
    view.unmount();
    expect(document.title).toBe(title);
  });

  it('offers working guest, provider, footer and cross-page anchor destinations', () => {
    renderPage();
    expect(screen.getByRole('link', { name: /Find equine care/ }).getAttribute('href')).toBe('/signup');
    expect(screen.getByRole('link', { name: 'I provide care' }).getAttribute('href')).toBe('/provider/signup');
    const footer = within(screen.getByRole('contentinfo'));
    expect(footer.getByRole('link', { name: 'About EquiConnected' }).getAttribute('href')).toBe('/about');
    expect(footer.getByRole('link', { name: 'Contact us' }).getAttribute('href')).toBe('/#contact');
    expect(footer.getByRole('link', { name: 'How it works' }).getAttribute('href')).toBe('/#how-it-works');
    const navigation = within(screen.getByRole('navigation', { name: 'Primary navigation' }));
    expect(navigation.getByRole('link', { name: 'For horse people' }).getAttribute('href')).toBe('/#owners');
    expect(navigation.getByRole('link', { name: 'For providers' }).getAttribute('href')).toBe('/#providers');
  });

  it('routes verified members to care and keeps provider signup available', () => {
    vi.mocked(useAuth).mockReturnValue({ ...guest(), isAuthenticated: true, user: member });
    renderPage();
    expect(screen.getByRole('link', { name: 'Directory' }).getAttribute('href')).toBe('/providers');
    expect(screen.getByRole('link', { name: /Explore providers/ }).getAttribute('href')).toBe('/providers');
    expect(within(screen.getByRole('contentinfo')).getByRole('link', { name: 'Find a provider' }).getAttribute('href')).toBe('/providers');
    expect(screen.getByRole('link', { name: 'I provide care' }).getAttribute('href')).toBe('/provider/signup');
  });

  it.each([
    { user: member, isLoading: true },
    { user: { ...member, email_verified_at: null }, isLoading: false },
    { user: { ...member, is_active: false }, isLoading: false },
    { user: { ...member, role: 'provider', roles: ['provider'] }, isLoading: false },
  ])('does not offer member care access for an ineligible session', (state) => {
    vi.mocked(useAuth).mockReturnValue({ ...guest(), isAuthenticated: true, ...state });
    renderPage();
    expect(screen.queryByRole('link', { name: 'Directory' })).toBeNull();
    expect(screen.getByRole('link', { name: /Find equine care/ }).getAttribute('href')).toBe('/signup');
    expect(within(screen.getByRole('contentinfo')).getByRole('link', { name: 'Create an account' }).getAttribute('href')).toBe('/signup');
  });

  it('closes nested choices before the menu on Escape and returns keyboard focus', async () => {
    const user = userEvent.setup();
    renderPage();
    const menu = screen.getByRole('button', { name: 'Menu' });
    await user.click(menu);
    const signin = screen.getByRole('button', { name: 'Sign in' });
    await user.click(signin);
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Members — horse owners & stable managers' }));
    await user.keyboard('{Escape}');
    expect(signin.getAttribute('aria-expanded')).toBe('false');
    expect(menu.getAttribute('aria-expanded')).toBe('true');
    expect(document.activeElement).toBe(signin);
    await user.keyboard('{Escape}');
    expect(menu.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(menu);
    await user.click(menu);
    await user.click(screen.getByRole('button', { name: 'Join EquiConnected' }));
    await user.click(screen.getByRole('link', { name: 'Providers — vets, clinics & hospitals' }));
    expect(menu.getAttribute('aria-expanded')).toBe('false');
    expect(screen.getByRole('button', { name: 'Join EquiConnected' }).getAttribute('aria-expanded')).toBe('false');
  });
});