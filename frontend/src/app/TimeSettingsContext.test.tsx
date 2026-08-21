import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  TimeSettingsProvider,
  useTimeSettings,
  FALLBACK_SETTINGS,
  systemCalendarDate,
} from './TimeSettingsContext';

// Mock apiClient so the context never hits the network
vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
  extractErrorMessage: vi.fn((_err: unknown, fallback: string) => fallback),
}));

import { apiClient } from '@/api/client';

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

// ── Helper component that exposes context values via text content ──────────

function Probe() {
  const { settings, formatTimestamp, formatDate, formatWeekday } = useTimeSettings();
  return (
    <div>
      <span data-testid="tz">{settings.timezone}</span>
      <span data-testid="date_format">{settings.date_format}</span>
      <span data-testid="time_format">{settings.time_format}</span>
      <span data-testid="ts">{formatTimestamp('2025-07-04T14:30:00Z')}</span>
      <span data-testid="date">{formatDate('2025-07-04T14:30:00Z')}</span>
      <span data-testid="weekday">{formatWeekday('2025-07-04')}</span>
    </div>
  );
}

describe('TimeSettingsContext', () => {
  it('uses fallback settings while loading and updates when API resolves', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { timezone: 'America/New_York', date_format: 'day_month_year', time_format: '24_hour' },
    });

    render(
      <TimeSettingsProvider>
        <Probe />
      </TimeSettingsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('tz').textContent).toBe('America/New_York')
    );
    expect(screen.getByTestId('date_format').textContent).toBe('day_month_year');
    expect(screen.getByTestId('time_format').textContent).toBe('24_hour');
  });

  it('keeps fallback settings when the API call fails', async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('network error'));

    render(
      <TimeSettingsProvider>
        <Probe />
      </TimeSettingsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('tz').textContent).toBe(FALLBACK_SETTINGS.timezone)
    );
    expect(screen.getByTestId('date_format').textContent).toBe(FALLBACK_SETTINGS.date_format);
    expect(screen.getByTestId('time_format').textContent).toBe(FALLBACK_SETTINGS.time_format);
  });

  it('formatDate returns a date-only string in the configured order', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { timezone: 'UTC', date_format: 'day_month_year', time_format: '24_hour' },
    });

    render(
      <TimeSettingsProvider>
        <Probe />
      </TimeSettingsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('tz').textContent).toBe('UTC')
    );
    // day_month_year → DD/MM/YYYY → 04/07/2025
    expect(screen.getByTestId('date').textContent).toBe('04/07/2025');
  });

  it('formatDate returns YYYY/MM/DD for year_month_day format', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { timezone: 'UTC', date_format: 'year_month_day', time_format: '24_hour' },
    });

    render(
      <TimeSettingsProvider>
        <Probe />
      </TimeSettingsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('tz').textContent).toBe('UTC')
    );
    expect(screen.getByTestId('date').textContent).toBe('2025/07/04');
  });

  it('formatDate returns MM/DD/YYYY for month_day_year format', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { timezone: 'UTC', date_format: 'month_day_year', time_format: '12_hour' },
    });

    render(
      <TimeSettingsProvider>
        <Probe />
      </TimeSettingsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('tz').textContent).toBe('UTC')
    );
    expect(screen.getByTestId('date').textContent).toBe('07/04/2025');
  });

  it('formatWeekday returns a short weekday label', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { timezone: 'UTC', date_format: 'month_day_year', time_format: '12_hour' },
    });

    render(
      <TimeSettingsProvider>
        <Probe />
      </TimeSettingsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('tz').textContent).toBe('UTC')
    );
    // 2025-07-04 is a Friday
    expect(screen.getByTestId('weekday').textContent).toBe('Fri');
  });

  it('uses the configured calendar day rather than the browser UTC day', () => {
    const instant = new Date('2025-07-05T02:30:00Z');
    expect(systemCalendarDate(instant, 'America/New_York')).toBe('2025-07-04');
    expect(systemCalendarDate(instant, 'Asia/Tokyo')).toBe('2025-07-05');
  });

  it('throws when used outside the provider', () => {
    // Suppress React error boundary output for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow();
    consoleSpy.mockRestore();
  });
});
