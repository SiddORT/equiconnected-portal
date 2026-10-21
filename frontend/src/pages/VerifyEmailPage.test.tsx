import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as authApi from '@/api/auth';
import { VerifyEmailPage } from './VerifyEmailPage';
import styles from './SignupPage.module.css';

const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigate };
});

vi.mock('@/api/auth', () => ({
  verifyEmail: vi.fn(),
  resendVerificationToken: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe('VerifyEmailPage', () => {
  it.each(['invalid', 'expired', 'used'])('recovers an unsuccessful %s link using its retained token after clearing the address bar', async (reason) => {
    const message = `Verification link ${reason}.`;
    vi.mocked(authApi.verifyEmail).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: { code: `verification_link_${reason}`, message } } },
    });
    vi.mocked(authApi.resendVerificationToken).mockResolvedValue({ message: 'If this link belongs to an unverified account, a verification link will be sent when available.' });
    const replace = vi.spyOn(window.history, 'replaceState');
    try {
      render(<MemoryRouter initialEntries={['/verify-email?token=expired-token-value-123456']}><VerifyEmailPage /></MemoryRouter>);
      expect(await screen.findByRole('heading', { name: 'Unable to verify email' })).toBeTruthy();
      expect(screen.getByText(message)).toBeTruthy();
      expect(screen.getByRole('link', { name: 'Return to EquiConnected' }).getAttribute('href')).toBe('/');
      expect(replace).toHaveBeenCalledWith({}, document.title, '/verify-email');
      expect(screen.queryByRole('textbox')).toBeNull();
      fireEvent.click(screen.getByRole('button', { name: 'Request a new verification link' }));
      await act(async () => { await Promise.resolve(); });
      expect(authApi.resendVerificationToken).toHaveBeenCalledWith('expired-token-value-123456');
      expect(navigate).not.toHaveBeenCalled();
    } finally { replace.mockRestore(); }
  });

  it('keeps provider approval confirmation visible under Strict Mode beyond the old redirect delay', async () => {
    vi.useFakeTimers();
    const message = 'Your email has been verified. Your account is awaiting administrator approval. Once approved, you’ll receive an email with a link to sign in.';
    vi.mocked(authApi.verifyEmail).mockResolvedValue({
      message,
      email: 'synthetic.provider@example.test',
      outcome: 'provider_awaiting_approval',
    });
    const { container } = render(
      <MemoryRouter initialEntries={['/verify-email?token=synthetic-provider-token']}>
        <StrictMode><VerifyEmailPage /></StrictMode>
      </MemoryRouter>
    );
    await act(async () => { await Promise.resolve(); });
    expect(authApi.verifyEmail).toHaveBeenCalledExactlyOnceWith('synthetic-provider-token');
    expect(screen.getByText(message)).toBeTruthy();
    expect(screen.queryByText(/Redirecting/)).toBeNull();
    expect(container.querySelector(`.${styles.redirectTrack}`)).toBeNull();
    expect(screen.queryByRole('link', { name: /sign in/i })).toBeNull();
    expect(screen.getByRole('link', { name: 'Return to EquiConnected' }).getAttribute('href')).toBe('/');
    expect(vi.getTimerCount()).toBe(0);
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(screen.getByRole('heading', { name: 'Email verified successfully' })).toBeTruthy();
    expect(screen.getByText(message)).toBeTruthy();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('clears a scheduled member redirect on unmount', async () => {
    vi.useFakeTimers();
    vi.mocked(authApi.verifyEmail).mockResolvedValue({ email: 'member@example.test', message: 'Verified.' });
    const { unmount } = render(
      <MemoryRouter initialEntries={['/verify-email?token=synthetic-member-token']}>
        <StrictMode><VerifyEmailPage /></StrictMode>
      </MemoryRouter>
    );
    await act(async () => { await Promise.resolve(); });
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(navigate).not.toHaveBeenCalled();
  });

  it('ignores a verification response received after unmount', async () => {
    vi.useFakeTimers();
    let resolve!: (value: Awaited<ReturnType<typeof authApi.verifyEmail>>) => void;
    vi.mocked(authApi.verifyEmail).mockReturnValue(new Promise((done) => { resolve = done; }));
    const { unmount } = render(
      <MemoryRouter initialEntries={['/verify-email?token=synthetic-member-token']}>
        <StrictMode><VerifyEmailPage /></StrictMode>
      </MemoryRouter>
    );
    unmount();
    await act(async () => { resolve({ email: 'member@example.test', message: 'Verified.' }); });
    expect(vi.getTimerCount()).toBe(0);
    expect(navigate).not.toHaveBeenCalled();
    expect(authApi.verifyEmail).toHaveBeenCalledTimes(1);
  });

  it('disables resend when the verification URL has no token', async () => {
    render(<MemoryRouter initialEntries={['/verify-email']}><VerifyEmailPage /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: 'Unable to verify email' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Request a new verification link' }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByText(/Without a verification link/)).toBeTruthy();
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(authApi.verifyEmail).not.toHaveBeenCalled();
  });

  it('shows the successful verification state before redirecting to member sign in', async () => {
    vi.useFakeTimers();
    vi.mocked(authApi.verifyEmail).mockResolvedValue({
      message: 'Your email has been verified. You can now sign in.',
      email: 'rider@example.com',
    });

    render(
      <MemoryRouter initialEntries={['/verify-email?token=one-time-token']}>
        <StrictMode>
          <VerifyEmailPage />
        </StrictMode>
      </MemoryRouter>
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByRole('heading', { name: 'Email verified successfully' })).toBeTruthy();
    expect(screen.getByText('Redirecting you to member sign in…')).toBeTruthy();
    expect(authApi.verifyEmail).toHaveBeenCalledExactlyOnceWith('one-time-token');
    expect(navigate).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1799);
    });
    expect(navigate).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(navigate).toHaveBeenCalledWith('/login', {
      replace: true,
      state: {
        verifiedEmail: 'rider@example.com',
        verifiedNotice: 'Your email has been verified. You can now sign in.',
      },
    });
  });
});