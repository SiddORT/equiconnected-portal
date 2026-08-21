import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LocationMarker } from '@/types';

const leaflet = vi.hoisted(() => {
  const mapInstance = {
    remove: vi.fn(),
    setView: vi.fn(),
    fitBounds: vi.fn(),
  };
  const createMarker = vi.fn((coordinates: unknown, options: unknown) => {
    void coordinates;
    void options;
    const marker = {
      addTo: vi.fn(),
      bindPopup: vi.fn(),
    };
    marker.addTo.mockReturnValue(marker);
    return marker;
  });

  return {
    mapInstance,
    map: vi.fn(() => mapInstance),
    tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
    latLngBounds: vi.fn(() => ({
      extend: vi.fn(),
      getCenter: vi.fn(() => [0, 0]),
    })),
    circleMarker: createMarker,
  };
});

vi.mock('leaflet', () => ({ default: leaflet }));

import { DashboardMap } from './DashboardMap';

const markers: LocationMarker[] = [
  {
    location_id: 'hospital-location',
    provider_id: 'hospital',
    provider_name: 'General Hospital',
    provider_type: 'HOSPITAL',
    location_name: 'Main campus',
    address: '1 Hospital Way',
    city: 'Austin',
    latitude: 30.2672,
    longitude: -97.7431,
    is_primary: true,
  },
  {
    location_id: 'clinic-location',
    provider_id: 'clinic',
    provider_name: 'Downtown Clinic',
    provider_type: 'CLINIC',
    location_name: null,
    address: '2 Clinic Street',
    city: 'Austin',
    latitude: 30.268,
    longitude: -97.742,
    is_primary: false,
  },
  {
    location_id: 'doctor-location',
    provider_id: 'doctor',
    provider_name: 'Dr. Green',
    provider_type: 'DOCTOR',
    location_name: 'Office',
    address: '3 Doctor Avenue',
    city: 'Austin',
    latitude: 30.269,
    longitude: -97.741,
    is_primary: true,
  },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('DashboardMap', () => {
  it('shows all provider types and markers by default', () => {
    render(<DashboardMap markers={markers} />);

    expect(screen.getByRole('button', { name: 'Hide Hospital locations' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Hide Clinic locations' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Hide Doctor locations' }).getAttribute('aria-pressed')).toBe('true');
    expect(leaflet.circleMarker).toHaveBeenCalledTimes(3);
  });

  it('immediately shows only the selected provider types and refits the map', async () => {
    const user = userEvent.setup();
    render(<DashboardMap markers={markers} />);

    await user.click(screen.getByRole('button', { name: 'Hide Hospital locations' }));
    expect(leaflet.circleMarker).toHaveBeenCalledTimes(5);
    expect(screen.getByRole('button', { name: 'Show Hospital locations' }).getAttribute('aria-pressed')).toBe('false');
    expect(leaflet.circleMarker.mock.calls.slice(-2).map(([coordinates]) => coordinates)).toEqual([
      [markers[1].latitude, markers[1].longitude],
      [markers[2].latitude, markers[2].longitude],
    ]);
    expect(leaflet.mapInstance.fitBounds).toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Hide Clinic locations' }));
    expect(leaflet.circleMarker).toHaveBeenCalledTimes(6);
    expect(screen.getByRole('button', { name: 'Hide Doctor locations' }).getAttribute('aria-pressed')).toBe('true');
    expect(leaflet.circleMarker.mock.calls[leaflet.circleMarker.mock.calls.length - 1][0]).toEqual([
      markers[2].latitude,
      markers[2].longitude,
    ]);
  });

  it('shows an in-map empty state when all selected types are hidden', async () => {
    const user = userEvent.setup();
    render(<DashboardMap markers={markers} />);

    for (const type of ['Hospital', 'Clinic', 'Doctor']) {
      await user.click(screen.getByRole('button', { name: `Hide ${type} locations` }));
    }

    expect(screen.getByRole('status').textContent).toContain('No visible locations');
    expect(screen.getByText('Select a provider type to show its locations on the map.')).toBeTruthy();
    expect(leaflet.circleMarker).toHaveBeenCalledTimes(6);
  });

  it('keeps the original empty state when no locations have coordinates', () => {
    render(<DashboardMap markers={[{ ...markers[0], latitude: null, longitude: null } as unknown as LocationMarker]} />);

    expect(screen.getByRole('status').textContent).toContain('No mappable locations');
    expect(screen.queryByRole('group', { name: 'Filter provider locations by type' })).toBeNull();
  });
});