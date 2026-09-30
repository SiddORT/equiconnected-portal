import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as publicApi from '@/api/public';
import { useAuth } from '@/app/AuthContext';
import { PublicPage } from './PublicPage';

vi.mock('@/api/public', () => ({
  recordPublicVisit: vi.fn(() => Promise.resolve()),
  registerSubscriber: vi.fn(),
}));

vi.mock('@/app/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  systemCalendarDate: () => '2026-08-31',
  useTimeSettings: () => ({
    settings: { timezone: 'UTC' },
    isLoading: false,
    error: null,
  }),
}));

function guestAuth() {
  return {
    isAuthenticated: false,
    isLoading: false,
    user: null,
    login: vi.fn(),
    logout: vi.fn(),
  };
}

function renderPage() {
  return render(<MemoryRouter><PublicPage /></MemoryRouter>);
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  window.history.replaceState(null, '', '/');
  vi.resetAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue(guestAuth());
  vi.mocked(publicApi.recordPublicVisit).mockResolvedValue(undefined);
  vi.mocked(publicApi.registerSubscriber).mockResolvedValue({ message: 'Thanks' });
});

describe('PublicPage', () => {
  it('provides the guest destinations in navigation and the footer', () => {
    renderPage();
    const footer = within(screen.getByRole('contentinfo'));
    const destinations: Array<[RegExp, string]> = [
      [/Create an account/, '/signup'],
      [/Sign in|Member sign in/, '/login'],
      [/Join the network|Join as a provider|Create a provider account/, '/provider/signup'],
      [/Provider sign in/, '/provider/login'],
      [/Admin login/, '/admin/login'],
      [/Privacy/, '/privacy-policy'],
      [/Terms of service/, '/terms-of-service'],
    ];

    for (const [name, href] of destinations) {
      const link = footer.getByRole('link', { name });
      expect(link.getAttribute('href')).toBe(href);
    }
    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' });
    expect(within(navigation).getByRole('link', { name: 'Sign in' }).getAttribute('href'))
      .toBe('/login');
    expect(within(navigation).getByRole('link', { name: 'Join EquiConnected' }).getAttribute('href'))
      .toBe('/signup');
  });

  it('greets a signed-in member and provides profile, sign-out, and directory actions', async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({
      ...guestAuth(),
      isAuthenticated: true,
      user: {
        id: 'member',
        email: 'ada@example.com',
        first_name: 'Ada',
        last_name: 'Rider',
        full_name: 'Ada Rider',
        role: 'horse_owner',
        roles: ['horse_owner'],
        email_verified_at: '2026-08-31',
        last_successful_login_at: null,
        is_active: true,
      },
      logout,
    });
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByText('Hi, Ada')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Profile' }).getAttribute('href')).toBe('/profile');
    expect(screen.getByRole('link', { name: 'Directory' }).getAttribute('href')).toBe('/providers');
    const hero = screen.getByRole('heading', { name: /Trusted equine care/i }).closest('section');
    expect(within(hero as HTMLElement).getByRole('link', { name: 'Find care' })
      .getAttribute('href')).toBe('/providers');
    expect(within(hero as HTMLElement).getByRole('link', { name: 'Open directory' })
      .getAttribute('href')).toBe('/providers');
    expect(screen.getByRole('link', { name: 'Explore Vets in the directory' }).getAttribute('href'))
      .toBe('/providers');
    const footer = within(screen.getByRole('contentinfo'));
    expect(footer.getByRole('link', { name: 'Your profile' }).getAttribute('href')).toBe('/profile');
    expect(footer.getByRole('link', { name: 'Provider directory' }).getAttribute('href')).toBe('/providers');
    expect(document.getElementById('care-near-you')).toBeNull();
    expect(within(document.getElementById('find')!).getByRole('link', { name: 'Check all providers' }).getAttribute('href')).toBe('/providers');

    await user.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(logout).toHaveBeenCalledOnce();
  });

  it('uses member-gated directory destinations for guests', () => {
    renderPage();

    expect(screen.queryByText(/Hi, /)).toBeNull();
    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' });
    expect(within(navigation).getByRole('link', { name: 'Join EquiConnected' }).getAttribute('href'))
      .toBe('/signup');
    const hero = screen.getByRole('heading', { name: /Trusted equine care/i }).closest('section');
    expect(within(hero as HTMLElement).getByRole('link', { name: 'Find care' })
      .getAttribute('href')).toBe('/signup');
    expect(within(hero as HTMLElement).getByRole('link', { name: 'Join EquiConnected' })
      .getAttribute('href')).toBe('/signup');
    expect(within(document.getElementById('find')!).getByRole('link', { name: 'Check all providers' }).getAttribute('href'))
      .toBe('/signup');
    expect(screen.getByRole('link', { name: 'Explore Vets in the directory' }).getAttribute('href'))
      .toBe('/signup');
  });

  it('shows the requested category description below the heading without changing the cards', () => {
    renderPage();

    const heading = document.getElementById('categories-heading')!;
    const section = heading.closest('section')!;
    expect(within(section).getByText('Who you’ll find')).toBeTruthy();
    expect(heading.nextElementSibling?.textContent).toBe(
      'From the ambulatory vet who knows your yard to the hospital with a surgical suite — all verified, all searchable.',
    );
    expect(within(section).queryByText(/From independent veterinary professionals/)).toBeNull();
    for (const title of ['Vets', 'Clinics', 'Hospitals']) {
      expect(within(section).getByRole('heading', { level: 3, name: title })).toBeTruthy();
    }
  });

  it('keeps member-only controls private while auth is restoring or resolves to a nonmember', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...guestAuth(),
      isAuthenticated: true,
      isLoading: true,
      user: {
        id: 'admin',
        email: 'admin@example.com',
        first_name: 'Admin',
        last_name: null,
        full_name: 'Admin',
        role: 'admin',
        roles: ['admin'],
        email_verified_at: '2026-08-31',
        last_successful_login_at: null,
        is_active: true,
      },
    });
    const view = renderPage();
    expect(screen.queryByText(/Hi, /)).toBeNull();
    expect(screen.queryByRole('link', { name: 'Profile' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Sign out' })).toBeNull();

    vi.mocked(useAuth).mockReturnValue({
      ...vi.mocked(useAuth).mock.results[0].value,
      isLoading: false,
    });
    view.rerender(<MemoryRouter><PublicPage /></MemoryRouter>);
    expect(screen.queryByText(/Hi, /)).toBeNull();
    expect(screen.queryByRole('link', { name: 'Profile' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Directory' })).toBeNull();
    const hero = screen.getByRole('heading', { name: /Trusted equine care/i }).closest('section');
    expect(within(hero as HTMLElement).getByRole('link', { name: 'Find care' })
      .getAttribute('href')).toBe('/signup');
  });

  it('validates subscriber role and email before sending a registration', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: /keep me posted/i }));
    expect(screen.getByRole('alert').textContent).toContain('Please choose how you would like to register.');
    expect(publicApi.registerSubscriber).not.toHaveBeenCalled();

    await user.selectOptions(screen.getByLabelText('Your role'), 'VET');
    await user.type(screen.getByLabelText('Email address'), 'not-an-email');
    await user.click(screen.getByRole('button', { name: /keep me posted/i }));
    expect(screen.getByRole('alert').textContent).toContain('Please enter a valid email address.');
    expect(publicApi.registerSubscriber).not.toHaveBeenCalled();
  });

  it('submits a valid subscriber and announces success', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByLabelText('Your role'), 'HORSE_OWNER');
    await user.type(screen.getByLabelText('Email address'), ' owner@example.com ');
    await user.click(screen.getByRole('button', { name: /keep me posted/i }));
    await waitFor(() => expect(publicApi.registerSubscriber).toHaveBeenCalledWith({
      email: 'owner@example.com',
      registration_type: 'HORSE_OWNER',
    }));
    expect((await screen.findByText('You’re on the list.')).parentElement?.textContent)
      .toContain('team will be in touch soon');
  });

  it('announces subscriber API errors without showing the success state', async () => {
    vi.mocked(publicApi.registerSubscriber).mockRejectedValue(new Error('Service unavailable'));
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByLabelText('Your role'), 'CLINIC');
    await user.type(screen.getByLabelText('Email address'), 'clinic@example.com');
    await user.click(screen.getByRole('button', { name: /keep me posted/i }));

    expect((await screen.findByRole('alert')).textContent)
      .toContain('We could not save your registration. Please try again shortly.');
    expect(screen.queryByText('You’re on the list.')).toBeNull();
  });

  it('tracks one public visit per local date and retries after a failed request', async () => {
    vi.mocked(publicApi.recordPublicVisit)
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce(undefined);
    const first = renderPage();
    await waitFor(() => expect(publicApi.recordPublicVisit).toHaveBeenCalledOnce());
    await waitFor(() => expect(window.localStorage.getItem('equiconnected-public-visit-date')).toBeNull());
    first.unmount();

    const second = renderPage();
    await waitFor(() => expect(publicApi.recordPublicVisit).toHaveBeenCalledTimes(2));
    expect(window.localStorage.getItem('equiconnected-public-visit-date')).toBe('2026-08-31');
    second.unmount();

    renderPage();
    expect(publicApi.recordPublicVisit).toHaveBeenCalledTimes(2);
  });

  it('scrolls to and focuses a section heading addressed by the URL hash', async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    });
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    window.history.replaceState(null, '', '/#care');

    renderPage();
    const heading = screen.getByRole('heading', { name: /Every horse deserves care/i });
    await waitFor(() => expect(document.activeElement).toBe(heading));
    expect(scrollIntoView).toHaveBeenCalledOnce();
    expect(heading.getAttribute('tabindex')).toBe('-1');
  });

  it('keeps the owners anchor keyboard-accessible', async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    });
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    window.history.replaceState(null, '', '/#owners');
    renderPage();

    const heading = screen.getByRole('heading', { name: 'Your horses, known by heart — and on file.' });
    await waitFor(() => expect(document.activeElement).toBe(heading));
    expect(scrollIntoView).toHaveBeenCalledOnce();
  });

  it('opens the responsive navigation and closes it on Escape', async () => {
    const user = userEvent.setup();
    renderPage();
    const toggle = screen.getByRole('button', { name: 'Menu' });

    await user.click(toggle);
    expect(screen.getByRole('button', { name: 'Close' }).getAttribute('aria-expanded')).toBe('true');
    await user.keyboard('{Escape}');
    expect(screen.getByRole('button', { name: 'Menu' }).getAttribute('aria-expanded')).toBe('false');
  });

  it('uses the existing gold wordmark asset in the accessible home links', () => {
    renderPage();
    const brands = screen.getAllByRole('link', { name: 'EquiConnected home' });
    expect(brands).toHaveLength(2);

    for (const brand of brands) {
      expect(brand.getAttribute('href')).toBe('/');
      expect(brand.querySelector('img')?.getAttribute('src')).toBe('/equiconnected-logo.png');
    }
  });

  it('flows directly from Find equine care to Why EquiConnected without the removed explorer', () => {
    renderPage();

    const find = screen.getByRole('region', { name: 'Care that actually reaches your stable.' });
    const why = screen.getByRole('region', { name: 'Built around how equine care really works.' });
    expect(find.nextElementSibling).toBe(why);
    expect(document.getElementById('care-near-you')).toBeNull();
    expect(screen.queryByText('Care near you')).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Nearby providers' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Map of nearby equine care providers' })).toBeNull();
    expect(document.querySelector('[href*="care-near-you"]')).toBeNull();
  });

  it('presents eight provider-shared benefits alongside the undimmed horse photo', () => {
    renderPage();
    const why = screen.getByRole('region', { name: 'Built around how equine care really works.' });
    const benefits = within(why).getByRole('list', { name: 'What you can explore on EquiConnected' });
    const items = within(benefits).getAllByRole('listitem');
    expect(items).toHaveLength(8);
    for (const title of [
      'Shared locations', 'Provider details', 'Specialties', 'Stable visits',
      'Emergency services', 'Languages', 'Member reviews', 'Visiting care',
    ]) {
      expect(within(benefits).getByText(title)).toBeTruthy();
    }
    expect(within(benefits).getByText(/confirm availability directly/i)).toBeTruthy();
    expect(within(benefits).getByText(/Ask providers which languages they speak/i)).toBeTruthy();
    expect(within(benefits).getByText(/when they’re available/i)).toBeTruthy();
    expect(within(benefits).getByText(/Ask providers about travel and availability/i)).toBeTruthy();
    expect(within(why).getByRole('img', { name: /horse in a bright, close-up black-and-white portrait/i })).toBeTruthy();
    expect(within(why).getByText('Photo by Mahmoud Ayad on Unsplash')).toBeTruthy();
    expect(within(why).queryByText(/verified profiles|qualifications checked|emergency lines and hours|results reflect where your horse is stabled/i)).toBeNull();
  });

  it('presents Find Care as informational rather than a live radius search or fake filters', () => {
    renderPage();
    const find = within(screen.getByRole('region', { name: 'Care that actually reaches your stable.' }));

    expect(find.getByText('Find equine care')).toBeTruthy();
    expect(find.getByText(/Illustrative only/i)).toBeTruthy();
    expect(find.getByText(/Members only/i)).toBeTruthy();
    expect(find.getByText(/Street addresses are not shown publicly/i)).toBeTruthy();
    expect(find.getByText(/ask providers about their location and availability/i)).toBeTruthy();
    expect(find.getByText(/including whether a provider offers stable visits/i)).toBeTruthy();
    expect(find.getByRole('img', { name: /Illustrative stable and provider/i })).toBeTruthy();
    const details = within(find.getByRole('list', { name: 'Care topics to explore' }));

    const labels = ['Stable visit', 'Hospital / clinic visit', 'Specialization', 'Emirate', 'Availability', 'Language', 'Emergency services'];
    expect(details.getAllByRole('listitem').map(item => item.textContent)).toEqual(labels);
    expect(details.getAllByRole('listitem').every(item => item.querySelector('svg[aria-hidden="true"]'))).toBe(true);
    expect(details.queryByRole('link')).toBeNull();
    expect(details.queryByRole('button')).toBeNull();
    expect(find.queryByRole('button')).toBeNull();
    expect(find.queryByRole('textbox')).toBeNull();
    expect(find.queryByRole('combobox')).toBeNull();
    expect(find.queryByRole('checkbox')).toBeNull();
    expect(find.getByRole('link', { name: 'Check all providers' }).getAttribute('href')).toBe('/signup');
  });

  it('presents six honest owner steps, attributed imagery, and a guest signup action', () => {
    renderPage();
    const owners = within(screen.getByRole('region', { name: 'Your horses, known by heart — and on file.' }));
    expect(owners.getByText('For horse owners & riders')).toBeTruthy();
    expect(owners.getAllByRole('listitem')).toHaveLength(6);
    for (const text of [
      'Create your member profile', 'Add your horses', 'Include optional breed details',
      'Add registration and microchip numbers if you have them',
      'Browse provider-shared information', 'Save providers to revisit later',
    ]) expect(owners.getByText(text)).toBeTruthy();
    expect(owners.queryByText(/each horse’s stable location|search starts from|providers who reach that location/i)).toBeNull();
    expect(owners.getByRole('img', { name: /horse owner standing close beside a chestnut horse/i })).toBeTruthy();
    expect(owners.getByRole('img', { name: /close-up of a horse's eye/i })).toBeTruthy();
    expect(owners.getByLabelText('Illustrative horse profile, not a member record')).toBeTruthy();
    expect(owners.getByRole('link', { name: /Philippe Oursel/i }).getAttribute('href')).toBe('https://unsplash.com/@ourselp');
    expect(owners.getByRole('link', { name: /Glen Carrie/i }).getAttribute('href')).toBe('https://unsplash.com/@glencarrie');
    expect(owners.getByRole('link', { name: 'Create your account' }).getAttribute('href')).toBe('/signup');
  });

  it('routes owner members to horses and other members to their profile', () => {
    const memberUser = {
      id: 'member', email: 'member@example.com', first_name: 'Member', last_name: 'Rider',
      full_name: 'Member Rider', role: 'horse_owner', roles: ['horse_owner'],
      email_verified_at: '2026-08-31', last_successful_login_at: null, is_active: true,
    };
    vi.mocked(useAuth).mockReturnValue({ ...guestAuth(), isAuthenticated: true, user: memberUser });
    const view = renderPage();
    const owners = within(document.getElementById('owners')!);
    expect(owners.getByRole('link', { name: 'Your horses' }).getAttribute('href')).toBe('/profile?section=horses');

    vi.mocked(useAuth).mockReturnValue({
      ...guestAuth(), isAuthenticated: true,
      user: { ...memberUser, role: 'stable_manager', roles: ['stable_manager'] },
    });
    view.rerender(<MemoryRouter><PublicPage /></MemoryRouter>);
    expect(owners.getByRole('link', { name: 'View your profile' }).getAttribute('href')).toBe('/profile');
  });

  it('keeps the V2 care journey sections in their intended order', () => {
    renderPage();

    const intro = screen.getByRole('region', { name: /Every horse deserves care/i });
    expect(within(intro).getByRole('heading', { level: 2, name: /Every horse deserves care from someone who knows horses/i })).toBeTruthy();
    expect(within(intro).queryByText(/A starting point for horse owners, riders and stable teams/i)).toBeNull();
    expect(within(intro).queryByRole('link')).toBeNull();
    const steps = screen.getByRole('region', { name: 'Four quiet steps.' });
    expect(within(steps).getByText('How it works')).toBeTruthy();
    expect(within(steps).getAllByRole('listitem')).toHaveLength(4);
    expect(within(steps).queryByText(/Start with what your horse needs\. Explore the network at your own pace\./i)).toBeNull();
    expect(screen.queryByText(/A clearer first step/i)).toBeNull();
    expect(within(screen.getByRole('contentinfo')).getByRole('link', { name: 'How it works' }).getAttribute('href'))
      .toBe('/#how-it-works');
    const sectionIds = ['care', 'how-it-works', 'find', 'owners', 'providers', 'visiting', 'emergency'];
    const sections = sectionIds.map((id) => document.getElementById(id));
    expect(sections.every(Boolean)).toBe(true);

    for (let index = 1; index < sections.length; index += 1) {
      const relation = sections[index - 1]!.compareDocumentPosition(sections[index]!);
      expect(relation & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });
});
