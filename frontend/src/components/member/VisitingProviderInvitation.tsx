import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getMemberVisitAvailability } from '@/api/providers';
import styles from './VisitingProviderInvitation.module.css';

/** Directory-wide discovery, intentionally independent of listing filters. */
export function VisitingProviderInvitation({ query, directoryState }: { query: string; directoryState?: unknown }) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setAvailable(null);
    setFailed(false);
    void getMemberVisitAvailability().then(data => {
      if (active) setAvailable(data.has_visits);
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [retry]);
  return <section className={styles.invitation} aria-label="Directory-wide visiting providers">
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4m10-4v4M3 11h18m-13 4h3m2 0h3" /></svg>
    <div>
      <h2>{available === true ? 'See our esteemed visiting providers' : available === false ? 'No providers visiting' : 'Visiting providers'}</h2>
      <p>Scheduled visiting periods across the entire directory, independent of your filters.</p>
      {available === null && !failed && <p role="status">Checking scheduled visits…</p>}
      {failed && <div role="alert"><p>We couldn’t check visiting providers. Your directory results are still available.</p>
        <button type="button" onClick={() => setRetry(n => n + 1)}>Retry visiting providers</button></div>}
    </div>
    {available === true && <Link state={directoryState} to={`/providers/visiting-calendar${query ? `?${query}` : ''}`}>View calendar <span aria-hidden="true">→</span></Link>}
  </section>;
}