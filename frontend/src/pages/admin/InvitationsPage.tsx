import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { cancelInvitation, listInvitations, resendInvitation } from '@/api/invitations';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { CreateInvitationDialog } from '@/components/admin/CreateInvitationDialog';
import { PageHeader } from '@/components/layout/PageHeader';
import { ActionMenu, type ActionMenuItem } from '@/components/ui/ActionMenu';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Input } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import type { Invitation, InvitationStatus, LoadingState, PaginatedResponse, ProviderType } from '@/types';
import styles from './InvitationsPage.module.css';

const statuses: InvitationStatus[] = ['PENDING', 'ACCEPTED', 'EXPIRED', 'CANCELLED', 'COMPLETED'];
const providerTypes: ProviderType[] = ['HOSPITAL', 'CLINIC', 'DOCTOR'];

const STATUS_LABELS: Record<InvitationStatus, string> = {
  PENDING: 'Pending', ACCEPTED: 'Accepted', EXPIRED: 'Expired', CANCELLED: 'Cancelled', COMPLETED: 'Completed',
};
const TYPE_LABELS: Record<ProviderType, string> = { HOSPITAL: 'Hospital', CLINIC: 'Clinic', DOCTOR: 'Doctor' };

function providerDisplay(item: Invitation): string {
  return item.provider_name || `New — ${TYPE_LABELS[item.provider_type]}`;
}

function statusVariant(status: InvitationStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  const variants: Record<InvitationStatus, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
    PENDING: 'warning',
    ACCEPTED: 'info',
    EXPIRED: 'neutral',
    CANCELLED: 'error',
    COMPLETED: 'success',
  };
  return variants[status];
}

