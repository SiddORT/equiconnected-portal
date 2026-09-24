import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as authApi from '@/api/auth';
import { VerifyEmailPage } from './VerifyEmailPage';

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
  it('recovers a failed link using its retained token after clearing the address bar', async () => {
    vi.mocked(authApi.verifyEmail).mockRejectedValue(new Error('Expired'));
    vi.mocked(authApi.resendVerificationToken).mockResolvedValue({ message: 'If this link belongs to an unverified account, a verification link will be sent when available.' });
    const replace = vi.spyOn(window.history, 'replaceState');
    try {
      render(<MemoryRouter initialEntries={['/verify-email?token=expired-token-value-123456']}><VerifyEmailPage /></MemoryRouter>);
      expect(await screen.findByRole('heading', { name: 'Unable to verify email' })).toBeTruthy();
      expect(replace).toHaveBeenCalledWith({}, document.title, '/verify-email');
      expect(screen.queryByRole('textbox')).toBeNull();
      fireEvent.click(screen.getByRole('button', { name: 'Request a new verification link' }));
      await act(async () => { await Promise.resolve(); });
      expect(authApi.resendVerificationToken).toHaveBeenCalledWith('expired-token-value-123456');
    } finally { replace.mockRestore(); }
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