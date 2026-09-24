import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { VerificationResend } from './VerificationResend';
import * as authApi from '@/api/auth';

vi.mock('@/api/auth', () => ({ resendVerification: vi.fn(), resendVerificationToken: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('verification recovery', () => {
  it('requests another link without resubmitting signup', async () => {
    vi.mocked(authApi.resendVerification).mockResolvedValue({
      message: 'If this email belongs to an unverified account, a verification link will be sent when available.',
    });
    render(<VerificationResend email="rider@example.com" />);
    expect(screen.queryByRole('textbox')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Request a new verification link' }));
    await waitFor(() => expect(authApi.resendVerification).toHaveBeenCalledWith('rider@example.com'));
    expect(screen.getByRole('status').textContent).toContain('If this email belongs');
  });
  it('requests a link using the original token and never asks for an email', async () => {
    vi.mocked(authApi.resendVerificationToken).mockResolvedValue({ message: 'If this link belongs to an unverified account, a verification link will be sent when available.' });
    render(<VerificationResend token="original-link-token" />);
    expect(screen.queryByRole('textbox')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Request a new verification link' }));
    await waitFor(() => expect(authApi.resendVerificationToken).toHaveBeenCalledWith('original-link-token'));
    expect(screen.getByRole('status').textContent).toContain('If this link belongs');
  });
  it('keeps a missing-token recovery disabled', () => {
    render(<VerificationResend token={null} />);
    expect(screen.getByRole('button', { name: 'Request a new verification link' }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('status').textContent).toContain('Without a verification link');
    expect(screen.queryByRole('textbox')).toBeNull();
  });
  it('shows a request failure and restores the button', async () => {
    vi.mocked(authApi.resendVerification).mockRejectedValue(new Error('Network unavailable'));
    render(<VerificationResend email="rider@example.com" />);
    fireEvent.click(screen.getByRole('button', { name: 'Request a new verification link' }));
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Could not request a link'));
    expect(screen.getByRole('button', { name: 'Request a new verification link' }).hasAttribute('disabled')).toBe(false);
  });
});