export function InvitationsPage() {
  const { formatTimestamp } = useTimeSettings();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') ?? '';
  const status = searchParams.get('status') as InvitationStatus | null;
  const providerType = searchParams.get('provider_type') as ProviderType | null;
  const dateFrom = searchParams.get('date_from') ?? '';
  const dateTo = searchParams.get('date_to') ?? '';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pageSize = [10, 25, 100].includes(Number(searchParams.get('page_size'))) ? Number(searchParams.get('page_size')) : 10;

  const [result, setResult] = useState<PaginatedResponse<Invitation> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailTarget, setDetailTarget] = useState<Invitation | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Invitation | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ message: string; variant: 'success' | 'error' | 'info' } | null>(null);
  // Raw invitation links are only returned by create/resend, never by the
  // list endpoint — remember them for the session so Copy Link can work.
  const [linkById, setLinkById] = useState<Record<string, string>>({});
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filterPanelRef = useRef<HTMLDivElement>(null);

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    setSearchParams(next);
  }, [searchParams, setSearchParams]);

  const load = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const response = await listInvitations({
        search: search || undefined,
        status: status ?? undefined,
        provider_type: providerType ?? undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: pageSize,
      });
      if (page > 1 && response.meta.total_pages > 0 && page > response.meta.total_pages) {
        updateParams({ page: '1' });
        return;
      }
      setResult(response);
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load invitations.'));
      setLoadState('error');
    }
  }, [dateFrom, dateTo, page, pageSize, providerType, search, status, updateParams]);

  useEffect(() => { void load(); }, [load]);

  async function resend(invitation: Invitation) {
    setActionId(invitation.id);
    try {
      const updated = await resendInvitation(invitation.id);
      if (updated.invitation_url) setLinkById((prev) => ({ ...prev, [updated.id]: updated.invitation_url as string }));
      setNotice({ message: `A new invitation email was sent to ${invitation.recipient_email}.`, variant: 'success' });
      void load();
    } catch (err) {
      setNotice({ message: extractErrorMessage(err, 'Unable to resend this invitation.'), variant: 'error' });
    } finally {
      setActionId(null);
    }
  }

  async function confirmCancel() {
    if (!cancelTarget) return;
    setActionId(cancelTarget.id);
    try {
      await cancelInvitation(cancelTarget.id);
      setNotice({ message: `Invitation for ${cancelTarget.recipient_email} was cancelled.`, variant: 'success' });
      setCancelTarget(null);
      void load();
    } catch (err) {
      setNotice({ message: extractErrorMessage(err, 'Unable to cancel this invitation.'), variant: 'error' });
    } finally {
      setActionId(null);
    }
  }

  async function copyLink(invitation: Invitation) {
    const url = linkById[invitation.id] ?? invitation.invitation_url;
    if (!url) {
      setNotice({ message: 'For security, invitation links are only available right after they are created or resent. Use Resend to generate a fresh link.', variant: 'info' });
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      setNotice({ message: 'Invitation link copied to the clipboard.', variant: 'success' });
    } catch {
      setNotice({ message: 'Unable to copy the invitation link. Please try again.', variant: 'error' });
    }
  }

  const columns: DataTableColumn<Invitation>[] = [
    { key: 'recipient_email', label: 'Recipient', width: '1.5fr', render: (item) => <strong>{item.recipient_email}</strong> },
    { key: 'provider_type', label: 'Provider type', width: '120px', render: (item) => TYPE_LABELS[item.provider_type] },
    { key: 'provider', label: 'Provider', width: '1.3fr', hideOnMobile: true, render: (item) => providerDisplay(item) },
    { key: 'status', label: 'Status', width: '110px', render: (item) => <Badge size="sm" variant={statusVariant(item.status)}>{STATUS_LABELS[item.status]}</Badge> },
    { key: 'sent_at', label: 'Sent', width: '150px', hideOnMobile: true, render: (item) => formatTimestamp(item.sent_at) },
    { key: 'expires_at', label: 'Expires', width: '150px', hideOnMobile: true, render: (item) => formatTimestamp(item.expires_at) },
    {
      key: 'actions', label: 'Actions', width: '70px', align: 'right',
      render: (item) => {
        const actions: ActionMenuItem[] = [{ label: 'View', onSelect: () => setDetailTarget(item) }];
        if (item.status === 'COMPLETED' && item.provider_id) {
          actions.push({
            label: 'View submitted details',
            icon: '👁',
            onSelect: () => navigate(`/admin/providers/${item.provider_id}`),
          });
        }
        if (item.status === 'PENDING' || item.status === 'EXPIRED') actions.push({ label: actionId === item.id ? 'Resending…' : 'Resend', disabled: actionId === item.id, onSelect: () => void resend(item) });
        if (item.status === 'PENDING') actions.push({ label: 'Cancel', danger: true, onSelect: () => setCancelTarget(item) });
        if (item.status === 'PENDING' || item.status === 'ACCEPTED') actions.push({ label: 'Copy Link', onSelect: () => void copyLink(item) });
        return <ActionMenu items={actions} ariaLabel={`Actions for ${item.recipient_email}`} />;
      },
    },
  ];

  const hasFilters = Boolean(search || status || providerType || dateFrom || dateTo);
  const isUnfilteredEmpty =
    loadState === 'success' &&
    result !== null &&
    result.meta.total === 0 &&
    !hasFilters;
  const showListControls = !isUnfilteredEmpty;
  const activeChips: { label: string; onClear: () => void }[] = [];
  if (status) {
    activeChips.push({
      label: `Status: ${STATUS_LABELS[status]}`,
      onClear: () => updateParams({ status: null, page: '1' }),
    });
  }
  if (providerType) {
    activeChips.push({
      label: `Type: ${TYPE_LABELS[providerType]}`,
      onClear: () => updateParams({ provider_type: null, page: '1' }),
    });
  }
  if (dateFrom) {
    activeChips.push({
      label: `Sent from: ${dateFrom}`,
      onClear: () => updateParams({ date_from: null, page: '1' }),
    });
  }
  if (dateTo) {
    activeChips.push({
      label: `Sent to: ${dateTo}`,
      onClear: () => updateParams({ date_to: null, page: '1' }),
    });
  }

  const filterGroups = [
    {
      label: 'Invitation status',
      value: status ?? 'all',
      onChange: (value: string) => updateParams({ status: value === 'all' ? null : value, page: '1' }),
      options: [
        { value: 'all', label: 'All' },
        ...statuses.map((value) => ({ value, label: STATUS_LABELS[value] })),
      ],
    },
    {
      label: 'Provider type',
      value: providerType ?? 'all',
      onChange: (value: string) => updateParams({ provider_type: value === 'all' ? null : value, page: '1' }),
      options: [
        { value: 'all', label: 'All types' },
        ...providerTypes.map((value) => ({ value, label: TYPE_LABELS[value] })),
      ],
    },
  ];

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Invitations"
        subtitle="Invite providers and track their onboarding progress."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Invitations' }]}
        actions={<Button variant="primary" leftIcon="＋" onClick={() => setCreateOpen(true)}>New Invitation</Button>}
      />
      <div className={styles.body}>
        {notice && <Alert variant={notice.variant} onDismiss={() => setNotice(null)}>{notice.message}</Alert>}
        {showListControls && (
          <>
            <div className={styles.toolbar}>
              <SearchInput value={search} onChange={(value) => updateParams({ search: value || null, page: '1' })} placeholder="Search recipient or provider…" delay={300} containerClassName={styles.search} />
              <button
                type="button"
                className={`${styles.filterToggle} ${filtersOpen ? styles['filterToggle--open'] : ''} ${activeChips.length > 0 && !filtersOpen ? styles['filterToggle--active'] : ''}`}
                onClick={() => setFiltersOpen((open) => !open)}
                aria-expanded={filtersOpen}
                aria-controls="invitation-filter-panel"
              >
                <span className={styles.filterToggleIcon}>⊟</span>
                Filters
                {activeChips.length > 0 && (
                  <span className={styles.filterCount}>{activeChips.length}</span>
                )}
                <span className={`${styles.chevron} ${filtersOpen ? styles['chevron--up'] : ''}`}>▾</span>
              </button>

              {!filtersOpen && activeChips.length > 0 && (
                <div className={styles.activeChips} aria-label="Active filters">
                  {activeChips.map((chip) => (
                    <button
                      key={chip.label}
                      type="button"
                      className={styles.chip}
                      onClick={chip.onClear}
                      title={`Remove filter: ${chip.label}`}
                    >
                      {chip.label}
                      <span className={styles.chipClose} aria-hidden="true">✕</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div
              id="invitation-filter-panel"
              ref={filterPanelRef}
              className={`${styles.filterPanel} ${filtersOpen ? styles['filterPanel--open'] : ''}`}
              aria-hidden={!filtersOpen}
            >
              {filtersOpen && (
                <div className={styles.filterPanelInner}>
                  <FilterBar groups={filterGroups} />
                  <div className={styles.dateFilters} role="group" aria-label="Sent date range">
                    <label className={styles.dateLabel}>
                      Sent from
                      <Input type="date" value={dateFrom} onChange={(event) => updateParams({ date_from: event.target.value || null, page: '1' })} />
                    </label>
                    <label className={styles.dateLabel}>
                      to
                      <Input type="date" value={dateTo} onChange={(event) => updateParams({ date_to: event.target.value || null, page: '1' })} />
                    </label>
                  </div>
                  {hasFilters && (
                    <button
                      type="button"
                      className={styles.clearAll}
                      onClick={() => updateParams({ search: null, status: null, provider_type: null, date_from: null, date_to: null, page: null })}
                    >
                      Clear all filters
                    </button>
                  )}
                </div>
              )}
            </div>
          </>
        )}
        <DataTable
          ariaLabel="Provider invitations" columns={columns} data={result?.data ?? []} page={page} pageSize={pageSize}
          rowKey={(item) => item.id} loading={loadState === 'loading'} loadingLabel="Loading invitations…"
          error={loadState === 'error' ? { title: 'Failed to load invitations', message: errorMessage ?? undefined, onRetry: load } : null}
          empty={{ icon: '📩', title: hasFilters ? 'No invitations found' : 'No invitations yet', description: hasFilters ? 'Try adjusting your search or filters.' : 'Send an invitation to begin onboarding a provider.', action: !hasFilters ? <Button variant="primary" onClick={() => setCreateOpen(true)}>New Invitation</Button> : undefined }}
        />
        {showListControls && loadState === 'success' && result && <Pagination page={page} pageSize={pageSize} total={result.meta.total} onPageChange={(next) => updateParams({ page: String(next) })} onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })} />}
      </div>
      {createOpen && (
        <CreateInvitationDialog
          onCancel={() => setCreateOpen(false)}
          onDeliveryFailure={() => void load()}
          onSuccess={(invitation) => {
            setCreateOpen(false);
            if (invitation.invitation_url) setLinkById((prev) => ({ ...prev, [invitation.id]: invitation.invitation_url as string }));
            setNotice({ message: 'Invitation sent successfully.', variant: 'success' });
            void load();
          }}
        />
      )}
      <ConfirmDialog open={Boolean(cancelTarget)} title="Cancel invitation?" message={cancelTarget ? `This will invalidate the invitation sent to ${cancelTarget.recipient_email}.` : undefined} confirmLabel={actionId ? 'Cancelling…' : 'Cancel invitation'} danger onCancel={() => setCancelTarget(null)} onConfirm={() => void confirmCancel()} />
      {detailTarget && <InvitationDetailDialog invitation={detailTarget} onClose={() => setDetailTarget(null)} />}
    </div>
  );
}

