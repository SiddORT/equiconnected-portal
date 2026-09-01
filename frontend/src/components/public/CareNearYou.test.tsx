import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { PublicProviderDiscovery } from '@/types';
import * as publicApi from '@/api/public';
import { useAuth } from '@/app/AuthContext';
import styles from './CareNearYou.module.css';

const leaflet = vi.hoisted(() => {
  const mapInstance = {
    remove: vi.fn(),
    setView: vi.fn(),
    fitBounds: vi.fn(),
    invalidateSize: vi.fn(),
    getZoom: vi.fn(() => 8),
  };
  const layer = {
    addTo: vi.fn(),
    clearLayers: vi.fn(),
  };
  layer.addTo.mockReturnValue(layer);
  const marker = {
    bindTooltip: vi.fn(),
    bindPopup: vi.fn(),
    on: vi.fn(),
    addTo: vi.fn(),
  };
  marker.bindTooltip.mockReturnValue(marker);
  marker.bindPopup.mockReturnValue(marker);
  marker.on.mockReturnValue(marker);
  marker.addTo.mockReturnValue(marker);

  return {
    mapInstance,
    map: vi.fn(() => mapInstance),
    tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
    layerGroup: vi.fn(() => layer),
    circleMarker: vi.fn(() => marker),
    latLngBounds: vi.fn(() => ({ extend: vi.fn() })),
  };
});

vi.mock('leaflet', () => ({ default: leaflet }));
vi.mock('@/api/public', () => ({
  listPublicProviders: vi.fn(),
}));
vi.mock('@/app/AuthContext', () => ({
  useAuth: vi.fn(),
}));

import { CareNearYou } from './CareNearYou';

const providers: PublicProviderDiscovery[] = [
  {
    id: 'doctor-1',
    provider_type: 'DOCTOR',
    name: 'Dr. Mira Rao',
    specializations: ['Sports Medicine'],
    location: {
      city: 'Pune',
      state_province: 'Maharashtra',
      country: 'India',
      latitude: 18.5204,
      longitude: 73.8567,
    },
    thumbnail_url: null,
    average_rating: 4.9,
    review_count: 24,
    distance_km: null,
  },
  {
    id: 'clinic-1',
    provider_type: 'CLINIC',
    name: 'Blue Meadow Clinic',
    specializations: ['Diagnostics'],
    location: {
      city: 'Mumbai',
      state_province: 'Maharashtra',
      country: 'India',
      latitude: 19.076,
      longitude: 72.8777,
    },
    thumbnail_url: null,
    average_rating: 4.7,
    review_count: 12,
    distance_km: null,
  },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

const memberUser = {
  id: 'member-id',
  email: 'member@example.com',
  first_name: 'Member',
  last_name: 'User',
  full_name: 'Member User',
  role: 'horse_owner',
  roles: ['horse_owner'],
  email_verified_at: '2026-08-31T00:00:00Z',
  last_successful_login_at: null,
  is_active: true,
};

describe('CareNearYou', () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
    });
  });

  it('shows live provider cards, filters, selection, and member navigation', async () => {
    const user = userEvent.setup();
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: memberUser,
      login: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(publicApi.listPublicProviders).mockResolvedValue(providers);
    render(<MemoryRouter><CareNearYou /></MemoryRouter>);

    expect(screen.getByRole('status').textContent).toContain('Loading connected providers');
    expect(await screen.findByRole('button', { name: /Dr. Mira Rao/ })).toBeTruthy();
    expect(screen.getByText('Sports Medicine')).toBeTruthy();
    expect(screen.getByRole('link', { name: /FIND CARE NEAR ME/ }).getAttribute('href')).toBe('/member');
    expect(screen.getByRole('button', { name: /Dr. Mira Rao/ }).getAttribute('aria-pressed')).toBe('true');

    await user.click(screen.getByRole('button', { name: 'Clinics' }));

    expect(screen.queryByRole('button', { name: /Dr. Mira Rao/ })).toBeNull();
    expect(screen.getByRole('button', { name: /Blue Meadow Clinic/ }).getAttribute('aria-pressed')).toBe('true');
    expect(leaflet.circleMarker).toHaveBeenLastCalledWith(
      [19.076, 72.8777],
      expect.objectContaining({ fillColor: '#2d68a0' }),
    );
  });

  it('keeps provider details behind member access while leaving the public map usable', async () => {
    vi.mocked(publicApi.listPublicProviders).mockResolvedValue(providers);
    render(<MemoryRouter><CareNearYou /></MemoryRouter>);

    expect(await screen.findByText('Please log in or register as a member to see more details.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Dr. Mira Rao/ })).toBeNull();
    expect(screen.queryByText('Sports Medicine')).toBeNull();
    expect(screen.getByRole('region', { name: 'Map of nearby equine care providers' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Log in as a member' }).getAttribute('href')).toBe('/login');
    expect(screen.getByRole('link', { name: 'Register as a member' }).getAttribute('href')).toBe('/signup');
    expect(screen.getByRole('link', { name: /Explore the full provider directory/ }).getAttribute('href')).toBe('/login');
  });

  it('does not expose provider details while session restoration is in progress', async () => {
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(publicApi.listPublicProviders).mockResolvedValue(providers);
    render(<MemoryRouter><CareNearYou /></MemoryRouter>);

    expect(await screen.findByText('Checking member access…')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Dr. Mira Rao/ })).toBeNull();
    expect(screen.queryByText('Sports Medicine')).toBeNull();
    expect(screen.getByRole('link', { name: /Explore the full provider directory/ }).getAttribute('href')).toBe('/login');
  });

  it('keeps the care discovery action full width without changing its destination', () => {
    vi.mocked(publicApi.listPublicProviders).mockResolvedValue([]);
    render(<MemoryRouter><CareNearYou /></MemoryRouter>);

    const actions = document.querySelector(`.${styles.introActions}`) as HTMLElement;
    const findCareLink = screen.getByRole('link', { name: /FIND CARE NEAR ME/ });

    expect(actions).toBeTruthy();
    expect(findCareLink.getAttribute('href')).toBe('/member');
    expect(findCareLink.classList.contains(styles.primaryCta)).toBe(true);
  });

  it('requests location only after consent and refreshes provider distances', async () => {
    const user = userEvent.setup();
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: memberUser,
      login: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(publicApi.listPublicProviders)
      .mockResolvedValueOnce(providers)
      .mockResolvedValueOnce([{ ...providers[0], distance_km: 3.2 }]);
    const getCurrentPosition = vi.fn((success) => success({
      coords: { latitude: 18.52, longitude: 73.85 },
    }));
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition } });
    render(<MemoryRouter><CareNearYou /></MemoryRouter>);
    await screen.findByRole('button', { name: /Dr. Mira Rao/ });

    await user.click(screen.getByRole('button', { name: /Use my location/ }));

    expect(getCurrentPosition).toHaveBeenCalledOnce();
    await waitFor(() => expect(publicApi.listPublicProviders).toHaveBeenLastCalledWith({
      latitude: 18.52,
      longitude: 73.85,
    }));
    expect(await screen.findByText('3 km away')).toBeTruthy();
  });

  it('keeps a useful recovery path when public discovery fails', async () => {
    vi.mocked(publicApi.listPublicProviders).mockRejectedValue(new Error('offline'));
    render(<MemoryRouter><CareNearYou /></MemoryRouter>);

    expect((await screen.findByRole('alert')).textContent).toContain("We couldn't load the care map.");
    expect(screen.getByRole('link', { name: /Explore the full provider directory/ }).getAttribute('href')).toBe('/login');
  });
});