import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { VerificationResend } from './VerificationResend';
import * as authApi from '@/api/auth';

vi.mock('@/api/auth', () => ({ resendVerification: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('verification recovery', () => {
  it('requests another link without resubmitting signup', async () => {
    vi.mocked(authApi.resendVerification).mockResolvedValue({
      message: 'If this email belongs to an unverified account, a verification link will be sent when available.',
    });
    render(<VerificationResend initialEmail="rider@example.com" />);
    fireEvent.click(screen.getByRole('button', { name: 'Request a new verification link' }));
    await waitFor(() => expect(authApi.resendVerification).toHaveBeenCalledWith('rider@example.com'));
    expect(screen.getByRole('status').textContent).toContain('If this email belongs');
  });
});