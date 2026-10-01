import type { AnalyticsBreakdowns } from '@/types/analytics';
import styles from './AnalyticsBreakdownTables.module.css';

interface AggregateRow {
  category: string;
  value: number;
}

const NON_COUNT_NUMBERS = new Set([
  'rating', 'average', 'average_rating', 'average_optional_rating', 'optional_rating_average',
  'percent', 'change_percent', 'page', 'page_size', 'total_pages', 'latitude', 'longitude',
]);
const COUNT_FIELDS = [
  'value', 'count', 'total', 'views', 'page_views', 'review_submissions', 'rating_count',
  'profile_views', 'saved_count', 'submissions', 'records', 'response_count',
];
const LABEL_FIELDS = ['label', 'name', 'provider_name', 'status', 'category', 'type', 'role', 'bucket', 'rating'];

function flattenAggregates(value: unknown, path = ''): AggregateRow[] {
  if (typeof value === 'number' && Number.isFinite(value)) return [{ category: path || 'Total', value }];
  if (Array.isArray(value)) return value.flatMap((row, index) => {
    if (!row || typeof row !== 'object') return [];
    const item = row as Record<string, unknown>;
    const valueField = COUNT_FIELDS.find((field) => typeof item[field] === 'number');
    if (valueField) {
      const label = LABEL_FIELDS.map((field) => item[field]).find((field) => field !== undefined && field !== null);
      return [{ category: [path, label === undefined ? `Item ${index + 1}` : String(label)].filter(Boolean).join(' · '), value: item[valueField] as number }];
    }
    return flattenAggregates(item, path);
  });
  if (value && typeof value === 'object') return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) => {
    if (NON_COUNT_NUMBERS.has(key.toLowerCase()) || key === 'definition' || key === 'unit' || key === 'available') return [];
    const nextPath = [path, key].filter(Boolean).join(' · ');
    if (typeof nested === 'number' && Number.isFinite(nested)) return [{ category: nextPath, value: nested }];
    return flattenAggregates(nested, nextPath);
  });
  return [];
}

function basisFor(domain: string, name: string): string {
  const key = `${domain}.${name}`.toLowerCase();
  if (key.includes('top_reviewed')) return 'Current eligible ratings snapshot';
  if (key.includes('star_distribution')) return 'Current eligible rating snapshot';
  if (key.includes('cohort')) return 'Selected-period cohort · current state';
  if (domain === 'feedback' && key.endsWith('.ratings')) return 'Selected period · non-withdrawn feedback';
  if (key.includes('period') || key.includes('submission') || key.includes('action') || key.includes('enquiry_type') || key.includes('subscriber_type') || key.includes('category')) return 'Selected period';
  if (key.includes('current') || key.includes('inventory') || key.includes('status') || key.includes('star_distribution') || key.includes('rating')) return 'Current snapshot';
  return 'Aggregate report';
}

function definitionFor(domain: string, name: string, supplied?: string): string {
  if (supplied) return supplied;
  const key = `${domain}.${name}`.toLowerCase();
  if (key.includes('top_reviewed')) return 'Current count of eligible provider ratings from undeleted published or hidden reviews; pending and rejected reviews are excluded.';
  if (key.includes('selected_period_submission')) return 'Initial provider-review submissions created during the selected period. Edits and moderation actions are not submissions.';
  if (key.includes('period_actions') || key.includes('review_actions')) return 'Edits and moderation actions recorded in the selected period; these are distinct from new review submissions.';
  if (key.includes('star_distribution')) return 'Current eligible published/hidden provider ratings by star value. Hidden approved ratings remain eligible; pending and rejected reviews do not.';
  if (key.includes('current_status') && domain === 'reviews') return 'Current moderation state of active, undeleted reviews. Retained deleted history is reported separately.';
  if (key.includes('current_backlog') || (key.includes('current_status') && domain === 'feedback')) return 'Current private feedback backlog. Withdrawn feedback is separate and is not counted in active states.';
  if (key.includes('selected_cohort')) return 'Current verification/account state of the member cohort registered during the selected period. Dual-role members count once.';
  if (key.includes('current_inventory')) return 'Current provider inventory snapshot, not a historical population. Active-published means active and publicly published.';
  if (key.includes('categories') && domain === 'feedback') return 'Private feedback submissions grouped by category in the selected period; message content is not included.';
  return `Aggregate count for ${name.replace(/_/g, ' ')}.`;
}

export function AnalyticsBreakdownTables({ reports }: { reports: AnalyticsBreakdowns[] }) {
  const groups = reports.flatMap((report) => Object.entries(report.groups ?? {}).map(([name, value]) => ({
    key: `${report.domain}-${name}`,
    domain: report.domain,
    name,
    rows: flattenAggregates(value),
    definition: definitionFor(report.domain, name, report.definitions?.[name]),
  }))).filter((group) => group.rows.length > 0);

  if (groups.length === 0) return null;
  return (
    <section className={styles.section} aria-labelledby="aggregate-tables-heading">
      <header><div><span className={styles.kicker}>Source-aligned detail</span><h2 id="aggregate-tables-heading">Breakdown tables</h2></div><p>Count-only aggregates. Period activity and present-day snapshots remain distinct.</p></header>
      <div className={styles.groups}>
        {groups.map((group) => (
          <details key={group.key} open>
            <summary><span>{group.domain.replace(/_/g, ' ')} · {group.name.replace(/_/g, ' ')}</span><small>{basisFor(group.domain, group.name)}</small></summary>
            <p className={styles.definition}>{group.definition}</p>
            <div className={styles.tableWrap}>
              <table><caption className="sr-only">{group.domain} {group.name} aggregate values</caption>
                <thead><tr><th scope="col">Category / status</th><th scope="col">Count</th><th scope="col">Basis</th></tr></thead>
                <tbody>{group.rows.map((row, index) => <tr key={`${row.category}-${index}`}><th scope="row">{row.category}</th><td>{row.value.toLocaleString()}</td><td>{basisFor(group.domain, group.name)}</td></tr>)}</tbody>
              </table>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}