import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { EmailLogsPage } from './EmailLogsPage';

vi.mock('@/api/admin', () => ({ getEmailDeliveryLogs: vi.fn(), sendSMTPTest: vi.fn() }));
vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({ user: { email: 'admin@example.com' } }),
}));
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => value,
  }),
}));

const emailLog = {
  id: 'email-log-1',
  recipient_email: 'recipient@example.com',
  purpose: 'provider_invitation' as const,
  status: 'success' as const,
  failure_message: null,
  created_at: '2026-01-02T12:00:00Z',
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('EmailLogsPage', () => {
  it('shows safe delivery rows and sends the selected date mode to the API', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [emailLog],
      meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
    });
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Email Logs' })).toBeTruthy();
    expect(screen.getByText('recipient@example.com')).toBeTruthy();
    expect(screen.getByText('Accepted by SMTP')).toBeTruthy();

    await user.selectOptions(screen.getByLabelText('Date filter'), 'month');
    expect(adminApi.getEmailDeliveryLogs).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2026-01' } });
    await waitFor(() => expect(adminApi.getEmailDeliveryLogs).toHaveBeenLastCalledWith(
      expect.objectContaining({ filter_mode: 'month', month: 1, year: 2026 }),
    ));
  });

  it('confirms the fixed recipient, shows progress and refreshes logs after SMTP acceptance', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [{ ...emailLog, purpose: 'smtp_test', recipient_email: 'admin@example.com' }],
      meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
    });
    let finish!: (value: { status: 'success'; failure_message: null }) => void;
    vi.mocked(adminApi.sendSMTPTest).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);
    expect(await screen.findByText('SMTP test')).toBeTruthy();
    expect(screen.getByText(/your admin-account email address/)).toBeTruthy();
    expect(screen.queryByRole('textbox')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Send test email' }));
    expect(adminApi.sendSMTPTest).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Confirm send' }));
    expect(screen.getByRole('button', { name: 'Sending…' }).hasAttribute('disabled')).toBe(true);
    finish({ status: 'success', failure_message: null });
    expect(await screen.findByRole('status')).toHaveProperty('textContent',
      'Accepted by SMTP. This does not guarantee inbox delivery.');
    await waitFor(() => expect(adminApi.getEmailDeliveryLogs).toHaveBeenCalledTimes(2));
    expect(adminApi.sendSMTPTest).toHaveBeenCalledWith();
  });

  it('shows safe failure and rate-limit guidance without exposing API errors', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [], meta: { page: 1, page_size: 25, total: 0, total_pages: 1 },
    });
    vi.mocked(adminApi.sendSMTPTest).mockResolvedValueOnce({
      status: 'failed', failure_message: 'SMTP authentication failed.',
    }).mockRejectedValueOnce(Object.assign(new Error('smtp-password=secret'), {
      isAxiosError: true,
      response: { data: { detail: { code: 'rate_limited' } } },
    }));
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);
    await user.click(screen.getByRole('button', { name: 'Send test email' }));
    await user.click(screen.getByRole('button', { name: 'Confirm send' }));
    expect(await screen.findByText('Test failed: SMTP authentication failed.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Send test email' }));
    await user.click(screen.getByRole('button', { name: 'Confirm send' }));
    expect(await screen.findByText('Too many SMTP tests. Please try again later.')).toBeTruthy();
    expect(screen.queryByText(/smtp-password/)).toBeNull();
  });
});