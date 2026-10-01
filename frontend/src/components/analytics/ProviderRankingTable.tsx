import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { AnalyticsSort, ProviderRankingResponse } from '@/types/analytics';
import { Pagination } from '@/components/ui/Pagination';
import styles from './ProviderRankingTable.module.css';

interface Props {
  report: ProviderRankingResponse | null;
  loading: boolean;
  search: string;
  onSearch: (value: string) => void;
  sortBy: AnalyticsSort;
  sortDirection: 'asc' | 'desc';
  onSort: (key: AnalyticsSort) => void;
  page: number;
  pageSize: number;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}

const primarySortable: Array<[AnalyticsSort, string]> = [
  ['name', 'Provider'], ['profile_views', 'Period profile views'],
  ['review_submissions', 'Period review submissions'], ['average_rating', 'Current average'],
];
const secondarySortable: Array<[AnalyticsSort, string]> = [
  ['rating_count', 'Eligible rating count'], ['saved_count', 'Current saves'],
];

export function ProviderRankingTable(props: Props) {
  const [showSecondarySort, setShowSecondarySort] = useState(false);
  const [openProviderDetails, setOpenProviderDetails] = useState<Record<string, boolean>>({});
  const { report, loading, search, onSearch, sortBy, sortDirection, onSort, page, pageSize, onPage, onPageSize } = props;
  const rows = report?.data ?? [];
  const total = report?.meta.total ?? 0;
  return (
    <section className={styles.wrap} aria-labelledby="provider-ranking-title">
      <header className={styles.header}>
        <div><h3 id="provider-ranking-title">Provider popularity</h3><p>Period activity and current directory snapshots are labelled separately.</p></div>
        <label className={styles.search}>Search providers<input value={search} maxLength={100} onChange={(event) => onSearch(event.target.value)} placeholder="Name contains…" /></label>
      </header>
      <details className={styles.secondarySort} open={showSecondarySort}>
        <summary onClick={(event) => { event.preventDefault(); setShowSecondarySort((open) => !open); }}>Additional sort options{secondarySortable.some(([key]) => key === sortBy) ? ` · Sorted by ${secondarySortable.find(([key]) => key === sortBy)?.[1]} (${sortDirection === 'asc' ? 'ascending' : 'descending'})` : ''}</summary>
        {showSecondarySort && <div className={styles.sortOptions}>
          {secondarySortable.map(([key, label]) => <button type="button" key={key} onClick={() => onSort(key)} aria-pressed={sortBy === key}>{label}{sortBy === key ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : ''}</button>)}
        </div>}
      </details>
      <div className={styles.scroll}>
        <table>
          <caption className="sr-only">Provider ranking: period profile views, period review submissions, and current average rating</caption>
          <thead><tr>{primarySortable.map(([key, label]) => (
            <th scope="col" key={key} aria-sort={sortBy === key ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}><button type="button" onClick={() => onSort(key)} aria-label={`Sort by ${label}`}>{label}{sortBy === key ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : ' ↕'}</button></th>
          ))}</tr></thead>
          <tbody>
            {loading && Array.from({ length: 4 }, (_, i) => <tr key={`loading-${i}`} className={styles.skeleton}><td colSpan={4}><span /></td></tr>)}
            {!loading && rows.map((row) => (
              <tr key={row.provider_id}>
                <th scope="row"><Link to={`/admin/providers/${row.provider_id}`}>{row.name}</Link>
                  <details className={styles.rowDetails} open={!!openProviderDetails[row.provider_id]}>
                    <summary onClick={(event) => { event.preventDefault(); setOpenProviderDetails((current) => ({ ...current, [row.provider_id]: !current[row.provider_id] })); }}>Provider details</summary>
                    {openProviderDetails[row.provider_id] && <>
                    <dl><div><dt>Listing</dt><dd>{row.provider_type} · {row.provider_status}</dd></div><div><dt>Publication</dt><dd>{row.publication_status}</dd></div>
                      <div><dt>Eligible ratings</dt><dd>{row.rating_count.toLocaleString()}</dd></div><div><dt>Current saves</dt><dd>{row.saved_count.toLocaleString()}</dd></div></dl>
                    <Link to={`/admin/reviews?provider_id=${encodeURIComponent(row.provider_id)}`}>View reviews</Link>
                    </>}
                  </details>
                </th>
                <td>{row.profile_views_available === false || row.profile_views === null ? 'Unavailable' : row.profile_views.toLocaleString()}</td>
                <td>{row.review_submissions.toLocaleString()}</td>
                <td>{row.average_rating === null ? '—' : <strong>{row.average_rating.toFixed(1)} / 5</strong>}<span className={styles.eligibleCount}>{row.rating_count.toLocaleString()} eligible</span></td>
              </tr>
            ))}
            {!loading && rows.length === 0 && <tr><td className={styles.empty} colSpan={4}>No providers match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={pageSize} total={total} onPageChange={onPage} onPageSizeChange={onPageSize} />
    </section>
  );
}