import { StrictMode } from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
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
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe('VerifyEmailPage', () => {
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