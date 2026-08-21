/**
 * Admin Settings page — /admin/settings
 * Configure system-wide timezone, date format, and time format.
 */
import { useEffect, useId, useState } from 'react';
import { getSystemSettings, updateSystemSettings } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { PageHeader } from '@/components/layout/PageHeader';
import { Select } from '@/components/ui/Select';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import type { DateFormat, SystemSettings, TimeFormat } from '@/types';
import styles from './SettingsPage.module.css';

// ── Timezone options — common IANA zones ───────────────────────────────────

const TIMEZONE_OPTIONS = [
  { value: 'UTC', label: 'UTC — Coordinated Universal Time' },
  { value: 'America/New_York', label: 'America/New_York — Eastern Time' },
  { value: 'America/Chicago', label: 'America/Chicago — Central Time' },
  { value: 'America/Denver', label: 'America/Denver — Mountain Time' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles — Pacific Time' },
  { value: 'America/Anchorage', label: 'America/Anchorage — Alaska Time' },
  { value: 'Pacific/Honolulu', label: 'Pacific/Honolulu — Hawaii Time' },
  { value: 'America/Toronto', label: 'America/Toronto — Eastern Time (Canada)' },
  { value: 'America/Vancouver', label: 'America/Vancouver — Pacific Time (Canada)' },
  { value: 'America/Sao_Paulo', label: 'America/Sao_Paulo — Brazil Time' },
  { value: 'America/Argentina/Buenos_Aires', label: 'America/Argentina/Buenos_Aires' },
  { value: 'Europe/London', label: 'Europe/London — GMT/BST' },
  { value: 'Europe/Paris', label: 'Europe/Paris — Central European Time' },
  { value: 'Europe/Berlin', label: 'Europe/Berlin — Central European Time' },
  { value: 'Europe/Amsterdam', label: 'Europe/Amsterdam — Central European Time' },
  { value: 'Europe/Rome', label: 'Europe/Rome — Central European Time' },
  { value: 'Europe/Madrid', label: 'Europe/Madrid — Central European Time' },
  { value: 'Europe/Stockholm', label: 'Europe/Stockholm — Central European Time' },
  { value: 'Europe/Helsinki', label: 'Europe/Helsinki — Eastern European Time' },
  { value: 'Europe/Moscow', label: 'Europe/Moscow — Moscow Time' },
  { value: 'Africa/Johannesburg', label: 'Africa/Johannesburg — SAST' },
  { value: 'Africa/Lagos', label: 'Africa/Lagos — West Africa Time' },
  { value: 'Africa/Nairobi', label: 'Africa/Nairobi — East Africa Time' },
  { value: 'Asia/Dubai', label: 'Asia/Dubai — Gulf Standard Time' },
  { value: 'Asia/Kolkata', label: 'Asia/Kolkata — India Standard Time' },
  { value: 'Asia/Dhaka', label: 'Asia/Dhaka — Bangladesh Standard Time' },
  { value: 'Asia/Bangkok', label: 'Asia/Bangkok — Indochina Time' },
  { value: 'Asia/Singapore', label: 'Asia/Singapore — Singapore Time' },
  { value: 'Asia/Shanghai', label: 'Asia/Shanghai — China Standard Time' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo — Japan Standard Time' },
  { value: 'Asia/Seoul', label: 'Asia/Seoul — Korea Standard Time' },
  { value: 'Australia/Sydney', label: 'Australia/Sydney — AEST/AEDT' },
  { value: 'Australia/Melbourne', label: 'Australia/Melbourne — AEST/AEDT' },
  { value: 'Australia/Perth', label: 'Australia/Perth — AWST' },
  { value: 'Pacific/Auckland', label: 'Pacific/Auckland — New Zealand Time' },
];

const DATE_FORMAT_OPTIONS: { value: DateFormat; label: string }[] = [
  { value: 'month_day_year', label: 'MM/DD/YYYY (e.g. 01/31/2025)' },
  { value: 'day_month_year', label: 'DD/MM/YYYY (e.g. 31/01/2025)' },
  { value: 'year_month_day', label: 'YYYY/MM/DD (e.g. 2025/01/31)' },
];

const TIME_FORMAT_OPTIONS: { value: TimeFormat; label: string }[] = [
  { value: '12_hour', label: '12-hour (e.g. 02:30 PM)' },
  { value: '24_hour', label: '24-hour (e.g. 14:30)' },
];

// ── Preview helpers ────────────────────────────────────────────────────────

const PREVIEW_ISO = '2025-07-04T14:30:00Z';

function dateFormatToOrder(format: DateFormat): string[] {
  switch (format) {
    case 'month_day_year': return ['month', 'day', 'year'];
    case 'day_month_year': return ['day', 'month', 'year'];
    case 'year_month_day': return ['year', 'month', 'day'];
  }
}

function buildPreviewDate(format: DateFormat, timezone: string): string {
  try {
    const date = new Date(PREVIEW_ISO);
    const order = dateFormatToOrder(format);
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(date);
    const map: Record<string, string> = {};
    for (const part of parts) map[part.type] = part.value;
    return order.map((k) => map[k] ?? '').join('/');
  } catch {
    return '—';
  }
}

function buildPreviewTime(timeFormat: TimeFormat, timezone: string): string {
  try {
    const date = new Date(PREVIEW_ISO);
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: timeFormat === '12_hour',
    }).formatToParts(date);
    return parts.map((p) => p.value).join('');
  } catch {
    return '—';
  }
}

