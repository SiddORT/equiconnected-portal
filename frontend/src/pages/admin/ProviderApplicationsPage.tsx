import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  approveProviderApplication,
  approveProviderProfileUpdate,
  listProviderApplications,
  listProviderProfileUpdates,
  rejectProviderApplication,
  rejectProviderProfileUpdate,
} from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { ProviderPhotoComparison } from '@/components/admin/ProviderPhotoComparison';
import photoStyles from '@/components/admin/ProviderPhotoComparison.module.css';
import { ActionMenu } from '@/components/ui/ActionMenu';
import { ViewIcon } from '@/components/ui/AdminIcons';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import applicationStyles from './ProviderApplicationsPage.module.css';
import styles from './UsersPage.module.css';
import type {
  LoadingState,
  PaginatedResponse,
  ProviderApplication,
  ProviderApplicationStatus,
  ProviderProfileUpdate,
  ProviderProfileUpdateStatus,
} from '@/types';

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

function updateStatusBadge(status: ProviderProfileUpdateStatus) {
  const config: Record<ProviderProfileUpdateStatus, { label: string; variant: 'warning' | 'success' | 'error' }> = {
    PENDING_REVIEW: { label: 'Pending review', variant: 'warning' },
    APPROVED: { label: 'Approved', variant: 'success' },
    REJECTED: { label: 'Rejected', variant: 'error' },
  };
  return <Badge size="sm" variant={config[status].variant}>{config[status].label}</Badge>;
}

interface ProposedVisitLocation {
  name?: string | null;
  address_line_1?: string | null;
  address_line_2?: string | null;
  city?: string | null;
  state_province?: string | null;
  postal_code?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_primary?: boolean | null;
}

interface ProposedVisitAddition {
  start_date: string;
  end_date: string;
  location: ProposedVisitLocation;
}

const calendarDateFormatter = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
});

function formatCalendarDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;

  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const date = new Date(0);
  date.setUTCHours(0, 0, 0, 0);
  date.setUTCFullYear(year, month - 1, day);
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) return value;

  return calendarDateFormatter.format(date);
}

function renderVisitAdditions(value: unknown): ReactNode {
  const visits = Array.isArray(value) ? value as ProposedVisitAddition[] : [];
  if (!visits.length) {
    return 'No visits are being added; the provider’s existing visit history remains unchanged.';
  }

  const locationFields: Array<[string, keyof ProposedVisitLocation]> = [
    ['Name', 'name'],
    ['Address line 1', 'address_line_1'],
    ['Address line 2', 'address_line_2'],
    ['City', 'city'],
    ['State / province', 'state_province'],
    ['Postal code', 'postal_code'],
    ['Country', 'country'],
    ['Latitude', 'latitude'],
    ['Longitude', 'longitude'],
    ['Primary location', 'is_primary'],
  ];

  return <>
    <p>These visits are added to the existing history; they do not replace scheduled or completed visits.</p>
    <ol aria-label="Proposed additional doctor visits">
      {visits.map((visit, index) => <li key={`${visit.start_date}-${visit.end_date}-${index}`}>
        <strong>
          {formatCalendarDate(visit.start_date)} – {formatCalendarDate(visit.end_date)} (inclusive)
        </strong>
        <ul>
          {locationFields.map(([label, field]) => {
            const rawValue = visit.location?.[field];
            const displayValue = rawValue === null || rawValue === undefined || rawValue === ''
              ? 'Not provided'
              : typeof rawValue === 'boolean'
                ? rawValue ? 'Yes' : 'No'
                : String(rawValue);
            return <li key={field}><strong>{label}:</strong> {displayValue}</li>;
          })}
        </ul>
      </li>)}
    </ol>
  </>;
}

