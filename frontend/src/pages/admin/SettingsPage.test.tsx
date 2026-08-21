import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { SettingsPage } from './SettingsPage';

// Mock API module
vi.mock('@/api/admin', () => ({
  getSystemSettings: vi.fn(),
  updateSystemSettings: vi.fn(),
}));

// Mock TimeSettingsContext so we don't need the full provider tree
const mockRefresh = vi.fn();
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    settings: { timezone: 'UTC', date_format: 'month_day_year', time_format: '12_hour' },
    isLoading: false,
    error: null,
    formatTimestamp: (v: string) => v,
    formatDate: (v: string) => v,
    formatWeekday: (v: string) => v,
    refresh: mockRefresh,
  }),
}));

const baseSettings = {
  timezone: 'UTC',
  date_format: 'month_day_year' as const,
  time_format: '12_hour' as const,
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>
  );
}

describe('SettingsPage', () => {
  it('loads and displays current settings', async () => {
    vi.mocked(adminApi.getSystemSettings).mockResolvedValueOnce(baseSettings);
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeTruthy();

    await waitFor(() =>
      expect((screen.getByLabelText('Timezone') as HTMLSelectElement).value).toBe('UTC')
    );
    expect((screen.getByLabelText('Date format') as HTMLSelectElement).value).toBe('month_day_year');
    expect((screen.getByLabelText('Time format') as HTMLSelectElement).value).toBe('12_hour');
  });

  it('shows live preview that updates when selects change', async () => {
    vi.mocked(adminApi.getSystemSettings).mockResolvedValueOnce(baseSettings);
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect((screen.getByLabelText('Timezone') as HTMLSelectElement).value).toBe('UTC')
    );

    // Preview section should exist
    expect(screen.getByLabelText('Format preview')).toBeTruthy();

    // Change date format and verify preview section still renders
    await user.selectOptions(screen.getByLabelText('Date format'), 'day_month_year');
    expect(screen.getByLabelText('Format preview')).toBeTruthy();
  });

  it('saves settings and calls refresh on success', async () => {
    vi.mocked(adminApi.getSystemSettings).mockResolvedValueOnce(baseSettings);
    vi.mocked(adminApi.updateSystemSettings).mockResolvedValueOnce({
      timezone: 'Europe/London',
      date_format: 'day_month_year',
      time_format: '24_hour',
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect((screen.getByLabelText('Timezone') as HTMLSelectElement).value).toBe('UTC')
    );

    await user.selectOptions(screen.getByLabelText('Timezone'), 'Europe/London');
    await user.selectOptions(screen.getByLabelText('Date format'), 'day_month_year');
    await user.selectOptions(screen.getByLabelText('Time format'), '24_hour');

    await user.click(screen.getByRole('button', { name: 'Save settings' }));

    await waitFor(() =>
      expect(adminApi.updateSystemSettings).toHaveBeenCalledWith({
        timezone: 'Europe/London',
        date_format: 'day_month_year',
        time_format: '24_hour',
      })
    );

    await waitFor(() =>
      expect(screen.getByRole('status')).toBeTruthy()
    );

    expect(mockRefresh).toHaveBeenCalled();
  });

  it('shows error message when save fails', async () => {
    vi.mocked(adminApi.getSystemSettings).mockResolvedValueOnce(baseSettings);
    vi.mocked(adminApi.updateSystemSettings).mockRejectedValueOnce(new Error('Server error'));
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect((screen.getByLabelText('Timezone') as HTMLSelectElement).value).toBe('UTC')
    );

    await user.click(screen.getByRole('button', { name: 'Save settings' }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeTruthy()
    );
  });

  it('reset button restores context settings', async () => {
    vi.mocked(adminApi.getSystemSettings).mockResolvedValueOnce(baseSettings);
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect((screen.getByLabelText('Timezone') as HTMLSelectElement).value).toBe('UTC')
    );

    await user.selectOptions(screen.getByLabelText('Timezone'), 'Europe/London');
    expect((screen.getByLabelText('Timezone') as HTMLSelectElement).value).toBe('Europe/London');

    const resetBtn = screen.getByRole('button', { name: 'Reset' });
    expect((resetBtn as HTMLButtonElement).disabled).toBe(false);
    await user.click(resetBtn);

    expect((screen.getByLabelText('Timezone') as HTMLSelectElement).value).toBe('UTC');
  });

  it('shows a load error alert when getSystemSettings fails', async () => {
    vi.mocked(adminApi.getSystemSettings).mockRejectedValueOnce(new Error('network'));
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeTruthy()
    );
  });
});
