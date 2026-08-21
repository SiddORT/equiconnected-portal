import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as profileApi from '@/api/profile';
import * as providersApi from '@/api/providers';
import { ProviderDirectoryPage } from './ProviderDirectoryPage';
import type { MemberProfile } from '@/types';

vi.mock('@/api/providers', () => ({
  listMemberProviders: vi.fn(),
}));

vi.mock('@/api/profile', () => ({
  getProfile: vi.fn(),
}));

vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'member-1',
      email: 'amina@example.com',
      first_name: 'Amina',
      last_name: 'Rider',
      full_name: 'Amina Rider',
      role: 'horse_owner',
      roles: ['horse_owner'],
      email_verified_at: '2026-08-21T00:00:00Z',
      last_successful_login_at: '2026-08-21T15:30:00Z',
      is_active: true,
    },
  }),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => `System time: ${value}`,
  }),
}));

const response = {
  data: [{
    id: 'provider-1',
    provider_type: 'CLINIC' as const,
    name: 'Austin Equine Clinic',
    description: 'Trusted care',
    thumbnail_url: '/uploads/providers/austin-clinic.jpg',
    thumbnail_alt_text: 'Austin Equine Clinic care team outside the clinic',
    website: null,
    email: null,
    phone: null,
    visit_stability: 'STABLE_VISIT' as const,
    location: { city: 'Austin', state_province: 'Texas', country: 'United States' },
    average_rating: 4.5,
    review_count: 3,
    distance_km: null,
  }],
  meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
};

