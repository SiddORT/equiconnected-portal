import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  approveProviderApplication,
  listProviderApplications,
  rejectProviderApplication,
} from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { ActionMenu } from '@/components/ui/ActionMenu';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import type { LoadingState, PaginatedResponse, ProviderApplication, ProviderApplicationStatus } from '@/types';
import styles from './UsersPage.module.css';

const TYPE_OPTIONS = [
  { value: 'all', label: 'All provider types' },
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'CLINIC', label: 'Clinic' },
  { value: 'DOCTOR', label: 'Doctor' },
];
const REVIEW_OPTIONS = [
  { value: 'all', label: 'All review states' },
  { value: 'AWAITING_EMAIL_VERIFICATION', label: 'Awaiting email verification' },
  { value: 'PENDING_REVIEW', label: 'Pending review' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
];

function applicationStatusBadge(status: ProviderApplicationStatus) {
  const config: Record<ProviderApplicationStatus, { label: string; variant: 'warning' | 'success' | 'error' | 'neutral' }> = {
    AWAITING_EMAIL_VERIFICATION: { label: 'Unverified', variant: 'neutral' },
    PENDING_REVIEW: { label: 'Pending review', variant: 'warning' },
    APPROVED: { label: 'Approved', variant: 'success' },
    REJECTED: { label: 'Rejected', variant: 'error' },
  };
  return <Badge size="sm" variant={config[status].variant}>{config[status].label}</Badge>;
}

export function ProviderApplicationsPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') ?? '';
  const providerType = searchParams.get('provider_type') ?? '';
  const reviewStatus = (searchParams.get('review_status') ?? '') as ProviderApplicationStatus | '';
  const emailVerifiedParam = searchParams.get('email_verified');
  const emailVerified = emailVerifiedParam === 'true' ? true : emailVerifiedParam === 'false' ? false : undefined;
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pageSize = [10, 25, 100].includes(Number(searchParams.get('page_size'))) ? Number(searchParams.get('page_size')) : 10;
  const [result, setResult] = useState<PaginatedResponse<ProviderApplication> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [detailTarget, setDetailTarget] = useState<ProviderApplication | null>(null);
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    setSearchParams(next);
  }, [searchParams, setSearchParams]);

  const load = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const response = await listProviderApplications({
        search: search || undefined,
        provider_type: providerType ? providerType as ProviderApplication['provider_type'] : undefined,
        review_status: reviewStatus || undefined,
        email_verified: emailVerified,
        page,
        page_size: pageSize,
      });
      if (page > response.meta.total_pages && response.meta.total > 0) {
        updateParams({ page: '1' });
        return;
      }
      setResult(response);
      setLoadState('success');
    } catch (error) {
      setErrorMessage(extractErrorMessage(error, 'Failed to load provider applications.'));
      setLoadState('error');
    }
  }, [emailVerified, page, pageSize, providerType, reviewStatus, search, updateParams]);

  useEffect(() => { void load(); }, [load]);

  const columns: DataTableColumn<ProviderApplication>[] = [
    { key: 'provider_name', label: 'Provider', width: '1.4fr', render: (item) => <span className={styles.nameCell}><strong>{item.provider_name}</strong><span className={styles.muted}>{item.full_name}</span></span> },
    { key: 'provider_type', label: 'Type', width: '0.8fr', hideOnMobile: true, render: (item) => <Badge size="sm" variant="info">{item.provider_type[0] + item.provider_type.slice(1).toLowerCase()}</Badge> },
    { key: 'email', label: 'Email', width: '1.4fr', render: (item) => <span className={styles.emailCell}>{item.email}</span> },
    { key: 'email_verified_at', label: 'Email', width: '100px', hideOnMobile: true, render: (item) => item.email_verified_at ? <Badge size="sm" variant="success">Verified</Badge> : <Badge size="sm" variant="neutral">Unverified</Badge> },
    { key: 'review_status', label: 'Review', width: '130px', hideOnMobile: true, render: (item) => applicationStatusBadge(item.review_status) },
    { key: 'actions', label: 'Actions', width: '70px', align: 'right', render: (item) => <ActionMenu ariaLabel={`Actions for ${item.provider_name}`} items={[{ label: 'View application', onSelect: () => { setDetailTarget(item); setDecisionError(null); } }]} /> },
  ];

  const hasFilters = Boolean(search || providerType || reviewStatus || emailVerified !== undefined);
  const isUnfilteredEmpty =
    loadState === 'success' &&
    result !== null &&
    result.meta.total === 0 &&
    !hasFilters;
  const showListControls = !isUnfilteredEmpty;

  async function decide() {
    if (!detailTarget || !decision) return;
    setDeciding(true);
    setDecisionError(null);
    try {
      const updated = decision === 'approve'
        ? await approveProviderApplication(detailTarget.id)
        : await rejectProviderApplication(detailTarget.id);
      setDetailTarget(updated);
      setDecision(null);
      await load();
    } catch (error) {
      setDecisionError(extractErrorMessage(error, 'The application decision could not be saved.'));
      setDecision(null);
    } finally {
      setDeciding(false);
    }
  }

  return (
    <div className={styles.shell}>
      <PageHeader title="Provider applications" subtitle="Review verified provider registrations before staging directory listings." breadcrumbs={[{ label: 'Admin' }, { label: 'Provider applications' }]} />
      <div className={styles.body}>
        {showListControls && (
          <>
            <div className={styles.toolbar}>
              <SearchInput value={search} onChange={(value) => updateParams({ search: value || null, page: '1' })} placeholder="Search provider, contact, or email" aria-label="Search provider applications" />
              <Button variant="secondary" onClick={() => setFiltersOpen((open) => !open)} aria-expanded={filtersOpen} aria-controls="provider-application-filters">Filters</Button>
            </div>
            {filtersOpen && <div id="provider-application-filters"><FilterBar groups={[
              { label: 'Provider type', value: providerType || 'all', onChange: (value: string) => updateParams({ provider_type: value === 'all' ? null : value, page: '1' }), options: TYPE_OPTIONS },
              { label: 'Email verification', value: emailVerified === undefined ? 'all' : String(emailVerified), onChange: (value: string) => updateParams({ email_verified: value === 'all' ? null : value, page: '1' }), options: [{ value: 'all', label: 'All applications' }, { value: 'true', label: 'Verified' }, { value: 'false', label: 'Unverified' }] },
              { label: 'Review status', value: reviewStatus || 'all', onChange: (value: string) => updateParams({ review_status: value === 'all' ? null : value, page: '1' }), options: REVIEW_OPTIONS },
            ]} /></div>}
          </>
        )}
        <DataTable columns={columns} data={result?.data ?? []} page={page} pageSize={pageSize} rowKey={(item) => item.id} loading={loadState === 'loading'} ariaLabel="Provider applications" error={loadState === 'error' ? { title: 'Failed to load provider applications', message: errorMessage ?? undefined, onRetry: load } : null} empty={{ icon: '🏥', title: hasFilters ? 'No provider applications found' : 'No provider applications yet', description: hasFilters ? 'Try adjusting your search or filters.' : 'Verified provider registrations will appear here for review.' }} />
        {showListControls && loadState === 'success' && result && <Pagination page={page} pageSize={pageSize} total={result.meta.total} onPageChange={(next) => updateParams({ page: String(next) })} onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })} />}
      </div>
      {detailTarget && <ApplicationDialog application={detailTarget} formatTimestamp={formatTimestamp} onClose={() => { setDetailTarget(null); setDecision(null); }} onDecision={setDecision} error={decisionError} />}
      {detailTarget && decision && <DecisionDialog action={decision} providerName={detailTarget.provider_name} busy={deciding} onCancel={() => setDecision(null)} onConfirm={() => void decide()} />}
    </div>
  );
}

