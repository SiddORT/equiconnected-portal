import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProviderPasswordSetupPage } from './ProviderPasswordSetupPage';

const { setupProviderPortalPassword } = vi.hoisted(() => ({
  setupProviderPortalPassword: vi.fn(),
}));

vi.mock('@/api/auth', () => ({
  setupProviderPortalPassword,
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderSetup() {
  return render(
    <MemoryRouter initialEntries={['/provider/setup-password?token=invitation-token']}>
      <ProviderPasswordSetupPage />
    </MemoryRouter>
  );
}

describe('ProviderPasswordSetupPage', () => {
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
});