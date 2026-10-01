import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProviderPasswordSetupPage } from './ProviderPasswordSetupPage';

const { setupProviderPortalPassword, resetProviderPortalPassword } = vi.hoisted(() => ({
  setupProviderPortalPassword: vi.fn(),
  resetProviderPortalPassword: vi.fn(),
}));

vi.mock('@/api/auth', () => ({
  setupProviderPortalPassword,
  resetProviderPortalPassword,
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderSetup(path = '/provider/setup-password?token=invitation-token') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ProviderPasswordSetupPage />
    </MemoryRouter>
  );
}

describe('ProviderPasswordSetupPage', () => {
  it('disables setup when the token is missing', () => {
    renderSetup('/provider/setup-password');
    expect(screen.getByRole('alert').textContent).toContain('link is invalid');
    expect((screen.getByRole('button', { name: 'Set password' }) as HTMLButtonElement).disabled).toBe(true);
    expect(setupProviderPortalPassword).not.toHaveBeenCalled();
  });

  it.each([
    ['invalid', 404, 'provider_portal_link_invalid', 'link is invalid'],
    ['expired', 410, 'provider_portal_link_expired', 'link has expired'],
    ['used or replaced', 409, 'provider_portal_link_used', 'used or replaced'],
    ['network', undefined, undefined, 'Check your connection'],
    ['temporary service', 503, undefined, 'temporarily unavailable'],
    ['rate limited', 429, undefined, 'wait a few minutes'],
    ['validation', 422, undefined, '8–128 characters'],
    ['routing', 404, undefined, 'could not confirm'],
    ['unexpected response', 200, undefined, 'could not confirm'],
  ])('classifies %s failures and permits retry without clearing entered values', async (_name, status, code, message) => {
    const user = userEvent.setup();
    setupProviderPortalPassword.mockRejectedValueOnce({
      isAxiosError: true,
      response: status ? { status, data: { detail: { code, message: 'Untrusted server detail' } } } : undefined,
    }).mockResolvedValueOnce({ message: 'Password set' });
    renderSetup();
    await user.type(screen.getByLabelText('Password'), 'SyntheticSetup9');
    await user.type(screen.getByLabelText('Confirm password'), 'SyntheticSetup9');
    await user.click(screen.getByRole('button', { name: 'Set password' }));
    expect((await screen.findByRole('alert')).textContent).toContain(message);
    if (code !== 'provider_portal_link_invalid') {
      expect(screen.getByRole('alert').textContent).not.toContain('link is invalid');
    }
    expect(screen.queryByRole('heading', { name: 'Password set' })).toBeNull();
    expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('SyntheticSetup9');
    await user.click(screen.getByRole('button', { name: 'Set password' }));
    expect(await screen.findByRole('heading', { name: 'Password set' })).toBeTruthy();
    expect(setupProviderPortalPassword).toHaveBeenCalledTimes(2);
  });

  it('gives retry guidance for non-HTTP failures', async () => {
    setupProviderPortalPassword.mockRejectedValue(new Error('Unexpected response'));
    const user = userEvent.setup();
    renderSetup();
    await user.type(screen.getByLabelText('Password'), 'SyntheticSetup9');
    await user.type(screen.getByLabelText('Confirm password'), 'SyntheticSetup9');
    await user.click(screen.getByRole('button', { name: 'Set password' }));
    expect((await screen.findByRole('alert')).textContent).toContain('could not confirm');
  });

  it('rejects passwords above the API length limit without sending a request', async () => {
    const user = userEvent.setup();
    renderSetup();
    await user.type(screen.getByLabelText('Password'), `Synthetic9${'a'.repeat(120)}`);
    await user.click(screen.getByRole('button', { name: 'Set password' }));
    expect(screen.getByRole('alert').textContent).toContain('8–128 characters');
    expect(setupProviderPortalPassword).not.toHaveBeenCalled();
  });

  it('keeps both password fields masked by default and preserves their values while toggling independently', async () => {
    const user = userEvent.setup();
    renderSetup();

    const password = screen.getByLabelText('Password');
    const confirmation = screen.getByLabelText('Confirm password');
    expect(password.getAttribute('type')).toBe('password');
    expect(confirmation.getAttribute('type')).toBe('password');

    const showPassword = screen.getByRole('button', { name: 'Show password' });
    const showConfirmation = screen.getByRole('button', { name: 'Show password confirmation' });
    expect(showPassword.getAttribute('aria-pressed')).toBe('false');
    expect(showConfirmation.getAttribute('aria-pressed')).toBe('false');

    await user.type(password, 'SecureHorse7');
    await user.type(confirmation, 'SecureHorse7');
    await user.click(showPassword);

    expect(screen.getByLabelText('Password').getAttribute('type')).toBe('text');
    expect(screen.getByLabelText('Confirm password').getAttribute('type')).toBe('password');
    expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('SecureHorse7');
    expect((screen.getByLabelText('Confirm password') as HTMLInputElement).value).toBe('SecureHorse7');
    expect(screen.getByRole('button', { name: 'Hide password' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Show password confirmation' }).getAttribute('aria-pressed')).toBe('false');

    await user.click(showConfirmation);
    expect(screen.getByLabelText('Confirm password').getAttribute('type')).toBe('text');
    expect(screen.getByRole('button', { name: 'Hide password confirmation' }).getAttribute('aria-pressed')).toBe('true');

    await user.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(screen.getByLabelText('Password').getAttribute('type')).toBe('password');
    expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('SecureHorse7');
    expect((screen.getByLabelText('Confirm password') as HTMLInputElement).value).toBe('SecureHorse7');
  });

  it('supports keyboard activation and submits the existing token and password values', async () => {
    const user = userEvent.setup();
    setupProviderPortalPassword.mockResolvedValue({ message: 'Password set' });
    renderSetup();

    const password = screen.getByLabelText('Password');
    const confirmation = screen.getByLabelText('Confirm password');
    await user.type(password, 'SecureHorse7');
    await user.type(confirmation, 'SecureHorse7');

    const showPassword = screen.getByRole('button', { name: 'Show password' });
    showPassword.focus();
    await user.keyboard('{Enter}');
    expect(screen.getByLabelText('Password').getAttribute('type')).toBe('text');
    expect(screen.getByRole('button', { name: 'Hide password' }).getAttribute('aria-pressed')).toBe('true');

    await user.click(screen.getByRole('button', { name: 'Set password' }));
    await waitFor(() => {
      expect(setupProviderPortalPassword).toHaveBeenCalledWith(
        'invitation-token',
        'SecureHorse7',
        'SecureHorse7'
      );
    });
    expect(await screen.findByRole('heading', { name: 'Password set' })).toBeTruthy();
  });

  it('uses reset-specific copy and redeems the reset token through the reset endpoint', async () => {
    const user = userEvent.setup();
    resetProviderPortalPassword.mockResolvedValue({ message: 'Password reset' });
    renderSetup('/provider/reset-password?token=recovery-token');

    expect(screen.getByRole('heading', { name: 'Reset your password' })).toBeTruthy();
    expect(screen.getByText(/Choose a new secure password/)).toBeTruthy();
    await user.type(screen.getByLabelText('Password'), 'SecureHorse7');
    await user.type(screen.getByLabelText('Confirm password'), 'SecureHorse7');
    await user.click(screen.getByRole('button', { name: 'Reset password' }));

    await waitFor(() => expect(resetProviderPortalPassword).toHaveBeenCalledWith(
      'recovery-token',
      'SecureHorse7',
      'SecureHorse7'
    ));
    expect(setupProviderPortalPassword).not.toHaveBeenCalled();
    expect(await screen.findByRole('heading', { name: 'Password reset' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Go to provider sign in' }).getAttribute('href'))
      .toBe('/provider/login');
  });

  it.each([
    [
      'invalid',
      404,
      'provider_portal_recovery_link_invalid',
      'This password reset link is invalid.',
    ],
    [
      'expired',
      410,
      'provider_portal_recovery_link_expired',
      'This password reset link has expired.',
    ],
    [
      'used',
      409,
      'provider_portal_recovery_link_used',
      'This password reset link has already been used or replaced.',
    ],
  ])('gives specific replacement guidance for an %s reset link without generic retry advice', async (
    _state,
    status,
    code,
    guidance
  ) => {
    const user = userEvent.setup();
    resetProviderPortalPassword.mockRejectedValue({
      isAxiosError: true,
      response: { status, data: { detail: { code, message: 'Untrusted server detail' } } },
    });
    renderSetup('/provider/reset-password?token=recovery-token');
    await user.type(screen.getByLabelText('Password'), 'SecureHorse7');
    await user.type(screen.getByLabelText('Confirm password'), 'SecureHorse7');
    await user.click(screen.getByRole('button', { name: 'Reset password' }));

    const message = (await screen.findByRole('alert')).textContent ?? '';
    expect(message).toContain(guidance);
    expect(message.toLowerCase()).toContain('ask an administrator to send a new password reset email');
    expect(message).not.toContain('try again with this link');
    expect(message).not.toContain('Untrusted server detail');
  });
});