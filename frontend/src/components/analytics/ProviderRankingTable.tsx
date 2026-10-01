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

const sortable: Array<[AnalyticsSort, string]> = [
  ['name', 'Provider'], ['profile_views', 'Period profile views'],
  ['review_submissions', 'Period reviews'], ['average_rating', 'Current average'],
  ['rating_count', 'Current rating count'], ['saved_count', 'Current saves'],
];

export function ProviderRankingTable(props: Props) {
  const { report, loading, search, onSearch, sortBy, sortDirection, onSort, page, pageSize, onPage, onPageSize } = props;
  const rows = report?.data ?? [];
  const total = report?.meta.total ?? 0;
  return (
    <section className={styles.wrap} aria-labelledby="provider-ranking-title">
      <header className={styles.header}>
        <div><h3 id="provider-ranking-title">Provider popularity</h3><p>Period activity and current directory snapshots are labelled separately.</p></div>
        <label className={styles.search}>Search providers<input value={search} maxLength={100} onChange={(event) => onSearch(event.target.value)} placeholder="Name contains…" /></label>
      </header>
      <div className={styles.scroll}>
        <table>
          <caption className="sr-only">Provider ranking by views with period activity and current snapshot fields</caption>
          <thead><tr><th scope="col">Sr. No.</th>{sortable.map(([key, label]) => (
            <th scope="col" key={key} aria-sort={sortBy === key ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}><button type="button" onClick={() => onSort(key)} aria-label={`Sort by ${label}`}>{label}{sortBy === key ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : ' ↕'}</button></th>
          ))}<th scope="col">Type / status</th><th scope="col">Publication</th><th scope="col">Links</th></tr></thead>
          <tbody>
            {loading && Array.from({ length: 4 }, (_, i) => <tr key={`loading-${i}`} className={styles.skeleton}><td colSpan={10}><span /></td></tr>)}
            {!loading && rows.map((row, index) => (
              <tr key={row.provider_id}>
                <td>{(page - 1) * pageSize + index + 1}</td>
                <th scope="row"><Link to={`/admin/providers/${row.provider_id}`}>{row.name}</Link></th>
                <td>{row.profile_views_available === false || row.profile_views === null ? 'Unavailable' : row.profile_views.toLocaleString()}</td>
                <td>{row.review_submissions.toLocaleString()}</td>
                <td>{row.average_rating === null ? '—' : `${row.average_rating.toFixed(1)} / 5`}</td>
                <td>{row.rating_count.toLocaleString()}</td><td>{row.saved_count.toLocaleString()}</td>
                <td>{row.provider_type} · {row.provider_status}</td><td>{row.publication_status}</td>
                <td><Link to={`/admin/providers/${row.provider_id}`}>Provider</Link><span aria-hidden="true"> · </span><Link to={`/admin/reviews?provider_id=${encodeURIComponent(row.provider_id)}`}>Reviews</Link></td>
              </tr>
            ))}
            {!loading && rows.length === 0 && <tr><td className={styles.empty} colSpan={10}>No providers match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={pageSize} total={total} onPageChange={onPage} onPageSizeChange={onPageSize} />
    </section>
  );
}