import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { listMemberHistory } from '@/api/memberFeedback';
import type { MemberFeedbackPage, MemberHistoryEntry } from '@/api/memberFeedback';
import styles from './MemberHistoryPage.module.css';

const allowedFilters = new Set(['name', 'region', 'specialization_id', 'provider_type', 'visit_stability', 'minimum_rating', 'emergency_only', 'saved', 'sort']);
function filterSummary(filters: Record<string, string | boolean | number | null>) {
  const terms = Object.entries(filters).filter(([key, value]) => allowedFilters.has(key) && value !== null && value !== '').map(([key, value]) => {
    const label = key.replace(/_/g, ' ');
    const formatted = typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value);
    return `${label}: ${formatted}`;
  });
  return terms.length ? terms.join(' · ') : 'All providers';
}

export function MemberHistoryPage() {
  const { formatTimestamp } = useTimeSettings();
  const [result, setResult] = useState<MemberFeedbackPage<MemberHistoryEntry> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setResult(await listMemberHistory(page, 10)); }
    catch (loadError) { setError(extractErrorMessage(loadError, 'Your browsing history could not be loaded.')); }
    finally { setLoading(false); }
  }, [page]);
  useEffect(() => { void load(); }, [load]);
  const openHistory = (entry: MemberHistoryEntry) => {
    if (entry.type === 'provider') {
      if (entry.provider_available) navigate(`/providers/${entry.provider_id}`);
      return;
    }
    const params = new URLSearchParams();
    Object.entries(entry.filters ?? {}).forEach(([key, value]) => {
      if (allowedFilters.has(key) && value !== null && value !== '') params.set(key, String(value));
    });
    navigate(`/providers${params.size ? `?${params.toString()}` : ''}`);
  };

  return (
    <main className={styles.page}>
      <div className={styles.inner}>
        <div className={styles.breadcrumb}><Link to="/profile">My account</Link><span>/</span><span>Browsing history</span></div>
        <header className={styles.header}>
          <p className={styles.eyebrow}>Your own account history</p>
          <h1>Browsing history</h1>
          <p>Searches and provider profiles you visit from now on are kept here for your convenience.</p>
        </header>
        <section className={styles.panel} aria-label="Browsing history">
          {loading ? <div className={styles.skeletons} aria-label="Loading history"><i/><i/><i/></div> :
            error ? <div className={styles.state} role="alert"><span>!</span><h2>History is unavailable</h2><p>{error}</p><button type="button" onClick={() => void load()}>Try again</button></div> :
              !result?.data.length ? <div className={styles.empty}><span aria-hidden="true">↗</span><h2>Your activity will collect here</h2><p>Applied provider searches and profiles you open will appear here. Nothing has been added before history was enabled.</p></div> :
                <div className={styles.items}>{result.data.map((entry) => <article className={styles.entry} key={entry.id}>
                  <span className={styles.entryIcon} aria-hidden="true">{entry.type === 'search' ? '⌕' : '↗'}</span>
                  <div className={styles.entryBody}>
                    <div className={styles.entryTitle}><span>{entry.type === 'search' ? 'Provider search' : entry.provider_name}</span><time dateTime={entry.occurred_at}>{formatTimestamp(entry.occurred_at)}</time></div>
                    <p>{entry.type === 'search' ? filterSummary(entry.filters ?? {}) : entry.provider_available ? 'Viewed provider profile' : 'This provider profile is no longer available.'}</p>
                  </div>
                  {entry.type === 'search' || entry.provider_available ? <button type="button" onClick={() => openHistory(entry)}>{entry.type === 'search' ? 'Restore search' : 'Open profile'}<span aria-hidden="true">→</span></button> : <span className={styles.unavailable}>Unavailable</span>}
                </article>)}</div>}
          {result && result.meta.total_pages > 1 && <nav className={styles.pagination} aria-label="History pages"><button type="button" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</button><span>Page {result.meta.page} of {result.meta.total_pages} <small>· {result.meta.total} activities</small></span><button type="button" disabled={page >= result.meta.total_pages || loading} onClick={() => setPage(page + 1)}>Next</button></nav>}
        </section>
      </div>
    </main>
  );
}