import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppRouter } from './Router';

vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    user: null,
  }),
}));

afterEach(() => {
  cleanup();
  window.history.replaceState({}, '', '/');
});

describe('AppRouter member entry', () => {
  it('sends anonymous /member visitors to member sign-in with provider discovery preserved', async () => {
    window.history.replaceState({}, '', '/member');

    render(<AppRouter />);

    await waitFor(() => expect(window.location.pathname).toBe('/login'));
    expect(screen.getByRole('heading', { name: 'Sign in to your care community' })).toBeTruthy();
    expect(window.history.state.usr?.from?.pathname).toBe('/providers');
  });
});