export function ProviderApplicationsPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') ?? '';
  const activeTab = searchParams.get('tab') === 'updates' ? 'updates' : 'applications';
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
    { key: 'actions', label: 'Actions', width: '70px', align: 'right', render: (item) => <ActionMenu ariaLabel={`Actions for ${item.provider_name}`} items={[{ label: 'View application', icon: <ViewIcon />, onSelect: () => { setDetailTarget(item); setDecisionError(null); } }]} /> },
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
        <div className={styles.toolbar} role="tablist" aria-label="Provider review queues">
          <Button variant={activeTab === 'applications' ? 'primary' : 'secondary'} onClick={() => updateParams({ tab: null, page: '1' })} role="tab" aria-selected={activeTab === 'applications'}>New applications</Button>
          <Button variant={activeTab === 'updates' ? 'primary' : 'secondary'} onClick={() => updateParams({ tab: 'updates', page: '1' })} role="tab" aria-selected={activeTab === 'updates'}>Updates</Button>
        </div>
        {activeTab === 'updates' ? <ProviderUpdatesTab formatTimestamp={formatTimestamp} /> : <>
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
        </>}
      </div>
      {activeTab === 'applications' && detailTarget && <ApplicationDialog application={detailTarget} formatTimestamp={formatTimestamp} onClose={() => { setDetailTarget(null); setDecision(null); }} onDecision={setDecision} error={decisionError} confirmationOpen={decision !== null} />}
      {activeTab === 'applications' && detailTarget && decision && <DecisionDialog action={decision} providerName={detailTarget.provider_name} busy={deciding} onCancel={() => setDecision(null)} onConfirm={() => void decide()} />}
    </div>
  );
}

