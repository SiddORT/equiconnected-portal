import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getProviderInsights } from '@/api/providerInsights';
import type { ProviderInsights, ProviderInsightsPreset, ProviderInsightMetric } from '@/types/providerInsights';
import { AnalyticsChart } from '@/components/analytics/AnalyticsChart';
import { ProviderTopNav } from '@/components/layout/ProviderTopNav';
import styles from './ProviderInsightsPage.module.css';

type RequestParams = { preset: ProviderInsightsPreset; date_from?: string; date_to?: string };

function dateLabel(value: string) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function displayValue(metric: ProviderInsightMetric) {
  if (metric.value === null) return 'Not available';
  if (metric.coverage.status === 'partial') return `${metric.value.toLocaleString()}*`;
  return metric.value.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function comparisonExplanation(reason: string) {
  const explanations: Record<string, string> = {
    coverage_unknown: 'We don’t yet have confirmed collection coverage for this measure.',
    outside_collection_coverage: 'These dates are before collection began.',
    partial_coverage: 'A comparison isn’t shown because this period is only partly covered.',
    previous_period_not_fully_covered: 'A comparison will be available when the previous equal-length period is fully covered.',
    zero_previous_value: 'No percentage is shown because the previous period had no activity.',
  };
  return explanations[reason] ?? 'There isn’t enough covered history for a meaningful comparison.';
}

function errorStatus(error: unknown) {
  return (error as { response?: { status?: number } })?.response?.status;
}

function maxDays(from: string, to: string) {
  const start = Date.parse(`${from}T00:00:00Z`);
  const end = Date.parse(`${to}T00:00:00Z`);
  return Number.isFinite(start) && Number.isFinite(end) ? (end - start) / 86400000 + 1 : 0;
}

export function ProviderInsightsPage() {
  const [data, setData] = useState<ProviderInsights | null>(null);
  const [preset, setPreset] = useState<ProviderInsightsPreset>('last_30_days');
  const [request, setRequest] = useState<RequestParams>({ preset: 'last_30_days' });
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<{ kind: 'expired' | 'forbidden' | 'failure'; message: string } | null>(null);
  const [validation, setValidation] = useState('');
  const requestId = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(async (params: RequestParams) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const id = ++requestId.current;
    setBusy(true);
    setError(null);
    try {
      const result = await getProviderInsights(params, controller.signal);
      if (id !== requestId.current) return;
      setData(result);
      setFromDate((current) => current || result.period.date_from);
      setToDate((current) => current || result.period.date_to);
    } catch (err) {
      if (controller.signal.aborted || id !== requestId.current) return;
      const status = errorStatus(err);
      if (status === 401 || status === 403) setData(null);
      setError(status === 401
        ? { kind: 'expired', message: 'Your session has expired. Sign in again to view your engagement.' }
        : status === 403
          ? { kind: 'forbidden', message: 'Insights are not available for this provider account.' }
          : { kind: 'failure', message: 'We couldn’t load your insights just now. Your profile is unchanged.' });
    } finally {
      if (id === requestId.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load(request);
    return () => {
      requestId.current += 1;
      controllerRef.current?.abort();
    };
  }, [request, load]);

  function applyPeriod() {
    setValidation('');
    if (preset === 'custom') {
      if (!fromDate || !toDate || fromDate > toDate) {
        setValidation('Choose a start date on or before the end date.');
        return;
      }
      const today = data?.today;
      if (today && toDate > today) {
        setValidation(`Choose dates up to ${dateLabel(today)}. Future dates aren’t included.`);
        return;
      }
      if (maxDays(fromDate, toDate) > 366) {
        setValidation('Choose a range of 366 days or fewer.');
        return;
      }
      setRequest({ preset, date_from: fromDate, date_to: toDate });
      return;
    }
    setRequest({ preset });
  }

  function refresh() {
    void load(request);
  }

  const metricCards: Array<[string, ProviderInsightMetric]> = data ? [
    ['Profile visits', data.metrics.profile_views],
    ['Contact clicks', data.metrics.contact_clicks],
    ['New conversations', data.metrics.new_conversations],
  ] : [];
  const trendViews = data?.trends.map((point) => ({ bucket: point.date, value: point.profile_views })) ?? [];
  const trendContacts = data?.trends.map((point) => ({ bucket: point.date, value: point.contact_clicks })) ?? [];
  const coverageCount = data ? Object.values(data.metrics)
    .filter((metric) => metric.coverage.status !== 'full').length : 0;

  return (
    <div className={styles.page}>
      <ProviderTopNav />
      <main className={styles.shell}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Your practice · insights</p>
            <h1>{data?.provider_name ?? 'Your engagement'}</h1>
            <p className={styles.intro}>A clear view of how members find and connect with your practice. These numbers describe activity, not care outcomes.</p>
          </div>
        </header>

        <section className={styles.controls} aria-label="Insight date range">
          <label className={styles.control} htmlFor="insights-period">Show activity
            <select id="insights-period" value={preset} onChange={(event) => setPreset(event.target.value as ProviderInsightsPreset)}>
              <option value="last_7_days">Last 7 days</option>
              <option value="last_30_days">Last 30 days</option>
              <option value="this_month">This month</option>
              <option value="custom">Choose dates</option>
            </select>
          </label>
          {preset === 'custom' && <div className={styles.datePair}>
            <label className={styles.control} htmlFor="insights-from">From
              <input id="insights-from" type="date" value={fromDate} max={data?.today} onChange={(event) => setFromDate(event.target.value)} />
            </label>
            <label className={styles.control} htmlFor="insights-to">To
              <input id="insights-to" type="date" value={toDate} max={data?.today} onChange={(event) => setToDate(event.target.value)} />
            </label>
          </div>}
          <button type="button" className={styles.button} disabled={busy} onClick={applyPeriod}>Apply dates</button>
          <button type="button" className={styles.button} disabled={busy} onClick={refresh} aria-label="Refresh insights">Refresh</button>
          <span className={styles.refreshed}>{data ? `Updated ${new Date(data.refreshed_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: data.timezone })}` : ' '}</span>
        </section>
        {validation && <p className={styles.notice} role="alert">{validation}</p>}
        {error && <div className={`${styles.notice} ${styles.error}`} role="alert">
          {error.message} {error.kind === 'expired'
            ? <Link to="/provider/login">Sign in</Link>
            : error.kind === 'failure'
              ? <button className={styles.button} type="button" onClick={refresh}>Try again</button>
              : null}
        </div>}
        {busy && !data && <div className={styles.state} role="status">Loading your engagement…</div>}
        {!busy && !data && !error && <div className={styles.state}>No insight data is available yet. Check back after activity has been recorded.</div>}

        {data && <>
          {busy && <p className={styles.notice} role="status">Updating the selected period…</p>}
          {coverageCount > 0 && <p className={styles.notice}>Some measures have limited or unavailable source coverage. Each card explains what is known.</p>}
          <div className={styles.sectionTitle}>
            <h2>Activity in this period</h2>
            <p>{dateLabel(data.period.date_from)} – {dateLabel(data.period.date_to)} · {data.timezone}</p>
          </div>
          <section className={styles.metrics} aria-label="Engagement metrics">
            {metricCards.map(([label, metric]) => (
              <article className={styles.metric} key={label}>
                <div className={styles.metricLabel}>{label}</div>
                <div className={styles.value}>{displayValue(metric)}</div>
                <p className={styles.definition}>{metric.definition}</p>
                <span className={styles.coverage} data-status={metric.coverage.status}>
                  {metric.coverage.status === 'full' ? 'Coverage complete' : metric.coverage.status === 'partial' ? 'Partial coverage' : metric.coverage.status === 'unavailable' ? 'Unavailable' : 'Coverage not confirmed'}
                </span>
                {metric.coverage.note && <p className={styles.comparison}>{metric.coverage.note}</p>}
                {metric.comparison.change_percent !== null
                  ? <p className={styles.comparison}>{metric.comparison.change_percent > 0 ? '+' : ''}{metric.comparison.change_percent}% compared with {metric.comparison.previous_value?.toLocaleString()} previously</p>
                  : metric.comparison.reason && <p className={styles.comparison}>{comparisonExplanation(metric.comparison.reason)}</p>}
              </article>
            ))}
          </section>

          <div className={styles.sectionTitle}><h2>Activity over time</h2><p>Daily totals in your selected period</p></div>
          <section className={styles.charts} aria-label="Engagement trends">
            <AnalyticsChart title="Profile visits" description="Successfully loaded member profile pages." kind="trend" points={trendViews} unit="visits" definition="Revisits count again. This is not a unique-person count or an appointment." />
            <AnalyticsChart title="Contact clicks" description="Clicks on a listed phone, email, or website link." kind="trend" points={trendContacts} unit="clicks" definition="A click does not confirm that a call, email, booking, or other outcome happened." />
          </section>
          <div className={styles.sectionTitle}><h2>How members reached out</h2><p>Contact-link activations for this period</p></div>
          <section className={styles.breakdown} aria-label="Contact activation breakdown">
            <h3>Contact options</h3>
            {(['phone', 'email', 'website'] as const).map((key) => {
              const item = data.contact_breakdown[key];
              const max = Math.max(...Object.values(data.contact_breakdown).flatMap((value) => value === null ? [] : [value]), 1);
              return <div className={styles.breakRow} key={key}>
                <span>{key[0].toUpperCase() + key.slice(1)}</span>
                <span className={styles.track} aria-hidden="true"><i style={{ width: `${item === null ? 0 : item / max * 100}%` }} /></span>
                <strong>{item === null ? 'Not available' : item.toLocaleString()}</strong>
              </div>;
            })}
          </section>

          <div className={styles.sectionTitle}>
            <h2>Current snapshot</h2>
            <p>Live profile totals · independent of the date range</p>
          </div>
          <section className={styles.snapshot} aria-label="Current snapshot">
            <div className={styles.snapshotGrid}>
              {([
                ['Members who saved you', data.snapshot.saved_members],
                ['Ratings received', data.snapshot.rating_count],
                ['Visible written reviews', data.snapshot.visible_review_count],
                ['Average rating', data.snapshot.average_rating],
              ] as Array<[string, number | null]>).map(([label, value]) => (
                <div className={styles.snapshotItem} key={label}>
                  <span>{label}</span><strong>{value === null ? 'Not available' : value.toLocaleString(undefined, { maximumFractionDigits: 2 })}{label === 'Average rating' && value !== null ? ' / 5' : ''}</strong>
                  <small>{label === 'Visible written reviews' ? 'Member-visible comments' : 'Current profile total'}</small>
                </div>
              ))}
            </div>
          </section>
        </>}
      </main>
    </div>
  );
}