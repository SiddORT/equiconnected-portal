import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import * as feedbackApi from '@/api/adminFeedback';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import type {
  AdminPlatformFeedback,
  PlatformFeedbackCategory,
  PlatformFeedbackFilterStatus,
  PlatformFeedbackStatus,
} from '@/api/adminFeedback';
import styles from './PlatformFeedbackPage.module.css';

const STATUSES: Array<{ value: PlatformFeedbackFilterStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All feedback' },
  { value: 'Pending', label: 'Pending' },
  { value: 'In review', label: 'In review' },
  { value: 'Resolved', label: 'Resolved' },
  { value: 'Rejected', label: 'Rejected' },
  { value: 'withdrawn', label: 'Withdrawn' },
];

const CATEGORIES: Array<{ value: PlatformFeedbackCategory | 'all'; label: string }> = [
  { value: 'all', label: 'All categories' },
  { value: 'Website / App', label: 'Website / App' },
  { value: 'Search & Matching', label: 'Search & Matching' },
  { value: 'Provider Experience', label: 'Provider Experience' },
  { value: 'Account / Profile', label: 'Account / Profile' },
  { value: 'Technical Issue', label: 'Technical Issue' },
  { value: 'Suggestion', label: 'Suggestion' },
  { value: 'Other', label: 'Other' },
];

const statusLabel: Record<PlatformFeedbackStatus, string> = {
  Pending: 'Pending',
  'In review': 'In review',
  Resolved: 'Resolved',
  Rejected: 'Rejected',
};

const statusVariant = (status: PlatformFeedbackStatus) => (
  status === 'Resolved' ? 'success'
    : status === 'Pending' ? 'warning'
      : status === 'Rejected' ? 'error' : 'info'
);

const isWithdrawn = (item: AdminPlatformFeedback) => Boolean(item.withdrawn_at);
const displayedStatus = (item: AdminPlatformFeedback) => isWithdrawn(item) ? 'Withdrawn' : statusLabel[item.status];
const displayedStatusVariant = (item: AdminPlatformFeedback) => isWithdrawn(item) ? 'neutral' : statusVariant(item.status);

function categoryLabel(category: PlatformFeedbackCategory) {
  return CATEGORIES.find((item) => item.value === category)?.label ?? category;
}

function detailPath(id: string, params: URLSearchParams) {
  const query = params.toString();
  return `/admin/feedback/${id}${query ? `?${query}` : ''}`;
}

