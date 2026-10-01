import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { getDashboardVisits } from '@/api/admin';
import { getMemberVisitCalendar } from '@/api/providers';
import type { DashboardVisitMonth } from '@/types';
import {
  AdminVisitingProviderCalendarPage,
  MemberVisitingProviderCalendarPage,
} from './VisitingProviderCalendarPage';

vi.mock('@/api/admin', () => ({ getDashboardVisits: vi.fn() }));
vi.mock('@/api/providers', () => ({ getMemberVisitCalendar: vi.fn() }));

const feed: DashboardVisitMonth = {
  month: '2026-09',
  today: '2026-09-24',
  visits: [{
    id: 'visit', provider_id: 'provider-7', provider_name: 'Dr. Rowan',
    start_date: '2026-09-24', end_date: '2026-09-24', specializations: ['Dentistry'],
    location: { city: 'Kelowna', state_province: 'BC', country: 'Canada' },
  }],
};

function LocationView() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="location">{location.pathname}{location.search}|{JSON.stringify(location.state)}</output>
      <button type="button" onClick={() => navigate(-1)}>Go back</button>
    </>
  );
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it('loads admin visits and returns to dashboard with the current search and navigation state', async () => {
  vi.mocked(getDashboardVisits).mockResolvedValue(feed);
  const state = { openedFrom: 'audit', page: 3 };
  render(
    <MemoryRouter initialEntries={[{ pathname: '/admin/calendar', search: '?focus=provider', state }]}>
      <Routes>
        <Route path="/admin/calendar" element={<AdminVisitingProviderCalendarPage />} />
        <Route path="/admin/providers/:id" element={<LocationView />} />
        <Route path="/admin/dashboard" element={<LocationView />} />
      </Routes>
    </MemoryRouter>,
  );
  const agenda = await screen.findByRole('complementary');
  const profile = await within(agenda).findByRole('link', { name: /Dr. Rowan/ });
  expect(profile.getAttribute('href')).toBe('/admin/providers/provider-7');
  await userEvent.setup().click(profile);
  expect(screen.getByTestId('location').textContent).toContain('/admin/providers/provider-7|{"openedFrom":"audit","page":3}');
  await userEvent.setup().click(screen.getByRole('button', { name: 'Go back' }));
  await userEvent.setup().click(screen.getByRole('link', { name: /Dashboard/ }));
  expect(screen.getByTestId('location').textContent).toBe('/admin/dashboard?focus=provider|{"openedFrom":"audit","page":3}');
  expect(getDashboardVisits).toHaveBeenCalledWith(undefined);
});

it('keeps member directory query and state on profile links and the return path', async () => {
  vi.mocked(getMemberVisitCalendar).mockResolvedValue(feed);
  const state = { directoryCoordinates: { lat: 49.88, lng: -119.49 }, restored: true };
  render(
    <MemoryRouter initialEntries={[{ pathname: '/visiting-calendar', search: '?specialty=equine&region=west', state }]}>
      <Routes>
        <Route path="/visiting-calendar" element={<MemberVisitingProviderCalendarPage />} />
        <Route path="/providers/:id" element={<LocationView />} />
        <Route path="/providers" element={<LocationView />} />
      </Routes>
    </MemoryRouter>,
  );
  const agenda = await screen.findByRole('complementary');
  const profile = await within(agenda).findByRole('link', { name: /Dr. Rowan/ });
  expect(profile.getAttribute('href')).toBe('/providers/provider-7?specialty=equine&region=west');
  await userEvent.setup().click(profile);
  expect(screen.getByTestId('location').textContent).toBe(
    '/providers/provider-7?specialty=equine&region=west|{"directoryCoordinates":{"lat":49.88,"lng":-119.49},"restored":true}',
  );
  await userEvent.setup().click(screen.getByRole('button', { name: 'Go back' }));
  await userEvent.setup().click(screen.getByRole('link', { name: /Provider directory/ }));
  expect(screen.getByTestId('location').textContent).toBe(
    '/providers?specialty=equine&region=west|{"directoryCoordinates":{"lat":49.88,"lng":-119.49},"restored":true}',
  );
  expect(getMemberVisitCalendar).toHaveBeenCalledWith(undefined);
});