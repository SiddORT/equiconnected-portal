import { StrictMode } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemberPasswordRecoveryPage } from './MemberPasswordRecoveryPage';
import { MemberLoginPage } from './MemberLoginPage';

const { request, reset, logout, auth } = vi.hoisted(() => ({
  request: vi.fn(), reset: vi.fn(), logout: vi.fn(),
  auth: { isAuthenticated: false, isLoading: false, user: null as null | {
    id: string; email: string; full_name: string; role: string; roles: string[];
  } },
}));
vi.mock('@/api/auth', () => ({
  requestMemberPasswordRecovery: request, resetMemberPassword: reset,
}));
vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({ ...auth, logout, login: vi.fn() }),
}));

function renderRecovery(path = '/forgot-password') {
  const router = createMemoryRouter([
    { path: '/forgot-password', element: <MemberPasswordRecoveryPage key="request" /> },
    { path: '/reset-password', element: <MemberPasswordRecoveryPage key="reset" /> },
    { path: '/login', element: <MemberLoginPage /> },
  ], { initialEntries: [path] });
  render(<StrictMode><RouterProvider router={router} /></StrictMode>);
  return router;
}
function rejection(code: string, status = 400) {
  return { isAxiosError: true, response: { status, data: { detail: { code } } } };
}
async function fillReset(password = 'SecureHorse7', confirmation = password) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('New password'), password);
  await user.type(screen.getByLabelText('Confirm new password'), confirmation);
  await user.click(screen.getByRole('button', { name: 'Reset password' }));
  return user;
}
beforeEach(() => {
  auth.isAuthenticated = false;
  auth.isLoading = false;
  auth.user = null;
  request.mockResolvedValue({ message: 'Generic acknowledgment' });
  reset.mockResolvedValue({ message: 'Password reset' });
  logout.mockResolvedValue(undefined);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe('member recovery request', () => {
  it('links member login to member recovery, never provider setup', async () => {
    const user = userEvent.setup();
    renderRecovery('/login');
    const link = screen.getByRole('link', { name: 'Forgot password?' });
    expect(link.getAttribute('href')).toBe('/forgot-password');
    await user.click(link);
    expect(screen.getByRole('heading', { name: 'Reset your password' })).toBeTruthy();
  });
  it('validates email, normalizes it, and acknowledges without revealing eligibility', async () => {
    const user = userEvent.setup();
    renderRecovery();
    await user.click(screen.getByRole('button', { name: 'Send recovery email' }));
    expect(screen.getByRole('alert').textContent).toContain('Enter a valid email');
    expect(request).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText('Email address'), ' Unknown@Example.com ');
    await user.click(screen.getByRole('button', { name: 'Send recovery email' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith('unknown@example.com'));
    expect(screen.getByRole('status').textContent).toContain('If the account is eligible');
    await user.click(screen.getByRole('button', { name: 'Request another email' }));
    expect(screen.getByLabelText('Email address')).toBeTruthy();
  });
  it('uses the signed-in account rather than a client-supplied email', async () => {
    auth.isAuthenticated = true;
    auth.user = { id: 'member', email: 'rider@example.com', full_name: 'Rider', role: 'horse_owner', roles: ['horse_owner'] };
    const user = userEvent.setup();
    renderRecovery();
    expect(screen.queryByLabelText('Email address')).toBeNull();
    expect(screen.getByText('rider@example.com')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Send recovery email' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(undefined));
  });
  it('offers retry rather than false acknowledgment after a temporary request failure', async () => {
    request.mockRejectedValueOnce(new Error('Network unavailable'));
    const user = userEvent.setup();
    renderRecovery();
    await user.type(screen.getByLabelText('Email address'), 'rider@example.com');
    await user.click(screen.getByRole('button', { name: 'Send recovery email' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Check your connection');
    expect(screen.queryByRole('status')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Send recovery email' }));
    expect(await screen.findByRole('status')).toBeTruthy();
  });
});

describe('member recovery redemption', () => {
  it.each(['/reset-password#token=private-token', '/reset-password?token=private-token'])(
    'captures and removes the URL credential safely under Strict Mode: %s', async (path) => {
      const router = renderRecovery(path);
      await waitFor(() => expect(router.state.location.hash + router.state.location.search).toBe(''));
      expect(reset).not.toHaveBeenCalled();
      await fillReset();
      await waitFor(() => expect(reset).toHaveBeenCalledTimes(1));
      expect(reset).toHaveBeenCalledWith('private-token', 'SecureHorse7', 'SecureHorse7');
      expect(await screen.findByText('Your password has been reset. Sign in with your new password.')).toBeTruthy();
      expect(router.state.location.pathname).toBe('/login');
      expect(logout).not.toHaveBeenCalled();
    },
  );
  it('enforces password policy and confirmation before redemption', async () => {
    renderRecovery('/reset-password#token=private-token');
    const user = await fillReset('weak');
    expect(screen.getByRole('alert').textContent).toContain('8–128 characters');
    expect(reset).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText('New password'));
    await user.type(screen.getByLabelText('New password'), 'SecureHorse7');
    await user.click(screen.getByRole('button', { name: 'Reset password' }));
    expect(screen.getByRole('alert').textContent).toContain('Passwords do not match');
    expect(reset).not.toHaveBeenCalled();
  });
  it.each([
    ['member_recovery_link_invalid', 'invalid'],
    ['member_recovery_link_expired', 'expired'],
    ['member_recovery_link_used', 'already been used or replaced'],
  ])('gives distinct guidance for %s and a new-request action', async (code, text) => {
    reset.mockRejectedValue(rejection(code));
    renderRecovery('/reset-password#token=private-token');
    await fillReset();
    expect((await screen.findByRole('alert')).textContent).toContain(text);
    expect((screen.getByRole('button', { name: 'Reset password' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole('link', { name: 'Request a new recovery email' }).getAttribute('href')).toBe('/forgot-password');
    expect(screen.getByRole('link', { name: 'Return to member sign in' })).toBeTruthy();
  });
  it('retains a usable token for retry after network failure and mentions possible prior success', async () => {
    reset.mockRejectedValueOnce(new Error('Lost response'));
    renderRecovery('/reset-password#token=private-token');
    const user = await fillReset();
    expect((await screen.findByRole('alert')).textContent).toContain('try signing in first');
    expect((screen.getByRole('button', { name: 'Reset password' }) as HTMLButtonElement).disabled).toBe(false);
    await user.click(screen.getByRole('button', { name: 'Reset password' }));
    expect(await screen.findByText('Your password has been reset. Sign in with your new password.')).toBeTruthy();
    expect(reset).toHaveBeenCalledTimes(2);
    expect(reset.mock.calls[1][0]).toBe('private-token');
  });
  it('clears a signed-in member session on success without automatically signing in', async () => {
    auth.isAuthenticated = true;
    auth.user = { id: 'member', email: 'rider@example.com', full_name: 'Rider', role: 'horse_owner', roles: ['horse_owner'] };
    logout.mockImplementation(async () => { auth.isAuthenticated = false; auth.user = null; });
    renderRecovery('/reset-password#token=private-token');
    await fillReset();
    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('Your password has been reset. Sign in with your new password.')).toBeTruthy();
  });
  it('rejects a missing link without submitting', async () => {
    renderRecovery('/reset-password');
    expect(screen.getByRole('alert').textContent).toContain('invalid');
    expect((screen.getByRole('button', { name: 'Reset password' }) as HTMLButtonElement).disabled).toBe(true);
    expect(reset).not.toHaveBeenCalled();
  });
});