export function PlatformFeedbackPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [result, setResult] = useState<feedbackApi.AdminPlatformFeedbackPage | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const search = searchParams.get('search') ?? '';
  const rawStatus = searchParams.get('status');
  const status = STATUSES.some((item) => item.value === rawStatus)
    ? rawStatus as PlatformFeedbackFilterStatus | 'all'
    : 'all';
  const rawCategory = searchParams.get('category');
  const category = CATEGORIES.some((item) => item.value === rawCategory)
    ? rawCategory as PlatformFeedbackCategory | 'all'
    : 'all';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const requestedPageSize = Number(searchParams.get('page_size'));
  const pageSize = [10, 25, 50, 100].includes(requestedPageSize) ? requestedPageSize : 25;
  const queryKey = `${search}|${status}|${category}|${page}|${pageSize}`;
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
      const response = await feedbackApi.listAdminPlatformFeedback({
        q: search || undefined,
        status: status === 'all' ? undefined : status,
        category: category === 'all' ? undefined : category,
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
      setError(extractErrorMessage(loadError, 'Platform feedback could not be loaded.'));
      setLoadState('error');
    }
  }, [category, page, pageSize, queryKey, search, status, updateParams]);

  useEffect(() => { void load(); }, [load]);
  const columns = useMemo<DataTableColumn<AdminPlatformFeedback>[]>(() => [
    {
      key: 'sender',
      label: 'Member',
      width: '1.35fr',
      render: (item) => <span className={styles.sender}><strong>{item.submitter_name}</strong><small>{item.submitter_email}</small></span>,
    },
    {
      key: 'category',
      label: 'Category',
      width: '1.2fr',
      render: (item) => <Badge size="sm" variant="info">{categoryLabel(item.category)}</Badge>,
    },
    {
      key: 'subject',
      label: 'Subject & rating',
      width: '1.6fr',
      render: (item) => <span className={styles.subject}><strong>{item.subject || 'No subject'}</strong><small>{item.rating ? `${item.rating}/5 rating` : 'No rating'}</small></span>,
    },
    {
      key: 'status',
      label: 'Status',
      width: '115px',
      render: (item) => <Badge size="sm" variant={displayedStatusVariant(item)}>{displayedStatus(item)}</Badge>,
    },
    {
      key: 'submitted_at',
      label: 'Submitted / updated',
      width: '180px',
      hideOnMobile: true,
      render: (item) => <span className={styles.times}><time dateTime={item.submitted_at}>{formatTimestamp(item.submitted_at)}</time>{item.updated_at !== item.submitted_at && <small>Updated {formatTimestamp(item.updated_at)}</small>}</span>,
    },
    {
      key: 'actions',
      label: 'Details',
      width: '90px',
      align: 'right',
      render: (item) => <Link className={styles.viewLink} to={detailPath(item.id, searchParams)} aria-label={`View feedback from ${item.submitter_name}`}>View</Link>,
    },
  ], [formatTimestamp, searchParams]);

  const hasFilters = Boolean(search || status !== 'all' || category !== 'all');

  return (
    <div className={styles.shell}>
      <PageHeader title="Platform feedback" subtitle="Private feedback from members about the EquiConnected experience." breadcrumbs={[{ label: 'Admin' }, { label: 'Platform feedback' }]} />
      <div className={styles.body}>
        <div className={styles.toolbar}>
          <SearchInput value={search} onChange={(value) => updateParams({ search: value.trim() || null, page: '1' })} placeholder="Search member, email, subject or message" aria-label="Search platform feedback" />
          <Button type="button" variant="ghost" disabled={!hasFilters} onClick={() => updateParams({ search: null, status: null, category: null, page: '1' })}>Clear filters</Button>
        </div>
        <div className={styles.filterGroups}>
          <FilterBar groups={[
            {
              label: 'Feedback status',
              value: status,
              onChange: (value) => updateParams({ status: value === 'all' ? null : value, page: '1' }),
              options: STATUSES,
            },
            {
              label: 'Feedback category',
              value: category,
              onChange: (value) => updateParams({ category: value === 'all' ? null : value, page: '1' }),
              options: CATEGORIES,
            },
          ]} />
        </div>
        <div className={styles.tableViewport}>
          <DataTable
            columns={columns}
            data={result?.data ?? []}
            page={page}
            pageSize={pageSize}
            rowKey={(item) => item.id}
            loading={loadState === 'loading'}
            loadingLabel="Loading platform feedback…"
            error={loadState === 'error' ? { title: 'Failed to load platform feedback', message: error ?? undefined, onRetry: load } : null}
            empty={{
              icon: '✉',
              title: hasFilters ? 'No feedback found' : 'No platform feedback yet',
              description: hasFilters ? 'Try adjusting or clearing your search or filters.' : 'Private feedback submitted by members will appear here.',
            }}
            ariaLabel="Platform feedback"
          />
        </div>
        {loadState === 'success' && result && result.meta.total > 0 && (
          <Pagination page={page} pageSize={pageSize} total={result.meta.total} onPageChange={(next) => updateParams({ page: String(next) })} onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })} />
        )}
      </div>
    </div>
  );
}

