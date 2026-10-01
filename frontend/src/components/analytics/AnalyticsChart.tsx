import { useMemo } from 'react';
import type { AnalyticsGroup, AnalyticsPoint } from '@/types/analytics';
import { Card } from '@/components/ui/Card';
import styles from './AnalyticsChart.module.css';

export interface ChartDatum { label: string; value: number | null }

function entriesOf(group: AnalyticsGroup | undefined): ChartDatum[] {
  if (!group) return [];
  const rows: Array<Record<string, unknown>> = Array.isArray(group)
    ? group
    : Object.entries(group).map(([label, value]) => typeof value === 'object' && value !== null
      ? { label, ...(value as Record<string, unknown>) }
      : { label, value });
  return rows.map((row, index) => {
    const label = String(row.label ?? row.bucket ?? row.name ?? row.provider_name ?? row.status ?? row.category ?? row.rating ?? row.type ?? row.role ?? `Item ${index + 1}`);
    const raw = row.value ?? row.count ?? row.total ?? row.views ?? row.submissions ?? row.review_submissions ?? row.rating_count ?? row.profile_views;
    if (raw === null || raw === undefined || raw === '') return { label, value: null };
    const parsed = typeof raw === 'number' ? raw : Number(raw);
    return { label, value: Number.isFinite(parsed) ? parsed : null };
  });
}

interface Props {
  title: string;
  description?: string;
  kind?: 'trend' | 'bars' | 'columns';
  points?: AnalyticsPoint[] | null;
  group?: AnalyticsGroup;
  unit?: string;
  definition?: string;
  tableOpen?: boolean;
}

function bucketTimestamp(bucket: string): number | null {
  const week = bucket.match(/^(\d{4})-W(\d{2})$/);
  if (week) {
    const first = new Date(Date.UTC(Number(week[1]), 0, 4));
    const weekday = first.getUTCDay() || 7;
    first.setUTCDate(first.getUTCDate() - weekday + 1 + (Number(week[2]) - 1) * 7);
    return first.getTime();
  }
  const timestamp = Date.parse(bucket);
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function AnalyticsChart({ title, description, kind = 'bars', points, group, unit = 'records', definition, tableOpen = true }: Props) {
  const data = useMemo(() => points
    ? points.map((point) => ({ label: point.bucket, value: point.value }))
    : entriesOf(group), [points, group]);
  const max = Math.max(...data.flatMap((d) => d.value === null ? [] : [d.value]), 1);
  const chartLabel = `${title}. ${data.map((d) => `${d.label}: ${d.value === null ? 'unavailable' : `${d.value} ${unit}`}`).join('; ') || 'No data available'}`;
  const times = data.map(({ label }) => bucketTimestamp(label));
  const temporal = kind === 'trend' && times.length > 1 && times.every((time) => time !== null)
    && Math.max(...times as number[]) > Math.min(...times as number[]);
  const firstTime = temporal ? Math.min(...times as number[]) : 0;
  const lastTime = temporal ? Math.max(...times as number[]) : 0;
  const xForIndex = (index: number) => {
    if (temporal) return 58 + (((times[index] ?? firstTime) - firstTime) / (lastTime - firstTime)) * 632;
    return data.length === 1 ? 374 : 58 + (index / (data.length - 1)) * 632;
  };
  const rawStep = max / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalizedStep = rawStep / magnitude;
  const tickStep = (normalizedStep <= 1 ? 1 : normalizedStep <= 2 ? 2 : normalizedStep <= 5 ? 5 : 10) * magnitude;
  const tickMax = Math.ceil(max / tickStep) * tickStep;
  const yTicks = Array.from({ length: Math.round(tickMax / tickStep) + 1 }, (_, index) => index * tickStep);
  const yForValue = (value: number) => 180 - (value / tickMax) * 150;

  return (
    <Card padding="md" shadow="sm" className={styles.card}>
      <header className={styles.heading}>
        <div><h3>{title}</h3>{description && <p>{description}</p>}{definition && <p className={styles.definition}>{definition}</p>}</div>
        {data.length > 0 && <span className={styles.unit}>{unit}</span>}
      </header>
      {data.length === 0 ? (
        <div className={styles.empty} role="status">No covered data for this selection.</div>
      ) : (
        <>
          <div className={`${styles.chart} ${kind === 'trend' ? styles.trend : ''}`} role="img" aria-label={chartLabel}>
            {kind === 'trend' ? (
              <svg viewBox="0 0 700 220" preserveAspectRatio="none" aria-hidden="true">
                {yTicks.map((tick, i) => {
                  const y = 180 - (tick / tickMax) * 150;
                  return <g key={tick}><line x1="56" y1={y} x2="692" y2={y} className={styles.gridLine} /><text x="48" y={y + 3} textAnchor="end" className={styles.tick}>{tick.toLocaleString()}</text></g>;
                })}
                {data.reduce<Array<Array<string>>>((segments, item, i) => {
                  if (item.value === null) {
                    if (segments[segments.length - 1]?.length) segments.push([]);
                    return segments;
                  }
                  const x = xForIndex(i);
                  const y = yForValue(item.value);
                  if (!segments.length) segments.push([]);
                  segments[segments.length - 1].push(`${x},${y}`);
                  return segments;
                }, []).filter((segment) => segment.length > 1).map((segment, i) => <polyline key={i} className={styles.line} points={segment.join(' ')} />)}
                {data.map((item, i) => {
                  if (item.value === null) return null;
                  const x = xForIndex(i);
                  const y = yForValue(item.value);
                  return <circle key={`${item.label}-${i}`} cx={x} cy={y} r="3.5" className={styles.dot}><title>{item.label}: {item.value} {unit}</title></circle>;
                })}
              </svg>
            ) : kind === 'columns' ? (
              <div className={styles.columns}>
                {data.map((item) => (
                  <div className={styles.columnItem} key={item.label} title={`${item.label}: ${item.value}`}>
                    <strong>{item.value ?? '—'}</strong>
                    <span className={styles.columnTrack}><i style={{ height: `${item.value === null || item.value === 0 ? 0 : Math.max(4, item.value / max * 100)}%` }} /></span>
                    <span className={styles.columnLabel}>{item.label}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.bars}>
                {data.map((item) => (
                  <div className={styles.barItem} key={item.label}>
                    <span className={styles.barLabel} title={item.label}>{item.label}</span>
                    <span className={styles.barTrack}><i style={{ width: `${item.value === null || item.value === 0 ? 0 : Math.max(1, item.value / max * 100)}%` }} /></span>
                    <strong>{item.value ?? '—'}</strong>
                  </div>
                ))}
              </div>
            )}
          </div>
          {kind === 'trend' && data.length > 1 && (
            <div className={styles.endpoints}><span>{data[0].label}</span><span>{data[data.length - 1].label}</span></div>
          )}
          <details className={styles.tableDetails} open={tableOpen}>
            <summary>View data table</summary>
            <div className={styles.tableWrap}>
              <table><caption className="sr-only">{title} data</caption><thead><tr><th scope="col">Period / category</th><th scope="col">{unit}</th></tr></thead>
                <tbody>{data.map((item) => <tr key={item.label}><th scope="row">{item.label}</th><td>{item.value === null ? 'Unavailable' : item.value.toLocaleString()}</td></tr>)}</tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </Card>
  );
}