function ProviderUpdatesTab({ formatTimestamp }: { formatTimestamp: (value: string) => string }) {
  const [search, setSearch] = useState('');
  const [reviewStatus, setReviewStatus] = useState<ProviderProfileUpdateStatus | ''>('');
  const [result, setResult] = useState<PaginatedResponse<ProviderProfileUpdate> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [detailTarget, setDetailTarget] = useState<ProviderProfileUpdate | null>(null);
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);

  const load = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      setResult(await listProviderProfileUpdates({
        search: search || undefined,
        review_status: reviewStatus || undefined,
        page: 1,
        page_size: 100,
      }));
      setLoadState('success');
    } catch (error) {
      setLoadState('error');
      setErrorMessage(extractErrorMessage(error, 'Failed to load provider profile updates.'));
    }
  }, [reviewStatus, search]);

  useEffect(() => { void load(); }, [load]);

  async function decide(rejectionReason?: string) {
    if (!detailTarget || !decision || deciding) return;
    setDeciding(true);
    setDecisionError(null);
    try {
      const updated = decision === 'approve'
        ? await approveProviderProfileUpdate(detailTarget.id)
        : await rejectProviderProfileUpdate(detailTarget.id, rejectionReason);
      setDetailTarget(updated);
      setDecision(null);
      await load();
    } catch (error) {
      setDecisionError(extractErrorMessage(error, 'The profile update decision could not be saved.'));
      setDecision(null);
    } finally {
      setDeciding(false);
    }
  }

  const columns: DataTableColumn<ProviderProfileUpdate>[] = [
    { key: 'provider_name', label: 'Provider', width: '1.3fr', render: (item) => <span className={styles.nameCell}><strong>{item.provider_name}</strong><span className={styles.muted}>{item.provider_type[0] + item.provider_type.slice(1).toLowerCase()}</span></span> },
    { key: 'changes', label: 'Proposed change', width: '1.4fr', hideOnMobile: true, render: (item) => <span>{item.current_profile.name === item.proposed_profile.name ? 'Profile details revised' : `${item.current_profile.name} → ${item.proposed_profile.name}`}</span> },
    { key: 'submitted_at', label: 'Submitted', width: '160px', hideOnMobile: true, render: (item) => formatTimestamp(item.submitted_at) },
    { key: 'review_status', label: 'Review', width: '130px', render: (item) => updateStatusBadge(item.review_status) },
    { key: 'actions', label: 'Actions', width: '70px', align: 'right', render: (item) => <ActionMenu ariaLabel={`Actions for ${item.provider_name} update`} items={[{ label: 'Compare profiles', onSelect: () => { setDetailTarget(item); setDecisionError(null); } }]} /> },
  ];
  const hasFilters = Boolean(search || reviewStatus);

  return <>
    <div className={styles.toolbar}>
      <SearchInput value={search} onChange={setSearch} placeholder="Search provider" aria-label="Search provider updates" />
      <FilterBar groups={[{
        label: 'Review status',
        value: reviewStatus || 'all',
        onChange: (value: string) => setReviewStatus(value === 'all' ? '' : value as ProviderProfileUpdateStatus),
        options: [
          { value: 'all', label: 'All review states' },
          { value: 'PENDING_REVIEW', label: 'Pending review' },
          { value: 'APPROVED', label: 'Approved' },
          { value: 'REJECTED', label: 'Rejected' },
        ],
      }]} />
    </div>
    <DataTable columns={columns} data={result?.data ?? []} page={1} pageSize={100} rowKey={(item) => item.id} loading={loadState === 'loading'} ariaLabel="Provider profile updates" error={loadState === 'error' ? { title: 'Failed to load provider profile updates', message: errorMessage ?? undefined, onRetry: load } : null} empty={{ icon: '↻', title: hasFilters ? 'No provider updates found' : 'No provider updates yet', description: hasFilters ? 'Try adjusting your search or review status.' : 'Published provider profile changes will appear here for review.' }} />
     {detailTarget && <ProfileUpdateDialog update={detailTarget} formatTimestamp={formatTimestamp} error={decisionError} confirmationOpen={decision !== null} onClose={() => { if (!deciding && !decision) setDetailTarget(null); }} onDecision={setDecision} />}
    {detailTarget && decision && <ProfileUpdateDecisionDialog action={decision} providerName={detailTarget.provider_name} busy={deciding} onCancel={() => setDecision(null)} onConfirm={(reason) => void decide(reason)} />}
  </>;
}
function ApplicationDialog({ application, formatTimestamp, onClose, onDecision, error, confirmationOpen }: { application: ProviderApplication; formatTimestamp: (value: string) => string; onClose: () => void; onDecision: (value: 'approve' | 'reject') => void; error: string | null; confirmationOpen: boolean }) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => { closeRef.current?.focus(); }, []);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape' && !confirmationOpen) onCloseRef.current(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [confirmationOpen]);
  const isPending = application.review_status === 'PENDING_REVIEW';
  const value = (input: string | number | boolean | null | undefined) => {
    if (input === null || input === undefined || input === '') return 'Not provided';
    if (typeof input === 'boolean') return input ? 'Yes' : 'No';
    return String(input);
  };
  const detail = (label: string, content: string | number | boolean | null | undefined, wide = false) =>
    <div className={`${applicationStyles.detailItem} ${wide ? applicationStyles.detailItemWide : ''}`} key={label}>
      <dt className={applicationStyles.detailLabel}>{label}</dt>
      <dd className={`${applicationStyles.detailValue} ${content === null || content === undefined || content === '' ? applicationStyles.detailValueMuted : ''}`}>{value(content)}</dd>
    </div>;
  const selectionDetail = (label: string, items: Array<{ id: string; name: string }> | null | undefined, fallback?: string[] | null) => {
    const names = items?.map((item) => item.name).filter(Boolean) ?? [];
    const selected = names.length ? names : fallback ?? [];
    return <div className={`${applicationStyles.detailItem} ${applicationStyles.detailItemWide}`} key={label}>
      <dt className={applicationStyles.detailLabel}>{label}</dt>
      <dd className={`${applicationStyles.detailValue} ${selected.length ? '' : applicationStyles.detailValueMuted}`}>
        {selected.length
          ? <span className={applicationStyles.selectionList}>{selected.map((name, index) => <span className={applicationStyles.selection} key={`${name}-${index}`}>{name}</span>)}</span>
          : 'Not provided'}
      </dd>
    </div>;
  };
  const consent = (timestamp: string | null) => timestamp ? `Accepted · ${formatTimestamp(timestamp)}` : 'Not provided';
  const focusableSelector = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  return <div className={applicationStyles.applicationBackdrop} role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(event) => { if (event.target === event.currentTarget && !confirmationOpen) onClose(); }}>
    <div className={applicationStyles.applicationPanel} onKeyDown={(event) => {
      if (event.key !== 'Tab') return;
      const nodes = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(focusableSelector));
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }}>
      <header className={applicationStyles.applicationHeader}>
        <div className={applicationStyles.headerCopy}>
          <span className={applicationStyles.eyebrow}>New provider registration</span>
          <h2 id={titleId} className={applicationStyles.applicationTitle}>Provider application</h2>
          <p className={applicationStyles.providerLine}>{application.provider_name} · {application.provider_type[0] + application.provider_type.slice(1).toLowerCase()}</p>
        </div>
        <button ref={closeRef} type="button" className={applicationStyles.closeButton} onClick={onClose} aria-label="Close application details">×</button>
      </header>
      <main className={applicationStyles.applicationContent}>
        <section className={applicationStyles.section} aria-labelledby={`${titleId}-professional`}>
          <h3 id={`${titleId}-professional`} className={applicationStyles.sectionHeading}><span className={applicationStyles.sectionIndex}>01</span> Provider &amp; professional details</h3>
          <dl className={applicationStyles.detailGrid}>
            {detail('Provider name', application.provider_name)}
            {detail('Provider type', application.provider_type[0] + application.provider_type.slice(1).toLowerCase())}
            {detail('Professional title', application.professional_title)}
            {detail('Years of experience', application.years_experience)}
            {selectionDetail('Specializations', application.specializations, application.specialization_ids)}
            {selectionDetail('Languages', application.languages)}
          </dl>
        </section>
        <section className={applicationStyles.section} aria-labelledby={`${titleId}-applicant`}>
          <h3 id={`${titleId}-applicant`} className={applicationStyles.sectionHeading}><span className={applicationStyles.sectionIndex}>02</span> Applicant &amp; contact</h3>
          <dl className={applicationStyles.detailGrid}>
            {detail('First name', application.first_name)}
            {detail('Last name', application.last_name)}
            {detail('Full name on account', application.full_name)}
            {detail('Email', application.email)}
            {detail('Mobile number', application.mobile_number)}
          </dl>
        </section>
        <section className={applicationStyles.section} aria-labelledby={`${titleId}-address`}>
          <h3 id={`${titleId}-address`} className={applicationStyles.sectionHeading}><span className={applicationStyles.sectionIndex}>03</span> Address</h3>
          <dl className={applicationStyles.detailGrid}>
            {detail('Working address', application.working_address, true)}
            {detail('City', application.city)}
            {detail('State / province', application.state_province)}
            {detail('Postal code', application.postal_code)}
            {detail('Country', application.country)}
          </dl>
        </section>
        <section className={applicationStyles.section} aria-labelledby={`${titleId}-services`}>
          <h3 id={`${titleId}-services`} className={applicationStyles.sectionHeading}><span className={applicationStyles.sectionIndex}>04</span> Services</h3>
          <dl className={applicationStyles.detailGrid}>
            {detail('Stable visits available', application.stable_visit)}
            {detail('Maximum working radius (km)', application.maximum_working_radius_km)}
            {detail('Emergency services available', application.emergency_services_available)}
            {detail('Emergency contact number', application.emergency_contact_number)}
          </dl>
        </section>
        <section className={applicationStyles.section} aria-labelledby={`${titleId}-review`}>
          <h3 id={`${titleId}-review`} className={applicationStyles.sectionHeading}><span className={applicationStyles.sectionIndex}>05</span> Consent &amp; review</h3>
          <dl className={applicationStyles.detailGrid}>
            {detail('Terms accepted', consent(application.terms_accepted_at), true)}
            {detail('Privacy accepted', consent(application.privacy_accepted_at), true)}
            {detail('Email verification', application.email_verified_at ? `Verified · ${formatTimestamp(application.email_verified_at)}` : 'Unverified', true)}
            {detail('Review status', application.review_status.replace(/_/g, ' '))}
            {detail('Submitted', formatTimestamp(application.created_at))}
            {detail('Reviewed', application.reviewed_at ? formatTimestamp(application.reviewed_at) : null)}
            {detail('Reviewed by', application.reviewed_by_name)}
            {detail('Rejection reason', application.rejection_reason, true)}
            {detail('Legacy visit classification', application.visit_stability === 'STABLE_VISIT' ? 'Stable visits' : 'Clinic-based', true)}
            {detail('Staged listing', application.provider_id ? `Draft, unpublished · ${application.provider_id}` : 'Created as a draft listing when approved', true)}
          </dl>
        </section>
      </main>
      {error && <div className={applicationStyles.applicationError}><Alert variant="error">{error}</Alert></div>}
      <footer className={applicationStyles.applicationFooter}>
        <p className={applicationStyles.footerNote}>{isPending ? 'Decisions are recorded in the activity history.' : 'This application has already been reviewed.'}</p>
        <div className={applicationStyles.footerActions}>
          {isPending && <><Button variant="danger" onClick={() => onDecision('reject')}>Reject</Button><Button variant="primary" onClick={() => onDecision('approve')}>Approve &amp; stage listing</Button></>}
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </div>
      </footer>
    </div>
  </div>;
}

