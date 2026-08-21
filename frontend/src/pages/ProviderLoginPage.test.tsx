import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProviderLoginPage } from './ProviderLoginPage';

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

function renderProvider(
  initialEntries: NonNullable<ComponentProps<typeof MemoryRouter>['initialEntries']> = ['/provider/login']
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ProviderLoginPage />
    </MemoryRouter>
  );
}

describe('ProviderLoginPage', () => {
  it('uses a provider-specific care layout with an accessible credential form', () => {
    renderProvider();

    expect(screen.getByTestId('provider-login-page').getAttribute('data-layout')).toBe(
      'provider-care-story-left-form'
    );
    expect(screen.getByTestId('provider-login-page').getAttribute('data-mobile-layout')).toBe(
      'single-column-at-820px'
    );
    expect(screen.getByTestId('provider-care-panel')).toBeTruthy();
    expect(screen.getByTestId('provider-login-form')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Welcome back to your practice.' })).toBeTruthy();
    expect(screen.getByText('Care that keeps every horse moving forward.')).toBeTruthy();
    expect(screen.getByAltText("A hoof-care specialist supporting a horse's raised leg during a routine examination.").getAttribute('src')).toBe(
      '/provider-veterinary-care.jpg'
    );
    expect(screen.getByLabelText('Email address').getAttribute('id')).toBe('provider-login-email');
    expect(screen.getByLabelText('Email address').getAttribute('placeholder')).toBe('you@practice.com');
    expect(screen.getByLabelText('Password').getAttribute('placeholder')).toBe('Enter your password');
    expect(screen.getByRole('link', { name: 'Register your provider practice' }).getAttribute('href')).toBe('/provider/signup');
  });

  it('keeps the verification handoff prefilled and clears transient route state', () => {
    renderProvider([{
      pathname: '/provider/login',
      state: {
        verifiedEmail: 'clinician@example.com',
        verifiedNotice: 'Your email has been verified. You can now sign in.',
      },
    }]);

    expect(screen.getByDisplayValue('clinician@example.com')).toBeTruthy();
    expect(screen.getByRole('alert').textContent).toContain('Your email has been verified. You can now sign in.');
    expect(navigate).toHaveBeenCalledWith('/provider/login', { replace: true, state: null });
  });

  it('gives incomplete submissions, password visibility, loading, and normalized provider navigation clear feedback', async () => {
    const user = userEvent.setup();
    let resolveLogin: (() => void) | undefined;
    login.mockImplementation(() => new Promise<void>((resolve) => {
      resolveLogin = resolve;
    }));
    renderProvider();

    fireEvent.submit(screen.getByRole('button', { name: 'Sign in to provider portal' }).closest('form')!);
    expect((await screen.findByRole('alert')).textContent).toContain('Enter your email address and password.');
    expect(login).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText('Email address'), ' Provider@Example.com ');
    await user.type(screen.getByLabelText('Password'), 'SecureHorse7');
    expect(screen.getByLabelText('Password').getAttribute('type')).toBe('password');

    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(screen.getByLabelText('Password').getAttribute('type')).toBe('text');
    expect(screen.getByRole('button', { name: 'Hide password' }).getAttribute('aria-pressed')).toBe('true');

    await user.click(screen.getByRole('button', { name: 'Sign in to provider portal' }));
    expect(screen.getByRole('button', { name: 'Signing in…' }).getAttribute('aria-busy')).toBe('true');
    expect(screen.getByLabelText('Email address').getAttribute('disabled')).not.toBeNull();
    expect(login).toHaveBeenCalledWith('provider@example.com', 'SecureHorse7');

    resolveLogin?.();
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/provider/account', { replace: true }));
  });

  it('returns authentication failures through an accessible, safe alert', async () => {
    const user = userEvent.setup();
    login.mockRejectedValue(new Error('We could not verify those provider credentials.'));
    renderProvider();

    await user.type(screen.getByLabelText('Email address'), 'provider@example.com');
    await user.type(screen.getByLabelText('Password'), 'SecureHorse7');
    await user.click(screen.getByRole('button', { name: 'Sign in to provider portal' }));

    expect((await screen.findByRole('alert')).textContent).toContain('Sign in failed. Please check your credentials.');
  });
});