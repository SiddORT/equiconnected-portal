import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { MemberAuthGuard } from './MemberAuthGuard';

vi.mock('@/app/AuthContext', () => ({
  useAuth: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderGuard(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route element={<MemberAuthGuard />}>
          <Route path="/providers" element={<p>Provider directory</p>} />
          <Route path="/profile" element={<p>Member profile</p>} />
        </Route>
        <Route path="/login" element={<p>Member login</p>} />
        <Route path="/admin/login" element={<p>Admin login</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('MemberAuthGuard', () => {
  it('redirects missing sessions to member sign-in', async () => {
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: false, isLoading: false, user: null, login: vi.fn(), logout: vi.fn(),
    });

    renderGuard('/providers');
    expect(await screen.findByText('Member login')).toBeTruthy();
    expect(screen.queryByText('Provider directory')).toBeNull();
  });

  it('keeps administrator sessions out of member routes', async () => {
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: {
        id: 'admin-id',
        email: 'admin@example.com',
        first_name: 'Admin',
        last_name: 'User',
        full_name: 'Admin User',
        role: 'admin',
        roles: ['admin'],
        email_verified_at: null,
        last_successful_login_at: null,
        is_active: true,
      },
      login: vi.fn(),
      logout: vi.fn(),
    });

    renderGuard('/profile');
    expect(await screen.findByText('Admin login')).toBeTruthy();
    expect(screen.queryByText('Member profile')).toBeNull();
  });
});