const incompleteProfile: MemberProfile = {
  first_name: 'Amina',
  last_name: 'Rider',
  email: 'amina@example.com',
  mobile_number: '+1 555 123 4567',
  address: null,
  country: 'United States',
  state_province: 'Texas',
  city: 'Austin',
  postal_code: null,
  roles: ['horse_owner'],
  stable_profile: null,
  horses: [],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

const originalGeolocation = Object.getOwnPropertyDescriptor(navigator, 'geolocation');

beforeEach(() => {
  vi.mocked(profileApi.getProfile).mockResolvedValue(incompleteProfile);
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  if (originalGeolocation) Object.defineProperty(navigator, 'geolocation', originalGeolocation);
});

describe('ProviderDirectoryPage', () => {
  it('welcomes the signed-in member and shows the last successful sign-in', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response);
    vi.mocked(profileApi.getProfile).mockResolvedValue(incompleteProfile);

    render(
      <MemoryRouter initialEntries={['/providers']}>
        <ProviderDirectoryPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: 'Welcome back, Amina.' })).toBeTruthy();
    expect(screen.getByTestId('member-dashboard-hero')).toBeTruthy();
    expect(screen.getByRole('link', { name: /view your profile/i }).getAttribute('href')).toBe('/profile');
    expect(screen.getByText(/Last successful sign-in:/)).toBeTruthy();
    expect(screen.getByText('System time: 2026-08-21T15:30:00Z')).toBeTruthy();
    expect(document.querySelector('time')?.getAttribute('dateTime')).toBe('2026-08-21T15:30:00Z');
    expect(screen.getByTestId('member-dashboard-hero').querySelector('img[src="/horse-panel.jpg"]')?.getAttribute('alt')).toBe('');
    expect(screen.getByTestId('member-dashboard-hero').querySelector('img[src="/stable-panel.jpg"]')?.getAttribute('alt')).toBe('');
    expect(await screen.findByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();
    expect(screen.getByRole('img', { name: 'Austin Equine Clinic care team outside the clinic' }).getAttribute('src'))
      .toBe('/uploads/providers/austin-clinic.jpg');
    expect((screen.getByRole('button', { name: 'Previous providers' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Next providers' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('loads URL-backed filters and keeps providers available when location access is unavailable', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response);
    vi.mocked(profileApi.getProfile).mockResolvedValue(incompleteProfile);
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/providers?provider_type=CLINIC&minimum_rating=4']}>
        <ProviderDirectoryPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenCalledWith(
      expect.objectContaining({ provider_type: 'CLINIC', minimum_rating: 4 })
    ));
    expect(await screen.findByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Sort closest first' }));
    expect(await screen.findByText(/browser does not support location access/i)).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'View Austin Equine Clinic' }).getAttribute('href'))
      .toBe('/providers/provider-1?provider_type=CLINIC&minimum_rating=4');
  });

  it('supports slider controls and keyboard scrolling for the current page', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue({
      data: [
        response.data[0],
        {
          ...response.data[0],
          id: 'provider-2',
          name: 'Bluebonnet Equine Hospital',
          thumbnail_url: null,
          thumbnail_alt_text: null,
        },
        {
          ...response.data[0],
          id: 'provider-3',
          name: 'Prairie Veterinary Care',
          thumbnail_url: '/uploads/providers/prairie.jpg',
          thumbnail_alt_text: null,
        },
      ],
      meta: { page: 1, page_size: 20, total: 3, total_pages: 1 },
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/providers']}>
        <ProviderDirectoryPage />
      </MemoryRouter>
    );

    await screen.findByRole('heading', { name: 'Bluebonnet Equine Hospital' });
    const slider = screen.getByRole('region', { name: 'Provider results slider' });
    let scrollLeft = 0;
    const scrollBy = vi.fn(({ left }: ScrollToOptions) => {
      scrollLeft = Math.max(0, Math.min(600, scrollLeft + (left ?? 0)));
      fireEvent.scroll(slider);
    });
    Object.defineProperties(slider, {
      clientWidth: { configurable: true, value: 300 },
      scrollWidth: { configurable: true, value: 900 },
      scrollLeft: { configurable: true, get: () => scrollLeft },
      scrollBy: { configurable: true, value: scrollBy },
    });
    fireEvent.scroll(slider);

    const next = screen.getByRole('button', { name: 'Next providers' });
    expect((next as HTMLButtonElement).disabled).toBe(false);
    await user.click(next);
    expect(scrollBy).toHaveBeenCalledWith({ left: 280 });

    slider.focus();
    await user.keyboard('{ArrowRight}');
    expect(scrollBy).toHaveBeenLastCalledWith({ left: 280 });
    await user.click(next);
    expect((next as HTMLButtonElement).disabled).toBe(true);

    const previous = screen.getByRole('button', { name: 'Previous providers' });
    expect((previous as HTMLButtonElement).disabled).toBe(false);
    await user.click(previous);
    expect(scrollBy).toHaveBeenLastCalledWith({ left: -280 });
    const fallback = screen.getByRole('img', { name: 'No photo available for Bluebonnet Equine Hospital' });
    expect(fallback).toBeTruthy();
    expect(fallback.querySelector('img[src="/logo.png"]')).toBeTruthy();
    expect(screen.getByRole('img', { name: 'Prairie Veterinary Care provider' })).toBeTruthy();
  });

  it('replaces a failed provider image with the branded fallback', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response);

    render(
      <MemoryRouter initialEntries={['/providers']}>
        <ProviderDirectoryPage />
      </MemoryRouter>
    );

    const image = await screen.findByRole('img', { name: 'Austin Equine Clinic care team outside the clinic' });
    fireEvent.error(image);

    const fallback = screen.getByRole('img', { name: 'No photo available for Austin Equine Clinic' });
    expect(fallback.querySelector('img[src="/logo.png"]')).toBeTruthy();
  });

  it('tries a refreshed thumbnail after an earlier image failed', async () => {
    vi.mocked(providersApi.listMemberProviders)
      .mockResolvedValueOnce(response)
      .mockResolvedValueOnce({
        ...response,
        data: [{ ...response.data[0], thumbnail_url: '/uploads/providers/austin-clinic-updated.jpg' }],
      });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/providers']}>
        <ProviderDirectoryPage />
      </MemoryRouter>
    );

    fireEvent.error(await screen.findByRole('img', { name: 'Austin Equine Clinic care team outside the clinic' }));
    expect(screen.getByRole('img', { name: 'No photo available for Austin Equine Clinic' })).toBeTruthy();

    await user.selectOptions(screen.getByLabelText('Provider type'), 'CLINIC');
    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenCalledTimes(2));
    expect((await screen.findByRole('img', { name: 'Austin Equine Clinic care team outside the clinic' }) as HTMLImageElement).src)
      .toContain('/uploads/providers/austin-clinic-updated.jpg');
  });

  it('guides incomplete profiles to their next incomplete section without delaying providers', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response);
    vi.mocked(profileApi.getProfile).mockResolvedValue(incompleteProfile);

    render(<MemoryRouter initialEntries={['/providers']}><ProviderDirectoryPage /></MemoryRouter>);

    expect((await screen.findByTestId('profile-progress-card')).textContent).toContain('Finish your profile');
    const continueLink = screen.getByRole('link', { name: /continue in account and contact/i });
    expect(continueLink.getAttribute('href')).toBe('/profile?section=personal');
    expect(await screen.findByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();
  });

  it('shows a ready state instead of a completion prompt for complete profiles', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response);
    vi.mocked(profileApi.getProfile).mockResolvedValue({
      ...incompleteProfile,
      address: '12 Oak Lane',
      postal_code: '78701',
      horses: [{
        id: 'horse-1',
        name: 'Juniper',
        sex: 'MARE',
        registered_name: null,
        breed: null,
        date_of_birth: null,
        color: null,
        primary_discipline: null,
        registration_number: null,
        microchip_number: null,
        description: null,
        photo_reference: null,
        updated_at: '',
      }],
    });

    render(<MemoryRouter initialEntries={['/providers']}><ProviderDirectoryPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Your profile is ready' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /continue in/i })).toBeNull();
  });

  it('keeps provider discovery available while profile progress is still loading', async () => {
    const profileRequest = deferred<MemberProfile>();
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response);
    vi.mocked(profileApi.getProfile).mockReturnValue(profileRequest.promise);

    render(<MemoryRouter initialEntries={['/providers']}><ProviderDirectoryPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();
    expect(screen.getByText('Checking profile readiness…')).toBeTruthy();
    expect(screen.queryByTestId('profile-progress-card')).toBeNull();
    profileRequest.resolve(incompleteProfile);
  });

  it('keeps provider discovery available when profile progress cannot load', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response);
    vi.mocked(profileApi.getProfile).mockRejectedValue(new Error('Profile unavailable'));

    render(<MemoryRouter initialEntries={['/providers']}><ProviderDirectoryPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();
    await waitFor(() => expect(screen.queryByText('Checking profile readiness…')).toBeNull());
    expect(screen.queryByTestId('profile-progress-card')).toBeNull();
  });
});
