import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import * as reviewsApi from '@/api/reviews';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import type { AdminReview, ReviewStatus } from '@/api/reviews';
import styles from './ReviewsPage.module.css';

const STATUSES: Array<{ value: ReviewStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All reviews' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'PUBLISHED', label: 'Published' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'HIDDEN', label: 'Hidden' },
];

const statusLabel: Record<ReviewStatus, string> = {
  PENDING: 'Pending',
  PUBLISHED: 'Published',
  REJECTED: 'Rejected',
  HIDDEN: 'Hidden',
};

const statusVariant = (status: ReviewStatus) => (
  status === 'PUBLISHED' ? 'success'
    : status === 'PENDING' ? 'warning'
      : status === 'REJECTED' ? 'error' : 'neutral'
);

export function ReviewsPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [result, setResult] = useState<reviewsApi.AdminReviewPage | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminReview | null>(null);
  const [detailState, setDetailState] = useState<'loading' | 'success' | 'error'>('loading');
  const [detailError, setDetailError] = useState<string | null>(null);
  const [nextStatus, setNextStatus] = useState<ReviewStatus>('PENDING');
  const [memberNote, setMemberNote] = useState('');
  const [internalNote, setInternalNote] = useState('');
  const [saving, setSaving] = useState(false);
  const requestId = useRef(0);
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const rawStatus = searchParams.get('status');
  const status = STATUSES.some((item) => item.value === rawStatus)
    ? rawStatus as ReviewStatus | 'all'
    : 'all';
  const providerId = searchParams.get('provider_id') ?? undefined;
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const requestedPageSize = Number(searchParams.get('page_size'));
  const pageSize = [10, 25, 50, 100].includes(requestedPageSize) ? requestedPageSize : 25;
  const queryKey = `${status}|${providerId ?? ''}|${page}|${pageSize}`;
  const currentQueryKey = useRef(queryKey);
  currentQueryKey.current = queryKey;

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    setSearchParams(next);
  }, [searchParams, setSearchParams]);

  const load = useCallback(async () => {
    const requestedKey = queryKey;
    setLoadState('loading');
    setError(null);
    try {
      const response = await reviewsApi.listAdminReviews({
        status: status === 'all' ? undefined : status,
        provider_id: providerId,
        page,
        page_size: pageSize,
      });
      if (currentQueryKey.current !== requestedKey) return;
      if (page > response.meta.total_pages && response.meta.total > 0) {
        updateParams({ page: '1' });
        return;
      }
      setResult(response);
      setLoadState('success');
    } catch (loadError) {
      if (currentQueryKey.current !== requestedKey) return;
      setError(extractErrorMessage(loadError, 'Reviews could not be loaded.'));
      setLoadState('error');
    }
  }, [page, pageSize, providerId, queryKey, status, updateParams]);

  useEffect(() => { void load(); }, [load]);

  const loadDetail = useCallback(async (id: string) => {
    const request = ++requestId.current;
    setDetailState('loading');
    setDetailError(null);
    try {
      const loaded = await reviewsApi.getAdminReview(id);
      if (request !== requestId.current) return;
      setDetail(loaded);
      setNextStatus(loaded.status);
      setMemberNote(loaded.member_note ?? '');
      setInternalNote(loaded.internal_note ?? '');
      setDetailState('success');
    } catch (loadError) {
      if (request !== requestId.current) return;
      setDetailError(extractErrorMessage(loadError, 'Review details could not be loaded.'));
      setDetailState('error');
    }
  }, []);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
    return () => { requestId.current += 1; };
  }, [loadDetail, selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setSelectedId(null);
        setDetail(null);
        setDetailError(null);
      }
      if (event.key === 'Tab' && dialogRef.current) {
        const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href], summary',
        ));
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [selectedId]);

  const openDetail = (id: string) => {
    setSelectedId(id);
    setDetail(null);
  };
  const closeDetail = () => {
    setSelectedId(null);
    setDetail(null);
    setDetailError(null);
  };

  const save = async (targetStatus = nextStatus) => {
    if (!detail || saving || detail.deleted_at) return;
    setSaving(true);
    setDetailError(null);
    try {
      const updated = await reviewsApi.updateAdminReview(detail.id, {
        status: targetStatus,
        expected_version: detail.version,
        member_note: memberNote.trim() || null,
        internal_note: internalNote.trim() || null,
      });
      setDetail(updated);
      setNextStatus(updated.status);
      setMemberNote(updated.member_note ?? '');
      setInternalNote(updated.internal_note ?? '');
      setResult((current) => current
        ? { ...current, data: current.data.map((item) => item.id === updated.id ? updated : item) }
        : current);
      setError(null);
      try {
        // The status-write response is the current review row; reload its
        // retained action snapshots so the audit timeline immediately reflects
        // this decision and its before/after content.
        setDetail(await reviewsApi.getAdminReview(updated.id));
      } catch {
        // Keep the successful moderation response visible if the optional
        // history refresh is temporarily unavailable.
      }
      if (status !== 'all' && updated.status !== status) void load();
    } catch (saveError) {
      const message = extractErrorMessage(saveError, 'Review moderation could not be saved.');
      setDetailError(message);
      // A 409 means another moderator changed this review. Refresh before
      // allowing another update so a stale version is never submitted again.
      if (message.toLowerCase().includes('changed') || message.toLowerCase().includes('version')) {
        await loadDetail(detail.id);
        await load();
        setDetailError(`${message} The latest version has been refreshed.`);
      }
    } finally {
      setSaving(false);
    }
  };

  const columns = useMemo<DataTableColumn<AdminReview>[]>(() => [
    {
      key: 'provider',
      label: 'Provider',
      width: '1.1fr',
      render: (review) => <strong>{review.provider_name}</strong>,
    },
    {
      key: 'member',
      label: 'Member',
      width: '1.45fr',
      render: (review) => <span className={styles.memberCell}><strong>{review.reviewer_name}</strong><small>{review.reviewer_email}</small></span>,
    },
    {
      key: 'rating',
      label: 'Rating',
      width: '95px',
      render: (review) => <span className={styles.rating} aria-label={`${review.rating} out of 5 stars`}>{'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)} <small>{review.rating}/5</small></span>,
    },
    {
      key: 'status',
      label: 'Status',
      width: '120px',
      render: (review) => review.deleted_at
        ? <Badge size="sm" variant="neutral">Deleted</Badge>
        : <Badge size="sm" variant={statusVariant(review.status)}>{statusLabel[review.status]}</Badge>,
    },
    {
      key: 'created_at',
      label: 'Submitted',
      width: '160px',
      hideOnMobile: true,
      render: (review) => <time dateTime={review.created_at}>{formatTimestamp(review.created_at)}</time>,
    },
    {
      key: 'actions',
      label: 'Details',
      width: '90px',
      align: 'right',
      render: (review) => <Button size="sm" variant="outline" onClick={() => openDetail(review.id)}>View</Button>,
    },
  ], [formatTimestamp]);

  const hasFilters = Boolean(status !== 'all' || providerId);

  return (
    <div className={styles.shell}>
      <PageHeader title="Provider reviews" subtitle="Review member experiences, make publication decisions and keep a clear moderation record." breadcrumbs={[{ label: 'Admin' }, { label: 'Reviews' }]} />
      <div className={styles.body}>
        {error && loadState !== 'error' && <p className={styles.error} role="alert">{error}</p>}
        {providerId && (
          <div className={styles.scopeBanner} role="status">
            <span>Showing reviews for <strong>{result?.data[0]?.provider_name ?? 'selected provider'}</strong></span>
            <Button size="sm" variant="outline" onClick={() => updateParams({ provider_id: null, page: '1' })}>View all reviews</Button>
          </div>
        )}
        {hasFilters && <Button className={styles.clearButton} type="button" variant="ghost" onClick={() => updateParams({ status: null, provider_id: null, page: '1' })}>Clear filters</Button>}
        <FilterBar groups={[{
          label: 'Review status',
          value: status,
          onChange: (value) => updateParams({ status: value === 'all' ? null : value, page: '1' }),
          options: STATUSES,
        }]} />
        <div className={styles.tableViewport}>
          <DataTable
            columns={columns}
            data={result?.data ?? []}
            page={page}
            pageSize={pageSize}
            rowKey={(review) => review.id}
            loading={loadState === 'loading'}
            loadingLabel="Loading reviews…"
            error={loadState === 'error' ? { title: 'Failed to load reviews', message: error ?? undefined, onRetry: load } : null}
            empty={{
              icon: '★',
              title: hasFilters ? 'No reviews found' : 'No member reviews yet',
              description: hasFilters ? 'Try selecting another review status or clearing the current provider filter.' : 'Member reviews will appear here.',
            }}
            ariaLabel="Provider reviews"
          />
        </div>
        {loadState === 'success' && result && result.meta.total > 0 && (
          <Pagination page={page} pageSize={pageSize} total={result.meta.total} onPageChange={(next) => updateParams({ page: String(next) })} onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })} />
        )}
      </div>

      {selectedId && (
        <div className={styles.scrim} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDetail(); }}>
          <section ref={dialogRef} className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="review-detail-title">
            <header className={styles.dialogHeader}>
              <div><p className={styles.eyebrow}>Member review</p><h2 id="review-detail-title">{detail?.provider_name ?? 'Review details'}</h2></div>
              <button ref={closeRef} className={styles.closeButton} type="button" onClick={closeDetail} aria-label="Close review details">×</button>
            </header>
            {detailState === 'loading' && <p role="status">Loading review details…</p>}
            {detailState === 'error' && <div role="alert"><p>{detailError}</p><Button size="sm" variant="outline" onClick={() => void loadDetail(selectedId)}>Try again</Button></div>}
            {detailState === 'success' && detail && (
              <>
                <div className={styles.detailMeta}>
                  <span><strong>{detail.reviewer_name}</strong><small>{detail.reviewer_email}</small></span>
                  <Badge size="sm" variant={detail.deleted_at ? 'neutral' : statusVariant(detail.status)}>{detail.deleted_at ? 'Deleted' : statusLabel[detail.status]}</Badge>
                  <span className={styles.rating} aria-label={`${detail.rating} out of 5 stars`}>{'★'.repeat(detail.rating)}{'☆'.repeat(5 - detail.rating)} <small>{detail.rating}/5</small></span>
                </div>
                <p className={styles.comment}>{detail.comment || 'No written comment was provided.'}</p>
                <p className={styles.muted}>Submitted <time dateTime={detail.created_at}>{formatTimestamp(detail.created_at)}</time>{detail.updated_at !== detail.created_at && <> · Updated <time dateTime={detail.updated_at}>{formatTimestamp(detail.updated_at)}</time></>}</p>
                {detail.deleted_at && <p className={styles.deletedNotice}>This review was removed by its owner on {formatTimestamp(detail.deleted_at)}. The retained content and action history are available for administrative review only.</p>}
                <div className={styles.noteFields}>
                  <label>Member-visible moderation note<textarea value={memberNote} maxLength={2000} rows={3} disabled={Boolean(detail.deleted_at)} onChange={(event) => setMemberNote(event.target.value)} /></label>
                  <label>Internal administrator note<textarea value={internalNote} maxLength={4000} rows={3} disabled={Boolean(detail.deleted_at)} onChange={(event) => setInternalNote(event.target.value)} /></label>
                </div>
                <section className={styles.history} aria-labelledby="review-history-title">
                  <h3 id="review-history-title">Moderation history</h3>
                  {detail.history?.length ? <ol>{detail.history.map((item) => <li key={item.id}>
                    <div>
                      <strong>{item.action.replace(/_/g, ' ')}</strong>
                      <span>{item.actor_name || 'System'}{item.actor_email ? ` · ${item.actor_email}` : ''}{item.actor_type ? ` · ${item.actor_type}` : ''}{item.from_status && item.to_status ? ` · ${statusLabel[item.from_status]} → ${statusLabel[item.to_status]}` : ''}</span>
                      <details className={styles.snapshot}>
                        <summary>Retained review snapshot</summary>
                        <dl>{Object.entries(item.content_snapshot).map(([key, value]) => <div key={key}>
                          <dt>{key.replace(/_/g, ' ')}</dt>
                          <dd>{value === null || value === '' ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
                        </div>)}</dl>
                      </details>
                    </div>
                    <time dateTime={item.created_at}>{formatTimestamp(item.created_at)}</time>
                  </li>)}</ol> : <p className={styles.muted}>No moderation actions have been recorded.</p>}
                </section>
                {!detail.deleted_at && <>
                  {detailError && <p className={styles.error} role="alert">{detailError}</p>}
                  <div className={styles.actions}>
                    <label className={styles.statusSelect}>Review status<select value={nextStatus} onChange={(event) => setNextStatus(event.target.value as ReviewStatus)}><option value="PENDING">Pending</option><option value="PUBLISHED">Published</option><option value="REJECTED">Rejected</option><option value="HIDDEN" disabled={detail.status !== 'PUBLISHED' && detail.status !== 'HIDDEN'}>Hidden</option></select></label>
                    {detail.status === 'PENDING' && <Button size="sm" onClick={() => void save('PUBLISHED')} loading={saving}>Approve &amp; publish</Button>}
                    {detail.status !== 'REJECTED' && <Button size="sm" variant="outline" onClick={() => void save('REJECTED')} loading={saving}>Reject</Button>}
                    {detail.status === 'PUBLISHED' && <Button size="sm" variant="outline" onClick={() => void save('HIDDEN')} loading={saving}>Hide comment</Button>}
                    {detail.status === 'HIDDEN' && <Button size="sm" variant="secondary" onClick={() => void save('PUBLISHED')} loading={saving}>Restore comment</Button>}
                    <Button size="sm" variant="outline" onClick={() => void save()} loading={saving}>Save notes</Button>
                  </div>
                </>}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}