export function PlatformFeedbackDetailPage() {
  const { formatTimestamp } = useTimeSettings();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const [feedback, setFeedback] = useState<AdminPlatformFeedback | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<PlatformFeedbackStatus>('Pending');
  const [response, setResponse] = useState('');
  const [internalNote, setInternalNote] = useState('');
  const [saving, setSaving] = useState(false);
  const requestId = useRef(0);
  const backToList = `/admin/feedback${searchParams.toString() ? `?${searchParams.toString()}` : ''}`;

  const load = useCallback(async () => {
    const request = ++requestId.current;
    setLoadState('loading');
    setError(null);
    if (!id) {
      setError('Feedback record was not found.');
      setLoadState('error');
      return;
    }
    try {
      const loaded = await feedbackApi.getAdminPlatformFeedback(id);
      if (request !== requestId.current) return;
      setFeedback(loaded);
      setStatus(loaded.status);
      setResponse(loaded.member_response ?? '');
      setInternalNote(loaded.internal_note ?? '');
      setLoadState('success');
    } catch (loadError) {
      if (request !== requestId.current) return;
      setError(extractErrorMessage(loadError, 'Feedback details could not be loaded.'));
      setLoadState('error');
    }
  }, [id]);

  useEffect(() => {
    void load();
    return () => { requestId.current += 1; };
  }, [load]);

  const save = async () => {
    if (!feedback || saving || feedback.withdrawn_at) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await feedbackApi.updateAdminPlatformFeedback(feedback.id, {
        expected_version: feedback.version,
        status,
        member_response: response.trim() || null,
        internal_note: internalNote.trim() || null,
      });
      setFeedback(updated);
      setStatus(updated.status);
      setResponse(updated.member_response ?? '');
      setInternalNote(updated.internal_note ?? '');
    } catch (saveError) {
      const message = extractErrorMessage(saveError, 'Feedback update could not be saved.');
      setError(message);
      // Reload after stale/concurrent writes so the displayed version always
      // matches the server's current record.
      if (message.toLowerCase().includes('changed') || message.toLowerCase().includes('version')) {
        await load();
        setError(`${message} The latest version has been refreshed.`);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.shell}>
      <PageHeader title="Platform feedback" subtitle="Read and process private member feedback." breadcrumbs={[{ label: 'Admin', href: '/admin/dashboard' }, { label: 'Platform feedback', href: '/admin/feedback' }, { label: 'Details' }]} />
      <div className={styles.body}>
        <Link to={backToList} className={styles.backLink}>← Back to platform feedback</Link>
        {loadState === 'loading' && <div className={styles.loading} role="status">Loading feedback…</div>}
        {loadState === 'error' && <div className={styles.errorState} role="alert"><strong>Unable to load this feedback</strong><span>{error}</span><Button size="sm" variant="outline" onClick={() => void load()}>Try again</Button></div>}
        {loadState === 'success' && feedback && (
          <>
            <Card className={styles.detailCard} padding="lg">
              <header className={styles.detailHeading}>
                <div><p className={styles.eyebrow}>Private member feedback</p><h2>{feedback.subject || categoryLabel(feedback.category)}</h2></div>
                <Badge size="sm" variant={displayedStatusVariant(feedback)}>{displayedStatus(feedback)}</Badge>
              </header>
              <dl className={styles.details}>
                <dt>Member</dt><dd><strong>{feedback.submitter_name}</strong><a href={`mailto:${feedback.submitter_email}`}>{feedback.submitter_email}</a></dd>
                <dt>Category</dt><dd>{categoryLabel(feedback.category)}</dd>
                <dt>Rating</dt><dd>{feedback.rating ? <span className={styles.rating} aria-label={`${feedback.rating} out of 5 stars`}>{'★'.repeat(feedback.rating)}{'☆'.repeat(5 - feedback.rating)} {feedback.rating}/5</span> : 'Not provided'}</dd>
                <dt>Submitted</dt><dd><time dateTime={feedback.submitted_at}>{formatTimestamp(feedback.submitted_at)}</time></dd>
                <dt>Last updated</dt><dd><time dateTime={feedback.updated_at}>{formatTimestamp(feedback.updated_at)}</time></dd>
                <dt>Full feedback</dt><dd className={styles.message}>{feedback.message}</dd>
              </dl>
              {feedback.withdrawn_at && <p className={styles.withdrawnNotice}>This submission was withdrawn by its member on {formatTimestamp(feedback.withdrawn_at)}. Its retained content and history are visible here for administration only.</p>}
            </Card>
            {error && <p className={styles.alert} role="alert">{error}</p>}
            {!feedback.withdrawn_at && <Card className={styles.processing} padding="lg">
              <h2>Response and processing</h2>
              <label className={styles.field}>Member-visible response<textarea value={response} maxLength={4000} rows={4} onChange={(event) => setResponse(event.target.value)} aria-describedby="feedback-response-help" /></label>
              <small id="feedback-response-help" className={styles.hint}>This response is visible to the member in their account.</small>
              <label className={styles.field}>Internal administrator note<textarea value={internalNote} maxLength={4000} rows={4} onChange={(event) => setInternalNote(event.target.value)} aria-describedby="feedback-note-help" /></label>
              <small id="feedback-note-help" className={styles.hint}>Internal notes are only visible to administrators.</small>
              <div className={styles.saveControls}>
                <label className={styles.field}>Status<select value={status} onChange={(event) => setStatus(event.target.value as PlatformFeedbackStatus)}><option value="Pending">Pending</option><option value="In review">In review</option><option value="Resolved">Resolved</option><option value="Rejected">Rejected</option></select></label>
                <Button onClick={() => void save()} loading={saving}>Save processing update</Button>
              </div>
            </Card>}
            <Card className={styles.history} padding="lg">
              <h2>Action history</h2>
              {feedback.history?.length ? <ol>{feedback.history.map((item) => <li key={item.id}>
                <div><strong>{item.action.replace(/_/g, ' ')}</strong><span>{item.actor_name || 'System'}{item.actor_email ? ` · ${item.actor_email}` : ''}{item.actor_type ? ` · ${item.actor_type}` : ''}{item.from_status && item.to_status ? ` · ${item.from_status} → ${item.to_status}` : ''}</span>
                  <details className={styles.snapshot}>
                    <summary>Retained submission and moderation snapshot</summary>
                    <dl>{Object.entries(item.content_snapshot).map(([key, value]) => <div key={key}>
                      <dt>{key.replace(/_/g, ' ')}</dt>
                      <dd>{value === null || value === '' ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
                    </div>)}</dl>
                  </details>
                </div>
                <time dateTime={item.created_at}>{formatTimestamp(item.created_at)}</time>
              </li>)}</ol> : <p className={styles.hint}>No actions have been recorded yet.</p>}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}