function ProfileUpdateDialog({ update, formatTimestamp, onClose, onDecision, error, confirmationOpen }: { update: ProviderProfileUpdate; formatTimestamp: (value: string) => string; onClose: () => void; onDecision: (value: 'approve' | 'reject') => void; error: string | null; confirmationOpen: boolean }) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const confirmationRef = useRef(confirmationOpen);
  confirmationRef.current = confirmationOpen;
  useEffect(() => {
    closeRef.current?.focus();
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape' && !confirmationRef.current) onCloseRef.current(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
  const displayList = (items: unknown[]) => items.length ? JSON.stringify(items, null, 2) : '—';
  const proposedVisits = (
    update.proposed_profile as typeof update.proposed_profile & { visit_additions?: ProposedVisitAddition[] }
  ).visit_additions;
  const rows: Array<[string, ReactNode, ReactNode]> = [
    ['Name', update.current_profile.name, update.proposed_profile.name],
    ['Description', update.current_profile.description || '—', update.proposed_profile.description || '—'],
    ['Email', update.current_profile.email || '—', update.proposed_profile.email || '—'],
    ['Phone', update.current_profile.phone || '—', update.proposed_profile.phone || '—'],
    ['Website', update.current_profile.website || '—', update.proposed_profile.website || '—'],
    ['Visit availability', update.current_profile.visit_stability === 'STABLE_VISIT' ? 'Stable visits' : 'Clinic-based', update.proposed_profile.visit_stability === 'STABLE_VISIT' ? 'Stable visits' : 'Clinic-based'],
    ['Maximum working radius (km)', update.current_profile.maximum_working_radius_km?.toString() ?? '—', update.proposed_profile.maximum_working_radius_km?.toString() ?? '—'],
    ['Emergency services available', update.current_profile.emergency_services_available ? 'Yes' : 'No', update.proposed_profile.emergency_services_available ? 'Yes' : 'No'],
    ['Emergency contact number', update.current_profile.emergency_contact_number || '—', update.proposed_profile.emergency_contact_number || '—'],
    ['Specializations', displayList(update.current_profile.specialization_ids), displayList(update.proposed_profile.specialization_ids)],
    ['Locations', displayList(update.current_profile.locations), displayList(update.proposed_profile.locations)],
    ['Phone contacts', displayList(update.current_profile.phones), displayList(update.proposed_profile.phones)],
    ['Email contacts', displayList(update.current_profile.emails), displayList(update.proposed_profile.emails)],
    ['Professional title', update.current_profile.professional_title || '—', update.proposed_profile.professional_title || '—'],
    ['Biography', update.current_profile.biography || '—', update.proposed_profile.biography || '—'],
    ['Years of experience', update.current_profile.years_experience?.toString() || '—', update.proposed_profile.years_experience?.toString() || '—'],
    ['Experience notes', update.current_profile.experience_description || '—', update.proposed_profile.experience_description || '—'],
    ['Qualifications', displayList(update.current_profile.qualifications), displayList(update.proposed_profile.qualifications)],
    ['Visit additions', 'Existing visit history is retained.', renderVisitAdditions(proposedVisits)],
  ];
  const isPending = update.review_status === 'PENDING_REVIEW';
  const focusableSelector = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  return <div className={photoStyles.modalBackdrop} role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(event) => { if (event.target === event.currentTarget && !confirmationRef.current) onCloseRef.current(); }}>
    <div className={photoStyles.modalPanel} onKeyDown={(event) => {
      if (event.key !== 'Tab') return;
      const nodes = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(focusableSelector));
      if (!nodes.length) return;
      if (event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes[nodes.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === nodes[nodes.length - 1]) { event.preventDefault(); nodes[0].focus(); }
    }}>
      <header className={photoStyles.modalHeader}><h2 id={titleId}>Review provider profile update</h2><button ref={closeRef} type="button" className={photoStyles.close} onClick={onClose} aria-label="Close dialog" disabled={confirmationOpen}>×</button></header>
      <div className={photoStyles.modalBody}>
        <p className={photoStyles.providerMeta}><strong>{update.provider_name}</strong>{updateStatusBadge(update.review_status)}<span>Submitted {formatTimestamp(update.submitted_at)}</span></p>
        {update.rejection_reason && <Alert variant="error">Previous decision: {update.rejection_reason}</Alert>}
        <ProviderPhotoComparison current={update.current_profile.photos} proposed={update.proposed_profile.photos} />
        <div className={photoStyles.tableWrap}><table className={photoStyles.compareTable}>
          <thead><tr><th>Field</th><th>Current approved</th><th>Proposed</th></tr></thead>
          <tbody>{rows.map(([label, current, proposed]) => <tr key={label}><th scope="row">{label}</th><td>{current}</td><td style={{ fontWeight: current === proposed ? undefined : 700 }}>{proposed}</td></tr>)}</tbody>
        </table></div>
        <p className={photoStyles.scopeNote}>Reviewing this update changes only the submitted profile update. It does not change the provider’s active status, publication status, or account state.</p>
      </div>
      {error && <div style={{ padding: '0 24px 12px' }}><Alert variant="error">{error}</Alert></div>}
      <footer className={photoStyles.modalFooter}>
        {isPending && <><Button variant="danger" onClick={() => onDecision('reject')} disabled={confirmationOpen}>Reject update</Button><Button variant="primary" onClick={() => onDecision('approve')} disabled={confirmationOpen}>Approve update</Button></>}
        <Button variant="ghost" onClick={onClose} disabled={confirmationOpen}>Close</Button>
      </footer>
    </div>
  </div>;
}
function DecisionDialog({ action, providerName, busy, onCancel, onConfirm }: { action: 'approve' | 'reject'; providerName: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const titleId = useId();
  const confirmationRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef(onCancel);
  cancelRef.current = onCancel;
  const busyRef = useRef(busy);
  busyRef.current = busy;
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    confirmationRef.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busyRef.current) {
        event.stopPropagation();
        cancelRef.current();
      }
    };
    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);
  const approving = action === 'approve';
  return <div className={`${applicationStyles.applicationBackdrop} ${applicationStyles.decisionBackdrop}`} role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
    <div className={`${applicationStyles.applicationPanel} ${applicationStyles.decisionPanel}`} onKeyDown={(event) => {
      if (event.key !== 'Tab') return;
      const nodes = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'));
      if (!nodes.length) return;
      if (event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes[nodes.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === nodes[nodes.length - 1]) { event.preventDefault(); nodes[0].focus(); }
    }}>
      <header className={applicationStyles.applicationHeader}><h2 id={titleId} className={applicationStyles.applicationTitle}>{approving ? 'Approve provider application?' : 'Reject provider application?'}</h2></header>
      <div className={applicationStyles.decisionBody}>
        <p>{approving ? `Approving ${providerName} will enable its account and create one draft, unpublished directory listing.` : `Rejecting ${providerName} will prevent provider access and listing creation.`}</p>
        <p>This decision is recorded in the activity history.</p>
      </div>
      <footer className={applicationStyles.applicationFooter}><div className={applicationStyles.footerActions}><Button variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button><Button ref={confirmationRef} variant={approving ? 'primary' : 'danger'} onClick={onConfirm} loading={busy}>{approving ? 'Approve application' : 'Reject application'}</Button></div></footer>
    </div>
  </div>;
}

