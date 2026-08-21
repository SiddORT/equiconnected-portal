import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { EmailLogsPage } from './EmailLogsPage';

vi.mock('@/api/admin', () => ({ getEmailDeliveryLogs: vi.fn() }));

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
});