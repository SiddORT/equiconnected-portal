import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DashboardPage } from './DashboardPage';
import { getDashboardStats, getDashboardVisits } from '@/api/admin';
import type { DashboardStats } from '@/types';

vi.mock('@/api/admin', () => ({ getDashboardStats: vi.fn(), getDashboardVisits: vi.fn() }));
vi.mock('@/app/AuthContext', () => ({ useAuth: () => ({ user: { full_name: 'Admin' } }) }));
vi.mock('@/components/dashboard/DashboardMap', () => ({ DashboardMap: () => <p>Provider map retained</p> }));
vi.mock('@/components/dashboard/InvitationStatusChart', () => ({ InvitationStatusChart: () => <p>Invitation chart retained</p> }));
vi.mock('@/components/dashboard/RegistrationRequestsCard', () => ({ RegistrationRequestsCard: () => <p>Registration chart retained</p> }));
vi.mock('@/components/dashboard/VisitorVisitsChart', () => ({ VisitorVisitsChart: () => <p>Visitor chart retained</p> }));

afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('keeps statistics, activity charts, and the map visible if the visit feed fails', async () => {
  const stats: DashboardStats = {
    total_users: 1, active_providers: 2,
    provider_counts: { hospitals: 1, clinics: 0, doctors: 1 },
    invitation_counts: { sent: 0, accepted: 0, rejected: 0 },
    registration_counts: { registrations: 0, verified: 0, unverified: 0, horse_owners: 0, stable_managers: 0 },
    visitor_visits: [], location_markers: [],
  };
  vi.mocked(getDashboardStats).mockResolvedValue(stats);
  vi.mocked(getDashboardVisits).mockRejectedValue(new Error('Offline'));
  render(<MemoryRouter><DashboardPage /></MemoryRouter>);
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.getByText('Active providers')).toBeTruthy();
  expect(screen.getByText('Invitation chart retained')).toBeTruthy();
  expect(screen.getByText('Visitor chart retained')).toBeTruthy();
  expect(screen.getByText('Provider map retained')).toBeTruthy();
});