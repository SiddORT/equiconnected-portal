import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { EmailLogsPage } from './EmailLogsPage';

vi.mock('@/api/admin', () => ({ getEmailDeliveryLogs: vi.fn(), sendSMTPTest: vi.fn() }));
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
  expect(adminApi.sendSMTPTest).not.toHaveBeenCalled();
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

    expect(screen.getByRole('heading', { name: 'Email Logs' })).toBeTruthy();
    expect(await screen.findByText('recipient@example.com')).toBeTruthy();
    expect(screen.getByText('Accepted by SMTP')).toBeTruthy();

    await user.selectOptions(screen.getByLabelText('Date filter'), 'month');
    expect(adminApi.getEmailDeliveryLogs).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2026-01' } });
    await waitFor(() => expect(adminApi.getEmailDeliveryLogs).toHaveBeenLastCalledWith(
      expect.objectContaining({ filter_mode: 'month', month: 1, year: 2026 }),
    ));
  });

  it('labels contact notification attempts distinctly from invitations', async () => {
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [{ ...emailLog, purpose: 'contact_notification' }],
      meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
    });
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);

    expect(await screen.findByText('Contact notification')).toBeTruthy();
    expect(screen.queryByText('Provider profile invitation')).toBeNull();
  });

  it('labels contact confirmation attempts distinctly from notifications', async () => {
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [{ ...emailLog, purpose: 'contact_confirmation' }],
      meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
    });
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);

    expect(await screen.findByText('Contact confirmation')).toBeTruthy();
    expect(screen.queryByText('Contact notification')).toBeNull();
  });

  it('puts filters directly after the header without test-send controls or feedback', async () => {
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [{ ...emailLog, purpose: 'smtp_test', recipient_email: 'admin@example.com' }],
      meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
    });
    const { container } = render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);
    expect(await screen.findByText('SMTP test')).toBeTruthy();
    const filterForm = screen.getByLabelText('Date filter').closest('form');
    expect(filterForm?.parentElement?.firstElementChild).toBe(filterForm);
    expect(filterForm?.parentElement?.previousElementSibling?.contains(
      screen.getByRole('heading', { name: 'Email Logs' }),
    )).toBe(true);
    expect(container.querySelector('#smtp-test-heading')).toBeNull();
    expect(screen.queryByText(/your admin-account email address|cannot choose another recipient/)).toBeNull();
    expect(screen.queryByRole('button', { name: /Send test email|Confirm send|Sending|Cancel/ })).toBeNull();
    expect(screen.queryByText(/SMTP acceptance only confirms|does not guarantee inbox delivery/)).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  it('keeps historical SMTP test attempts readable with every existing status label', async () => {
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [
        { ...emailLog, id: 'accepted', purpose: 'smtp_test' },
        { ...emailLog, id: 'pending', purpose: 'smtp_test', status: 'pending' },
        { ...emailLog, id: 'failed', purpose: 'smtp_test', status: 'failed',
          failure_message: 'SMTP authentication failed.' },
      ],
      meta: { page: 1, page_size: 25, total: 3, total_pages: 1 },
    });
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);
    expect(await screen.findAllByText('SMTP test')).toHaveLength(3);
    const table = screen.getByRole('table', { name: 'Email delivery logs' });
    expect(within(table).getByText('Accepted by SMTP')).toBeTruthy();
    expect(within(table).getByText('Outcome pending')).toBeTruthy();
    expect(within(table).getByText('Failed')).toBeTruthy();
    expect(within(table).getByText('SMTP authentication failed.')).toBeTruthy();
  });

  it('clears the date filter and returns to the first page while retaining page size', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [emailLog], meta: { page: 2, page_size: 10, total: 30, total_pages: 3 },
    });
    render(<MemoryRouter initialEntries={['/?filter_mode=day&date=2026-01-02&page=2&page_size=10']}>
      <EmailLogsPage />
    </MemoryRouter>);
    await screen.findByText('recipient@example.com');
    expect(screen.getByText('Showing 2026-01-02')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Clear filter' }));
    await waitFor(() => expect(adminApi.getEmailDeliveryLogs).toHaveBeenLastCalledWith({
      filter_mode: undefined, date: undefined, month: undefined, year: undefined,
      date_from: undefined, date_to: undefined, page: 1, page_size: 10,
    }));
    expect(screen.getByText('Showing all email attempts')).toBeTruthy();
    expect(screen.queryByLabelText('Day')).toBeNull();
    expect(screen.getByRole('button', { name: 'Clear filter' }).hasAttribute('disabled')).toBe(true);
  });

  it.each([
    ['messaging_member_acknowledgement', 'Private message acknowledgement'],
    ['member_password_recovery', 'Member password recovery'],
    ['messaging_provider_new_message', 'New private provider message'],
    ['messaging_member_reply', 'Private message reply notification'],
  ] as const)('labels %s delivery attempts', async (purpose, label) => {
    vi.mocked(adminApi.getEmailDeliveryLogs).mockResolvedValue({
      data: [{ ...emailLog, purpose }],
      meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
    });
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);

    expect(await screen.findByText(label)).toBeTruthy();
  });

  it('paginates filtered logs and resets the page when changing page size', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.getEmailDeliveryLogs).mockImplementation(async (params) => ({
      data: [emailLog],
      meta: { page: params?.page ?? 1, page_size: params?.page_size ?? 25,
        total: 60, total_pages: Math.ceil(60 / (params?.page_size ?? 25)) },
    }));
    render(<MemoryRouter initialEntries={['/?filter_mode=year&year=2026']}>
      <EmailLogsPage />
    </MemoryRouter>);
    await screen.findByText('recipient@example.com');
    expect(screen.getByRole('button', { name: /Previous/ }).hasAttribute('disabled')).toBe(true);
    await user.click(screen.getByRole('button', { name: /Next/ }));
    await waitFor(() => expect(screen.getByText('Showing 26 to 50 of 60 entries')).toBeTruthy());
    expect(adminApi.getEmailDeliveryLogs).toHaveBeenLastCalledWith(
      expect.objectContaining({ filter_mode: 'year', year: 2026, page: 2, page_size: 25 }),
    );
    await user.click(screen.getByRole('button', { name: /Previous/ }));
    await waitFor(() => expect(screen.getByText('Showing 1 to 25 of 60 entries')).toBeTruthy());
    await user.click(screen.getByRole('button', { name: /Next/ }));
    await screen.findByText('Showing 26 to 50 of 60 entries');
    await user.selectOptions(screen.getByLabelText('Rows per page'), '100');
    await waitFor(() => expect(screen.getByText('Showing 1 to 60 of 60 entries')).toBeTruthy());
    expect(adminApi.getEmailDeliveryLogs).toHaveBeenLastCalledWith(
      expect.objectContaining({ filter_mode: 'year', year: 2026, page: 1, page_size: 100 }),
    );
    expect(screen.getByRole('button', { name: /Next/ }).hasAttribute('disabled')).toBe(true);
  });

  it('shows loading and empty states without test-send controls', async () => {
    let finish!: (value: Awaited<ReturnType<typeof adminApi.getEmailDeliveryLogs>>) => void;
    vi.mocked(adminApi.getEmailDeliveryLogs).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);
    expect(screen.getByLabelText('Loading email logs…')).toBeTruthy();
    await act(async () => finish({
      data: [], meta: { page: 1, page_size: 25, total: 0, total_pages: 1 },
    }));
    expect(await screen.findByText('No email attempts found')).toBeTruthy();
    expect(screen.getByText('Future transactional email attempts will appear here.')).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
  });

  it('retries a failed log request without sending a test email', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.getEmailDeliveryLogs).mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
      data: [], meta: { page: 1, page_size: 25, total: 0, total_pages: 1 },
    });
    render(<MemoryRouter><EmailLogsPage /></MemoryRouter>);
    expect(await screen.findByText('Failed to load email logs')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('No email attempts found')).toBeTruthy();
    expect(adminApi.getEmailDeliveryLogs).toHaveBeenCalledTimes(2);
  });
});
