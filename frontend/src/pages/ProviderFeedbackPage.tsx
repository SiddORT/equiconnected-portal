import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { ProviderTopNav } from '@/components/layout/ProviderTopNav';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import type { PaginatedResponse, ProviderFeedbackReview } from '@/types';
import styles from './ProviderFeedbackPage.module.css';

const PAGE_SIZE = 10;

type LoadError = 'expired' | 'unavailable' | 'failure';

function responseStatus(error: unknown) {
  return (error as { response?: { status?: number } })?.response?.status;
}

function statusDetails(status: ProviderFeedbackReview['status']) {
  switch (status) {
    case 'PENDING': return { label: 'Awaiting moderation', tone: 'pending' };
    case 'PUBLISHED': return { label: 'Published', tone: 'published' };
    case 'REJECTED': return { label: 'Not published', tone: 'rejected' };
    case 'HIDDEN': return { label: 'Hidden by admin', tone: 'hidden' };
    default: return { label: 'Awaiting moderation', tone: 'pending' };
  }
}

function Rating({ rating }: { rating: number }) {
  return (
    <span className={styles.stars} aria-label={`${rating} out of 5 stars`}>
      <span aria-hidden="true">{'★'.repeat(Math.max(0, Math.min(5, rating)))}{'☆'.repeat(Math.max(0, 5 - rating))}</span>
      <span className={styles.ratingNumber}>{rating}/5</span>
    </span>
  );
}

export function ProviderFeedbackPage() {
  const { formatTimestamp } = useTimeSettings();
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<PaginatedResponse<ProviderFeedbackReview> | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<LoadError | null>(null);
  const requestId = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  const loadPage = useCallback(async (requestedPage: number) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const request = ++requestId.current;
    setBusy(true);
    setError(null);
    try {
      const response = await providersApi.getProviderPortalFeedback(
        requestedPage,
        PAGE_SIZE,
        controller.signal
      );
      if (controller.signal.aborted || request !== requestId.current) return;
      setResult(response);
      setPage(response.meta.page);
    } catch (err) {
      if (controller.signal.aborted || request !== requestId.current) return;
      const status = responseStatus(err);
      if (status === 401 || status === 403) setResult(null);
      setError(status === 401 ? 'expired' : status === 403 ? 'unavailable' : 'failure');
    } finally {
      if (request === requestId.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadPage(page);
    return () => {
      controllerRef.current?.abort();
      requestId.current += 1;
    };
  }, [loadPage, page]);

  const errorCopy = error === 'expired'
    ? 'Your session has expired. Sign in again to view member feedback.'
    : error === 'unavailable'
      ? 'Member feedback is not available for this provider account.'
      : 'We couldn’t load member feedback just now. Please try again.';

  return (
    <div className={styles.page}>
      <ProviderTopNav />
      <main className={styles.shell}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Provider portal / Feedback</p>
            <h1>Member feedback</h1>
            <p className={styles.intro}>A private view of the reviews on your listing, including their current moderation status.</p>
          </div>
          <p className={styles.readOnly}>Read-only · only you can see this page</p>
        </header>

        {busy ? (
          <section className={styles.list} aria-label="Loading member feedback" aria-busy="true">
            <p role="status">Loading member feedback…</p>
            {[0, 1, 2].map((item) => (
              <div className={styles.skeletonCard} key={item}>
                <span className={styles.skeletonLine} />
                <span className={`${styles.skeletonLine} ${styles.short}`} />
                <span className={`${styles.skeletonLine} ${styles.medium}`} />
              </div>
            ))}
          </section>
        ) : error ? (
          <section className={`${styles.state} ${error === 'failure' ? styles.errorState : ''}`} role="alert">
            <span className={styles.stateMark} aria-hidden="true">{error === 'expired' ? '!' : '—'}</span>
            <h2>{error === 'expired' ? 'Session expired' : error === 'unavailable' ? 'Feedback unavailable' : 'We hit a snag'}</h2>
            <p>{errorCopy}</p>
            {error === 'expired' ? (
              <Link className={styles.actionLink} to="/provider/login">Sign in again</Link>
            ) : error === 'failure' ? (
              <button className={styles.actionButton} type="button" onClick={() => void loadPage(page)}>Retry</button>
            ) : (
              <Link className={styles.actionLink} to="/provider/account">Return to Account</Link>
            )}
          </section>
        ) : result?.data.length ? (
          <>
            <div className={styles.listIntro}>
              <span>{result.meta.total} {result.meta.total === 1 ? 'review' : 'reviews'}</span>
              <span>Newest first</span>
            </div>
            <section className={styles.list} aria-label="Member reviews">
              {result.data.map((review) => {
                const status = statusDetails(review.status);
                return (
                  <article className={styles.review} key={review.id}>
                    <div className={styles.reviewTop}>
                      <Rating rating={review.rating} />
                      <span className={styles.status} data-tone={status.tone}>{status.label}</span>
                    </div>
                    <div className={styles.reviewMeta}>
                      <strong>{review.reviewer_name || 'Member'}</strong>
                      <time dateTime={review.created_at}>Submitted {formatTimestamp(review.created_at)}</time>
                    </div>
                    {review.comment ? (
                      <p className={styles.comment}>{review.comment}</p>
                    ) : (
                      <p className={styles.ratingOnly}>Rating only — no written comment was provided.</p>
                    )}
                  </article>
                );
              })}
            </section>
            {result.meta.total_pages > 1 && (
              <nav className={styles.pagination} aria-label="Feedback pages">
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={busy || page <= 1}
                >
                  Previous
                </button>
                <span aria-live="polite">Page {result.meta.page} of {result.meta.total_pages}</span>
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.min(result.meta.total_pages, current + 1))}
                  disabled={busy || page >= result.meta.total_pages}
                >
                  Next
                </button>
              </nav>
            )}
          </>
        ) : (
          <section className={styles.state}>
            <span className={styles.stateMark} aria-hidden="true">✳</span>
            <h2>{page > 1 ? 'No reviews on this page' : 'No feedback yet'}</h2>
            <p>{page > 1
              ? 'The feedback list may have changed. Return to the first page to see the latest reviews.'
              : 'When members review your listing, their ratings and moderation status will appear here.'}</p>
            {page > 1 && <button className={styles.actionButton} type="button" onClick={() => setPage(1)}>Return to first page</button>}
          </section>
        )}
      </main>
    </div>
  );
}
