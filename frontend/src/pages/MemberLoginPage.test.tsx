import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { MemberLoginPage } from './MemberLoginPage';
import { LoginPage } from './admin/LoginPage';

const { login, navigate } = vi.hoisted(() => ({
  login: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    login,
    logout: vi.fn(),
    user: null,
  }),
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigate };
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderMember(
  initialEntries: NonNullable<ComponentProps<typeof MemoryRouter>['initialEntries']> = ['/login']
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <MemberLoginPage />
    </MemoryRouter>
  );
}

describe('MemberLoginPage', () => {
  it('uses a member-focused presentation and member field identifiers', () => {
    renderMember();

    expect(screen.getByRole('heading', { name: 'Sign in to your care community' })).toBeTruthy();
    expect(screen.getByText('Discover trusted hospitals, clinics, and doctors for the horses who rely on you.')).toBeTruthy();
    expect(screen.getByLabelText('Email address').getAttribute('id')).toBe('member-email');
    expect(screen.getByLabelText('Password').getAttribute('id')).toBe('member-password');
    expect(screen.queryByText('Admin sign in')).toBeNull();
  });

  it('keeps the administrator presentation and identifiers separate', () => {
    render(
      <MemoryRouter initialEntries={['/admin/login']}>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: 'Admin sign in' })).toBeTruthy();
    expect(screen.getByText('Enter your administrator credentials to access the portal.')).toBeTruthy();
    expect(screen.getByLabelText('Email address').getAttribute('id')).toBe('admin-email');
    expect(screen.getByLabelText('Password').getAttribute('id')).toBe('admin-password');
    expect(screen.queryByText('Sign in to your care community')).toBeNull();
  });

  it('preserves verification handoff notice and email prefill', () => {
    renderMember([{
      pathname: '/login',
      state: {
        verifiedEmail: 'rider@example.com',
        verifiedNotice: 'Your email has been verified. You can now sign in.',
      },
    }]);

    expect(screen.getByDisplayValue('rider@example.com')).toBeTruthy();
    expect(screen.getByText('Your email has been verified. You can now sign in.')).toBeTruthy();
    expect(navigate).toHaveBeenCalledWith('/login', { replace: true, state: null });
  });

  it('validates credentials, toggles password visibility, and returns to the requested page', async () => {
    const user = userEvent.setup();
    login.mockResolvedValue(undefined);
    renderMember([{
      pathname: '/login',
      state: { from: { pathname: '/providers/demo-provider' } },
    }]);

    fireEvent.submit(screen.getByRole('button', { name: 'Sign in' }).closest('form')!);
    expect(await screen.findByText('Email is required')).toBeTruthy();
    expect(screen.getByText('Password is required')).toBeTruthy();

    await user.type(screen.getByLabelText('Email address'), ' Rider@Example.com ');
    await user.type(screen.getByLabelText('Password'), 'SecureHorse7');
    const password = screen.getByLabelText('Password');
    expect(password.getAttribute('type')).toBe('password');

    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(screen.getByLabelText('Password').getAttribute('type')).toBe('text');
    expect(screen.getByRole('button', { name: 'Hide password' }).getAttribute('aria-pressed')).toBe('true');

    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(login).toHaveBeenCalledWith('rider@example.com', 'SecureHorse7'));
    expect(navigate).toHaveBeenCalledWith('/providers/demo-provider', { replace: true });
  });
});