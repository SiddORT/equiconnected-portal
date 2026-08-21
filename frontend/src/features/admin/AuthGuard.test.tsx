import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { LoginPage } from '@/pages/admin/LoginPage';
import { AuthGuard } from './AuthGuard';

vi.mock('@/app/AuthContext', () => ({
  useAuth: vi.fn(),
}));

const memberAuth = {
  isAuthenticated: true,
  isLoading: false,
  user: {
    id: 'member-1',
    email: 'member@example.com',
    first_name: 'Amina',
    last_name: 'Rider',
    full_name: 'Amina Rider',
    role: 'horse_owner',
    roles: ['horse_owner'],
    email_verified_at: '2026-08-21T00:00:00Z',
    last_successful_login_at: '2026-08-21T00:00:00Z',
    is_active: true,
  },
  login: vi.fn(),
  logout: vi.fn(),
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('admin access redirects', () => {
  it('sends authenticated members away from the admin dashboard instead of the admin login loop', async () => {
    vi.mocked(useAuth).mockReturnValue(memberAuth);

    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <Routes>
          <Route element={<AuthGuard requiredRole="admin" />}>
            <Route path="/admin/dashboard" element={<p>Admin dashboard</p>} />
          </Route>
          <Route path="/providers" element={<p>Member provider directory</p>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('Member provider directory')).toBeTruthy();
    expect(screen.queryByText('Admin dashboard')).toBeNull();
  });

  it('sends authenticated members away from the admin login page instead of the dashboard loop', async () => {
    vi.mocked(useAuth).mockReturnValue(memberAuth);

    render(
      <MemoryRouter initialEntries={['/admin/login']}>
        <Routes>
          <Route path="/admin/login" element={<LoginPage />} />
          <Route path="/providers" element={<p>Member provider directory</p>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('Member provider directory')).toBeTruthy();
  });
});