function ApplicationDialog({ application, formatTimestamp, onClose, onDecision, error }: { application: ProviderApplication; formatTimestamp: (value: string) => string; onClose: () => void; onDecision: (value: 'approve' | 'reject') => void; error: string | null }) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { closeRef.current?.focus(); const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); }; window.addEventListener('keydown', handler); return () => window.removeEventListener('keydown', handler); }, [onClose]);
  const isPending = application.review_status === 'PENDING_REVIEW';
  return <div className={styles.detailBackdrop} role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className={styles.detailPanel}>
      <header className={styles.detailHeader}><h2 id={titleId} className={styles.detailTitle}>Provider application</h2><button ref={closeRef} type="button" className={styles.detailClose} onClick={onClose} aria-label="Close dialog">✕</button></header>
      <dl className={styles.details}>
        <dt>Provider</dt><dd>{application.provider_name}</dd>
        <dt>Type</dt><dd>{application.provider_type[0] + application.provider_type.slice(1).toLowerCase()}</dd>
        <dt>Visit availability</dt><dd>{application.visit_stability === 'STABLE_VISIT' ? 'Stable visits' : 'Clinic-based'}</dd>
        <dt>Applicant</dt><dd>{application.full_name}</dd>
        <dt>Email</dt><dd>{application.email}</dd>
        <dt>Mobile</dt><dd>{application.mobile_number ?? '—'}</dd>
        <dt>Location</dt><dd>{[application.city, application.state_province, application.country].filter(Boolean).join(', ') || '—'}</dd>
        <dt>Email verification</dt><dd>{application.email_verified_at ? <><Badge size="sm" variant="success">Verified</Badge><span className={styles.muted}>{formatTimestamp(application.email_verified_at)}</span></> : <Badge size="sm" variant="neutral">Unverified</Badge>}</dd>
        <dt>Review status</dt><dd>{applicationStatusBadge(application.review_status)}</dd>
        <dt>Submitted</dt><dd>{formatTimestamp(application.created_at)}</dd>
        {application.reviewed_at && <><dt>Reviewed</dt><dd>{formatTimestamp(application.reviewed_at)}{application.reviewed_by_name ? ` by ${application.reviewed_by_name}` : ''}</dd></>}
        {application.rejection_reason && <><dt>Reason</dt><dd>{application.rejection_reason}</dd></>}
        {application.provider_id && <><dt>Staged listing</dt><dd>Draft, unpublished</dd></>}
      </dl>
      {error && <div style={{ padding: '0 var(--space-6)' }}><Alert variant="error">{error}</Alert></div>}
      <footer className={styles.detailFooter}>
        {isPending && <><Button variant="danger" onClick={() => onDecision('reject')}>Reject</Button><Button variant="primary" onClick={() => onDecision('approve')}>Approve &amp; stage listing</Button></>}
        <Button variant="ghost" onClick={onClose}>Close</Button>
      </footer>
    </div>
  </div>;
}

function DecisionDialog({ action, providerName, busy, onCancel, onConfirm }: { action: 'approve' | 'reject'; providerName: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const titleId = useId();
  const confirmationRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { confirmationRef.current?.focus(); }, []);
  const approving = action === 'approve';
  return <div className={styles.detailBackdrop} role="dialog" aria-modal="true" aria-labelledby={titleId}>
    <div className={styles.detailPanel}>
      <header className={styles.detailHeader}><h2 id={titleId} className={styles.detailTitle}>{approving ? 'Approve provider application?' : 'Reject provider application?'}</h2></header>
      <div style={{ padding: 'var(--space-6)' }}>
        <p>{approving ? `Approving ${providerName} will enable its account and create one draft, unpublished directory listing.` : `Rejecting ${providerName} will prevent provider access and listing creation.`}</p>
        <p className={styles.muted}>This decision is recorded in the activity history.</p>
      </div>
      <footer className={styles.detailFooter}><Button variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button><Button ref={confirmationRef} variant={approving ? 'primary' : 'danger'} onClick={onConfirm} loading={busy}>{approving ? 'Approve application' : 'Reject application'}</Button></footer>
    </div>
  </div>;
}