function buildPreviewWeekday(timezone: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      weekday: 'short',
    }).format(new Date(PREVIEW_ISO));
  } catch {
    return '—';
  }
}

// ── Component ──────────────────────────────────────────────────────────────

type SaveState = 'idle' | 'loading' | 'success' | 'error';

export function SettingsPage() {
  const { settings: liveSettings, refresh } = useTimeSettings();
  const formId = useId();

  const [timezone, setTimezone] = useState<string>(liveSettings.timezone);
  const [dateFormat, setDateFormat] = useState<DateFormat>(liveSettings.date_format);
  const [timeFormat, setTimeFormat] = useState<TimeFormat>(liveSettings.time_format);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pageLoading, setPageLoading] = useState(true);

  // Load latest from API on mount (independent of context, so the page always
  // has fresh server-side values even if the context already resolved earlier).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setPageLoading(true);
      setLoadError(null);
      try {
        const current = await getSystemSettings();
        if (!cancelled) {
          setTimezone(current.timezone);
          setDateFormat(current.date_format);
          setTimeFormat(current.time_format);
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(extractErrorMessage(err, 'Unable to load current settings.'));
          // Fall back to what the context already loaded.
          setTimezone(liveSettings.timezone);
          setDateFormat(liveSettings.date_format);
          setTimeFormat(liveSettings.time_format);
        }
      } finally {
        if (!cancelled) setPageLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isDirty =
    timezone !== liveSettings.timezone ||
    dateFormat !== liveSettings.date_format ||
    timeFormat !== liveSettings.time_format;

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setSaveState('loading');
    setSaveError(null);
    try {
      const saved = await updateSystemSettings({ timezone, date_format: dateFormat, time_format: timeFormat });
      setTimezone(saved.timezone);
      setDateFormat(saved.date_format);
      setTimeFormat(saved.time_format);
      setSaveState('success');
      await refresh();
      setTimeout(() => setSaveState('idle'), 3000);
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Settings could not be saved. Please try again.'));
      setSaveState('error');
    }
  }

  function handleReset() {
    setTimezone(liveSettings.timezone);
    setDateFormat(liveSettings.date_format);
    setTimeFormat(liveSettings.time_format);
    setSaveState('idle');
    setSaveError(null);
  }

  // Live preview values derived from draft form state.
  const previewDate = buildPreviewDate(dateFormat, timezone);
  const previewTime = buildPreviewTime(timeFormat, timezone);
  const previewWeekday = buildPreviewWeekday(timezone);

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Settings"
        subtitle="Configure system-wide time and display preferences."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Settings' }]}
      />

      <div className={styles.body}>
        {loadError && <Alert variant="error">{loadError}</Alert>}

        {pageLoading ? (
          <p aria-live="polite">Loading settings…</p>
        ) : (
          <form id={formId} onSubmit={(e) => void handleSave(e)}>
            <div className={styles.formCard}>
              <h2 className={styles.formTitle}>Time &amp; date configuration</h2>

              <div className={styles.fieldGroup}>
                <Select
                  label="Timezone"
                  value={timezone}
                  options={TIMEZONE_OPTIONS}
                  onChange={(e) => setTimezone(e.target.value)}
                  aria-label="Timezone"
                  disabled={saveState === 'loading'}
                />

                <Select
                  label="Date format"
                  value={dateFormat}
                  options={DATE_FORMAT_OPTIONS}
                  onChange={(e) => setDateFormat(e.target.value as DateFormat)}
                  aria-label="Date format"
                  disabled={saveState === 'loading'}
                />

                <Select
                  label="Time format"
                  value={timeFormat}
                  options={TIME_FORMAT_OPTIONS}
                  onChange={(e) => setTimeFormat(e.target.value as TimeFormat)}
                  aria-label="Time format"
                  disabled={saveState === 'loading'}
                />
              </div>

              {/* Live preview */}
              <div className={styles.previewPanel} aria-live="polite" aria-label="Format preview">
                <p className={styles.previewTitle}>Preview — July 4 2025, 2:30 PM UTC</p>
                <dl className={styles.previewGrid}>
                  <dt className={styles.previewLabel}>Date</dt>
                  <dd className={styles.previewValue}>{previewDate}</dd>
                  <dt className={styles.previewLabel}>Time</dt>
                  <dd className={styles.previewValue}>{previewTime}</dd>
                  <dt className={styles.previewLabel}>Weekday</dt>
                  <dd className={styles.previewValue}>{previewWeekday}</dd>
                  <dt className={styles.previewLabel}>Full timestamp</dt>
                  <dd className={styles.previewValue}>{previewDate}, {previewTime}</dd>
                </dl>
              </div>

              {saveState === 'error' && saveError && (
                <Alert variant="error">{saveError}</Alert>
              )}

              <div className={styles.formFooter}>
                <Button
                  type="submit"
                  variant="primary"
                  loading={saveState === 'loading'}
                  disabled={saveState === 'loading'}
                >
                  Save settings
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  disabled={saveState === 'loading' || !isDirty}
                  onClick={handleReset}
                >
                  Reset
                </Button>

                <div className={styles.spacer} />

                {saveState === 'success' && (
                  <span
                    className={`${styles.feedback} ${styles['feedback--success']}`}
                    role="status"
                    aria-live="polite"
                  >
                    ✓ Settings saved
                  </span>
                )}
                {saveState === 'loading' && (
                  <span
                    className={`${styles.feedback} ${styles['feedback--loading']}`}
                    role="status"
                    aria-live="polite"
                  >
                    Saving…
                  </span>
                )}
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
