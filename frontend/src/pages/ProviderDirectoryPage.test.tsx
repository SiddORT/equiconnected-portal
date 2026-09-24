import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { ProviderDirectoryPage } from './ProviderDirectoryPage';

vi.mock('@/api/providers', () => ({ listMemberProviders: vi.fn() }));
vi.mock('@/components/ui/LoadingSpinner', () => ({ LoadingSpinner: () => <span>loading</span> }));

const item = {
  id: 'p-1', provider_type: 'CLINIC' as const, name: 'Austin Equine Clinic',
  description: 'Trusted care', thumbnail_url: '/clinic.jpg', thumbnail_alt_text: 'Clinic exterior',
  website: null, email: null, phone: null, visit_stability: 'STABLE_VISIT' as const,
  location: { city: 'Austin', state_province: 'Texas', country: 'United States' },
  average_rating: 4.5, review_count: 3, distance_km: 4.2,
};
const response = { data: [item], meta: { page: 1, page_size: 12, total: 1, total_pages: 1 } };

beforeEach(() => vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response));
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks(); });

function renderPage(path = '/providers') {
  return render(<MemoryRouter initialEntries={[path]}><ProviderDirectoryPage /></MemoryRouter>);
}

function DetailBackLink() {
  const location = useLocation();
  return <Link to={`/providers${location.search}`} state={location.state}>Back to providers</Link>;
}

describe('member provider directory', () => {
  it('combines type and rating filters in the request and preserves them on detail links', async () => {
    const user = userEvent.setup();
    renderPage('/providers?provider_type=CLINIC&minimum_rating=4');
    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenCalledWith(expect.objectContaining({
      provider_type: 'CLINIC', minimum_rating: 4,
    })));
    expect((await screen.findByRole('link', { name: /view profile/i })).getAttribute('href'))
      .toContain('provider_type=CLINIC&minimum_rating=4');
    await user.selectOptions(screen.getByLabelText('Minimum rating'), '5');
    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenLastCalledWith(expect.objectContaining({ minimum_rating: 5 })));
  });

  it('only requests browser location after an explicit click and leaves radius off on denial', async () => {
    const user = userEvent.setup();
    const getCurrentPosition = vi.fn((_success: PositionCallback, failure: PositionErrorCallback) => failure({ code: 1, message: 'denied' } as GeolocationPositionError));
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } });
    renderPage();
    expect(getCurrentPosition).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: /within working radius/i }));
    expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/could not access your location/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /within working radius/i })).toBeTruthy();
    const calls = vi.mocked(providersApi.listMemberProviders).mock.calls;
    expect(calls[calls.length - 1]?.[0]).not.toEqual(expect.objectContaining({ within_working_radius: true }));
  });

  it('enables and disables radius independently after location succeeds', async () => {
    const user = userEvent.setup();
    let success!: PositionCallback;
    const getCurrentPosition = vi.fn((next: PositionCallback) => { success = next; });
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } });
    renderPage();
    await user.click(screen.getByRole('button', { name: /within working radius/i }));
    success({ coords: { latitude: 30, longitude: -97, accuracy: 1, altitude: null, altitudeAccuracy: null, heading: null, speed: null, toJSON: () => ({}) }, timestamp: Date.now(), toJSON: () => ({}) } as GeolocationPosition);
    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenLastCalledWith(expect.objectContaining({ within_working_radius: true, latitude: 30, longitude: -97 })));
    expect(vi.mocked(providersApi.listMemberProviders).mock.calls[vi.mocked(providersApi.listMemberProviders).mock.calls.length - 1]?.[0]).not.toEqual(expect.objectContaining({ closest_first: true }));
    await user.click(screen.getByRole('button', { name: /within working radius/i }));
    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenLastCalledWith(expect.not.objectContaining({ within_working_radius: true })));
  });

  it('renders a responsive grid and branded image fallback', async () => {
    renderPage();
    expect(await screen.findByRole('region', { name: 'Provider results' })).toBeTruthy();
    const image = screen.getByRole('img', { name: 'Clinic exterior' });
    fireEvent.error(image);
    expect(screen.getByRole('img', { name: 'No photo available for Austin Equine Clinic' })).toBeTruthy();
    expect(screen.queryByRole('region', { name: /slider/i })).toBeNull();
  });

  it('clears a radius flag on refresh without making an unfiltered request', async () => {
    renderPage('/providers?within_working_radius=true');
    await waitFor(() => expect(screen.getByText(/not available after refresh/i)).toBeTruthy());
    expect(vi.mocked(providersApi.listMemberProviders).mock.calls.every(([params]) => params?.within_working_radius !== true)).toBe(true);
    expect(screen.getByRole('button', { name: /within working radius/i })).toBeTruthy();
  });

  it('reports filtered counts and composed empty and error states', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValueOnce({ data: [], meta: { page: 1, page_size: 12, total: 0, total_pages: 0 } });
    renderPage('/providers?provider_type=DOCTOR');
    expect(await screen.findByRole('heading', { name: /no providers match/i })).toBeTruthy();
    cleanup();
    vi.mocked(providersApi.listMemberProviders).mockRejectedValueOnce(new Error('offline'));
    renderPage();
    expect(await screen.findByText(/providers could not be loaded/i)).toBeTruthy();
    expect(screen.queryByRole('heading', { name: /no providers match/i })).toBeNull();
  });

  it('keeps pagination, filtered counts and location context when returning from details', async () => {
    const user = userEvent.setup();
    let success!: PositionCallback;
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: (next: PositionCallback) => { success = next; } },
    });
    vi.mocked(providersApi.listMemberProviders).mockImplementation(async (params) => ({
      data: [{ ...item, id: `p-${params?.page ?? 1}` }],
      meta: { page: params?.page ?? 1, page_size: params?.page_size ?? 10, total: 18, total_pages: 2 },
    }));
    render(<MemoryRouter initialEntries={['/providers?provider_type=CLINIC&minimum_rating=4']}>
      <Routes>
        <Route path="/providers" element={<ProviderDirectoryPage />} />
        <Route path="/providers/:id" element={<DetailBackLink />} />
      </Routes>
    </MemoryRouter>);
    await screen.findByText('18', { selector: 'strong' });
    await user.click(screen.getByRole('button', { name: /within working radius/i }));
    success({ coords: { latitude: 30, longitude: -97 } } as GeolocationPosition);
    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenLastCalledWith(expect.objectContaining({
      provider_type: 'CLINIC', minimum_rating: 4, within_working_radius: true, latitude: 30, longitude: -97,
    })));
    await user.click(screen.getByRole('button', { name: /next/i }));
    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, within_working_radius: true })));
    await user.click(screen.getByRole('link', { name: /view profile/i }));
    await user.click(screen.getByRole('link', { name: /back to providers/i }));
    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenLastCalledWith(expect.objectContaining({
      page: 2, provider_type: 'CLINIC', minimum_rating: 4, within_working_radius: true, latitude: 30, longitude: -97,
    })));
    expect(screen.getByText(/showing 11 to 18 of 18 entries/i)).toBeTruthy();
  });
});