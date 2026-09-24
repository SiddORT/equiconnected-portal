import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppRouter } from './Router';

vi.mock('@/app/TimeSettingsContext', () => ({
  systemCalendarDate: () => '2026-08-31',
  useTimeSettings: () => ({ settings: { timezone: 'UTC' }, isLoading: false, error: null }),
}));
vi.mock('@/hooks/usePublicPageAnimations', () => ({ usePublicPageAnimations: vi.fn() }));
vi.mock('@/api/public', () => ({
  recordPublicVisit: vi.fn(() => Promise.resolve()),
  registerSubscriber: vi.fn(),
  listPublicProviders: vi.fn(() => Promise.resolve([])),
}));

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
  it('sends legacy /member visitors to the landing page', async () => {
    window.history.replaceState({}, '', '/member');

    render(<AppRouter />);

    await waitFor(() => expect(window.location.pathname).toBe('/'));
    expect(screen.getByRole('heading', { name: 'Healthcare, Connected Around You.' })).toBeTruthy();
  });

  it('preserves an anonymous provider-detail deep link through member sign-in', async () => {
    window.history.replaceState({}, '', '/providers/demo-provider');
    render(<AppRouter />);
    await waitFor(() => expect(window.location.pathname).toBe('/login'));
    expect(window.history.state.usr?.from?.pathname).toBe('/providers/demo-provider');
  });
});