function InvitationDetailDialog({ invitation, onClose }: { invitation: Invitation; onClose: () => void }) {
  const { formatTimestamp } = useTimeSettings();
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { closeRef.current?.focus(); }, []);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);
  return <div className={styles.detailBackdrop} role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className={styles.detailPanel}>
      <header><h2 id={titleId}>Invitation details</h2><button ref={closeRef} type="button" onClick={onClose} aria-label="Close dialog">✕</button></header>
      <dl className={styles.details}>
        <dt>Recipient</dt><dd>{invitation.recipient_email}</dd>
        <dt>Provider type</dt><dd>{TYPE_LABELS[invitation.provider_type]}</dd>
        <dt>Provider</dt><dd>{providerDisplay(invitation)}</dd>
        <dt>Status</dt><dd><Badge size="sm" variant={statusVariant(invitation.status)}>{STATUS_LABELS[invitation.status]}</Badge></dd>
        <dt>Sent</dt><dd>{formatTimestamp(invitation.sent_at)}</dd>
        <dt>Expires</dt><dd>{formatTimestamp(invitation.expires_at)}</dd>
        {invitation.accepted_at && <><dt>Accepted</dt><dd>{formatTimestamp(invitation.accepted_at)}</dd></>}
        {invitation.completed_at && <><dt>Completed</dt><dd>{formatTimestamp(invitation.completed_at)}</dd></>}
      </dl>
      <footer><Button variant="primary" onClick={onClose}>Close</Button></footer>
    </div>
  </div>;
}