function ProfileUpdateDecisionDialog({ action, providerName, busy, onCancel, onConfirm }: { action: 'approve' | 'reject'; providerName: string; busy: boolean; onCancel: () => void; onConfirm: (reason?: string) => void }) {
  const titleId = useId();
  const confirmationRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [reason, setReason] = useState('');
  const confirmLock = useRef(false);
  const busyRef = useRef(busy);
  busyRef.current = busy;
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    confirmationRef.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busyRef.current) { event.stopPropagation(); onCancelRef.current(); }
    };
    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);
  const approving = action === 'approve';
  return <div className={`${photoStyles.modalBackdrop} ${photoStyles.nestedBackdrop}`} role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
    <div className={photoStyles.modalPanel} onKeyDown={(event) => {
      if (event.key !== 'Tab') return;
      const nodes = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), textarea:not([disabled])'));
      if (!nodes.length) return;
      if (event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes[nodes.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === nodes[nodes.length - 1]) { event.preventDefault(); nodes[0].focus(); }
    }}>
      <header className={photoStyles.modalHeader}><h2 id={titleId}>{approving ? 'Approve profile update?' : 'Reject profile update?'}</h2></header>
      <div className={photoStyles.decisionText}>
        <p>{approving ? `Approving ${providerName}'s submitted profile update applies its proposed profile changes.` : `Rejecting ${providerName}'s submitted profile update leaves the approved profile unchanged.`}</p>
        <p>This review does not change the provider’s active status, publication status, or account state.</p>
        {!approving && <label style={{ display: 'grid', gap: 6, marginTop: 16 }}>Feedback for the provider (optional)<textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} maxLength={500} /></label>}
        <p>This decision is recorded in the activity history.</p>
      </div>
      <footer className={photoStyles.modalFooter}><Button ref={cancelRef} variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button><Button ref={confirmationRef} variant={approving ? 'primary' : 'danger'} onClick={() => { if (busy || confirmLock.current) return; confirmLock.current = true; onConfirm(approving ? undefined : reason.trim() || undefined); }} loading={busy}>{approving ? 'Approve update' : 'Reject update'}</Button></footer>
    </div>
  </div>;
}
