import { act, cleanup, render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
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
    tileLayer: vi.fn(() => ({ addTo: vi.fn(), on: vi.fn(), off: vi.fn() })),
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
  it('identifies only the origin for standard OSM tiles while retaining attribution and zoom limits', () => {
    render(<DashboardMap markers={markers} />);

    expect(leaflet.tileLayer).toHaveBeenCalledWith(
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        maxZoom: 19,
        referrerPolicy: 'strict-origin',
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    );
    expect(leaflet.tileLayer.mock.results[0].value.addTo).toHaveBeenCalledWith(leaflet.mapInstance);
    expect(leaflet.map).toHaveBeenCalledWith(expect.any(HTMLElement), { scrollWheelZoom: false });
  });

  it('keeps the actual document policy at no-referrer for other resources', () => {
    const documentHtml = new DOMParser().parseFromString(readFileSync('index.html', 'utf8'), 'text/html');
    const policies = documentHtml.querySelectorAll('meta[name="referrer"]');
    expect(policies).toHaveLength(1);
    expect(policies[0].getAttribute('content')).toBe('no-referrer');
  });

  it('retains marker colors, escaped popups, primary labels, and padded bounds', () => {
    render(<DashboardMap markers={[
      { ...markers[0], provider_name: '<Hospital & "Care">', location_name: '<Campus>', address: '<Street>' },
      ...markers.slice(1),
    ]} />);

    expect(leaflet.circleMarker.mock.calls.map(([, options]) => options)).toEqual(
      ['#dc2626', '#2563eb', '#059669'].map((fillColor) => ({
        radius: 9, color: '#ffffff', weight: 2, fillColor, fillOpacity: 0.9,
      })),
    );
    expect(leaflet.circleMarker.mock.results[0].value.bindPopup).toHaveBeenCalledWith(
      '<strong>&lt;Hospital &amp; &quot;Care&quot;&gt;</strong><br/>' +
      'Hospital — &lt;Campus&gt;<br/>&lt;Street&gt;<br/><em>Primary location</em>',
    );
    expect(leaflet.circleMarker.mock.results[1].value.bindPopup).toHaveBeenCalledWith(
      '<strong>Downtown Clinic</strong><br/>Clinic<br/>2 Clinic Street',
    );
    expect(leaflet.latLngBounds.mock.results[0].value.extend.mock.calls).toEqual(
      markers.map((marker) => [[marker.latitude, marker.longitude]]),
    );
    expect(leaflet.mapInstance.fitBounds).toHaveBeenCalledWith(
      leaflet.latLngBounds.mock.results[0].value, { padding: [32, 32] },
    );
  });

  it('centers a single location at zoom 12 and removes the map on unmount', () => {
    const { unmount } = render(<DashboardMap markers={[markers[0]]} />);
    expect(leaflet.mapInstance.setView).toHaveBeenCalledWith([0, 0], 12);
    expect(leaflet.mapInstance.fitBounds).not.toHaveBeenCalled();
    unmount();
    expect(leaflet.mapInstance.remove).toHaveBeenCalledOnce();
  });

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
    expect(leaflet.mapInstance.setView).toHaveBeenLastCalledWith([0, 0], 12);
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

    expect(screen.getByText('No visible locations')).toBeTruthy();
    expect(screen.getByText('Select a provider type to show its locations on the map.')).toBeTruthy();
    expect(leaflet.circleMarker).toHaveBeenCalledTimes(6);
    expect(leaflet.mapInstance.fitBounds).toHaveBeenLastCalledWith(
      leaflet.latLngBounds.mock.results[leaflet.latLngBounds.mock.results.length - 1].value,
      { padding: [32, 32] },
    );
    await user.click(screen.getByRole('button', { name: 'Show Hospital locations' }));
    expect(screen.queryByText('No visible locations')).toBeNull();
    expect(leaflet.circleMarker).toHaveBeenCalledTimes(7);
    expect(leaflet.mapInstance.setView).toHaveBeenLastCalledWith([0, 0], 12);
  });

  it('keeps the original empty state when no locations have coordinates', () => {
    render(<DashboardMap markers={[{ ...markers[0], latitude: null, longitude: null } as unknown as LocationMarker]} />);

    expect(screen.getByRole('status').textContent).toContain('No mappable locations');
    expect(screen.queryByRole('group', { name: 'Filter provider locations by type' })).toBeNull();
    expect(leaflet.map).not.toHaveBeenCalled();
    expect(leaflet.tileLayer).not.toHaveBeenCalled();
  });

  it('announces tile errors without removing markers, filters, or attribution, then recovers after a successful cycle', () => {
    render(<DashboardMap markers={markers} />);
    const events = leaflet.tileLayer.mock.results[0].value.on.mock.calls[0][0];
    const status = screen.getByRole('status');
    expect(status.textContent).toBe('');
    expect(status.getAttribute('aria-live')).toBe('polite');
    expect(status.getAttribute('aria-atomic')).toBe('true');

    act(() => {
      events.loading();
      events.tileerror();
      events.load();
    });
    expect(status.textContent).toContain('The map background could not load');
    expect(status.textContent).toContain('markers and type filters are still available');
    expect(screen.getByRole('region', { name: 'Map of provider locations' })).toBeTruthy();
    expect(screen.getByRole('group', { name: 'Filter provider locations by type' })).toBeTruthy();
    expect(leaflet.circleMarker).toHaveBeenCalledTimes(3);
    expect(leaflet.mapInstance.remove).not.toHaveBeenCalled();
    expect(leaflet.tileLayer).toHaveBeenCalledOnce();
    expect(leaflet.tileLayer).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ attribution: expect.stringContaining('OpenStreetMap') }),
    );

    act(() => events.loading());
    expect(status.textContent).toContain('The map background could not load');
    act(() => events.load());
    expect(status.textContent).toBe('');
    act(() => events.tileerror());
    expect(status.textContent).toContain('The map background could not load');
  });

  it('cleans up tile listeners and ignores events from replaced or unmounted maps', async () => {
    const user = userEvent.setup();
    const { rerender, unmount } = render(<DashboardMap markers={markers} />);
    const oldLayer = leaflet.tileLayer.mock.results[0].value;
    const oldEvents = oldLayer.on.mock.calls[0][0];
    act(() => oldEvents.tileerror());

    await user.click(screen.getByRole('button', { name: 'Hide Hospital locations' }));
    expect(oldLayer.off).toHaveBeenCalledWith(oldEvents);
    act(() => oldEvents.tileerror());
    expect(screen.getByRole('status').textContent).toBe('');

    for (const type of ['Clinic', 'Doctor']) {
      await user.click(screen.getByRole('button', { name: `Hide ${type} locations` }));
    }
    const lastLayer = leaflet.tileLayer.mock.results[leaflet.tileLayer.mock.results.length - 1].value;
    const lastEvents = lastLayer.on.mock.calls[0][0];
    act(() => lastEvents.tileerror());
    expect(screen.getByText('No visible locations')).toBeTruthy();
    expect(screen.getByText(/The map background could not load/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Show Hospital locations' })).toBeTruthy();

    rerender(<DashboardMap markers={[]} />);
    expect(lastLayer.off).toHaveBeenCalledWith(lastEvents);
    act(() => lastEvents.tileerror());
    expect(screen.getByText('No mappable locations')).toBeTruthy();
    expect(screen.queryByText(/The map background could not load/)).toBeNull();
    unmount();
  });
});