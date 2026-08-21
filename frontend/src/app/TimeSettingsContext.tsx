/**
 * TimeSettingsContext — application-wide date/time formatting settings.
 * Fetches GET /system-settings once on mount and exposes stable formatting
 * helpers using the configured IANA timezone and format preferences.
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
import type { DateFormat, SystemSettings, TimeFormat } from '@/types';

// ── Types ──────────────────────────────────────────────────────────────────

export type { DateFormat, SystemSettings, TimeFormat } from '@/types';

export interface TimeSettingsContextValue {
  settings: SystemSettings;
  isLoading: boolean;
  error: string | null;
  /** Format an ISO timestamp string as a localized date + time. */
  formatTimestamp: (value: string) => string;
  /** Format an ISO timestamp or date string as a date-only string. */
  formatDate: (value: string) => string;
  /** Return the short weekday name for an ISO date string (e.g. "Mon"). */
  formatWeekday: (value: string) => string;
  /** Reload settings from the API. */
  refresh: () => Promise<void>;
}

// ── Fallback defaults ──────────────────────────────────────────────────────

export const FALLBACK_SETTINGS: SystemSettings = {
  timezone: 'UTC',
  date_format: 'month_day_year',
  time_format: '12_hour',
};

// ── Helpers ────────────────────────────────────────────────────────────────

function dateFormatToOrder(format: DateFormat): [string, string, string] {
  switch (format) {
    case 'month_day_year': return ['month', 'day', 'year'];
    case 'day_month_year': return ['day', 'month', 'year'];
    case 'year_month_day': return ['year', 'month', 'day'];
  }
}

/**
 * Format a date according to the configured order (M/D/Y, D/M/Y, or Y/M/D).
 */
function applyDateFormat(date: Date, format: DateFormat, timezone: string): string {
  const order = dateFormatToOrder(format);
  // Use Intl.DateTimeFormat with individual parts to assemble in custom order.
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);

  const map: Record<string, string> = {};
  for (const part of parts) {
    map[part.type] = part.value;
  }

  return order.map((key) => map[key] ?? '').join('/');
}

function applyDateOnlyFormat(value: string, format: DateFormat): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const [, year, month, day] = match;
  const map: Record<string, string> = { year, month, day };
  return dateFormatToOrder(format).map((key) => map[key]).join('/');
}

/** Return the calendar day for an instant in the configured system timezone. */
export function systemCalendarDate(value: Date, timezone: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(value);
  const values = Object.fromEntries(
    parts
      .filter((part) => ['year', 'month', 'day'].includes(part.type))
      .map((part) => [part.type, part.value])
  );
  return `${values.year}-${values.month}-${values.day}`;
}

/**
 * Format a date+time according to configured format settings.
 */
function applyDateTimeFormat(date: Date, settings: SystemSettings): string {
  const datePart = applyDateFormat(date, settings.date_format, settings.timezone);
  const timeParts = new Intl.DateTimeFormat('en-US', {
    timeZone: settings.timezone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: settings.time_format === '12_hour',
  }).formatToParts(date);

  const timeStr = timeParts
    .filter((p) => p.type !== 'literal' || p.value !== ', ')
    .map((p) => p.value)
    .join('');

  return `${datePart}, ${timeStr}`;
}

// ── Context ────────────────────────────────────────────────────────────────

const TimeSettingsContext = createContext<TimeSettingsContextValue | null>(null);

export function TimeSettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<SystemSettings>(FALLBACK_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<SystemSettings>('/system-settings');
      setSettings({
        timezone: data.timezone ?? FALLBACK_SETTINGS.timezone,
        date_format: data.date_format ?? FALLBACK_SETTINGS.date_format,
        time_format: data.time_format ?? FALLBACK_SETTINGS.time_format,
      });
    } catch {
      // Non-fatal: keep fallback settings
      setError('Unable to load system settings. Using defaults.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const formatTimestamp = useCallback(
    (value: string): string => {
      try {
        return applyDateTimeFormat(new Date(value), settings);
      } catch {
        return value;
      }
    },
    [settings],
  );

  const formatDate = useCallback(
    (value: string): string => {
      try {
        // A YYYY-MM-DD value is already a system-calendar date, not a UTC
        // instant. Preserve that date rather than shifting it for a viewer.
        const dateOnly = applyDateOnlyFormat(value, settings.date_format);
        if (dateOnly) return dateOnly;
        return applyDateFormat(new Date(value), settings.date_format, settings.timezone);
      } catch {
        return value;
      }
    },
    [settings],
  );

  const formatWeekday = useCallback(
    (value: string): string => {
      try {
        const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
        return new Intl.DateTimeFormat('en-US', {
          // Dashboard buckets are dates already computed in the system zone.
          // Format their weekday as a calendar date, without another shift.
          timeZone: dateOnly ? 'UTC' : settings.timezone,
          weekday: 'short',
        }).format(new Date(dateOnly ? `${value}T12:00:00Z` : value));
      } catch {
        return value;
      }
    },
    [settings],
  );

  const refresh = useCallback(async () => {
    await load();
  }, [load]);

  return (
    <TimeSettingsContext.Provider
      value={{ settings, isLoading, error, formatTimestamp, formatDate, formatWeekday, refresh }}
    >
      {children}
    </TimeSettingsContext.Provider>
  );
}

export function useTimeSettings(): TimeSettingsContextValue {
  const ctx = useContext(TimeSettingsContext);
  if (!ctx) {
    throw new Error('useTimeSettings must be used within a TimeSettingsProvider');
  }
  return ctx;
}
