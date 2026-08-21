import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { approveUser, listAdminUsers, rejectUser } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { PageHeader } from '@/components/layout/PageHeader';
import { ActionMenu, type ActionMenuItem } from '@/components/ui/ActionMenu';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import type { AdminUser, LoadingState, PaginatedResponse, RegistrantApprovalStatus } from '@/types';
import styles from './UsersPage.module.css';

// ── Constants ──────────────────────────────────────────────────────────────

const APPROVAL_STATUSES: RegistrantApprovalStatus[] = ['PENDING', 'APPROVED', 'REJECTED'];

const APPROVAL_LABELS: Record<RegistrantApprovalStatus, string> = {
  PENDING: 'Pending',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
};

const ROLE_OPTIONS = [
  { value: 'all', label: 'All roles' },
  { value: 'horse_owner', label: 'Horse Owner' },
  { value: 'stable_manager', label: 'Stable Manager' },
];

function approvalVariant(
  status: RegistrantApprovalStatus
): 'warning' | 'success' | 'error' {
  if (status === 'PENDING') return 'warning';
  if (status === 'APPROVED') return 'success';
  return 'error';
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(new Date(value));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

// ── Page ───────────────────────────────────────────────────────────────────

export function UsersPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const search = searchParams.get('search') ?? '';
  const approvalStatus = searchParams.get('approval_status') as RegistrantApprovalStatus | null;
  const role = searchParams.get('role') ?? '';
  const emailVerifiedParam = searchParams.get('email_verified');
  const emailVerified =
    emailVerifiedParam === 'true'
      ? true
      : emailVerifiedParam === 'false'
        ? false
        : undefined;
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pageSize = [10, 25, 100].includes(Number(searchParams.get('page_size')))
    ? Number(searchParams.get('page_size'))
    : 10;

  const [result, setResult] = useState<PaginatedResponse<AdminUser> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [notice, setNotice] = useState<{
    message: string;
    variant: 'success' | 'error' | 'info';
  } | null>(null);

  const [detailTarget, setDetailTarget] = useState<AdminUser | null>(null);
  const [approveTarget, setApproveTarget] = useState<AdminUser | null>(null);
  const [rejectTarget, setRejectTarget] = useState<AdminUser | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);

  const [filtersOpen, setFiltersOpen] = useState(false);
  const filterPanelRef = useRef<HTMLDivElement>(null);

  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      Object.entries(updates).forEach(([key, value]) =>
        value ? next.set(key, value) : next.delete(key)
      );
      setSearchParams(next);
    },
    [searchParams, setSearchParams]
  );

  const load = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const response = await listAdminUsers({
        search: search || undefined,
        approval_status: approvalStatus ?? undefined,
        role: role || undefined,
        email_verified: emailVerified,
        page,
        page_size: pageSize,
      });
      if (
        page > 1 &&
        response.meta.total_pages > 0 &&
        page > response.meta.total_pages
      ) {
        updateParams({ page: '1' });
        return;
      }
      setResult(response);
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load users.'));
      setLoadState('error');
    }
  }, [search, approvalStatus, role, emailVerified, page, pageSize, updateParams]);

  useEffect(() => {
    void load();
  }, [load]);

  async function confirmApprove() {
    if (!approveTarget) return;
    setActionId(approveTarget.id);
    try {
      await approveUser(approveTarget.id);
      setNotice({
        message: `${approveTarget.full_name} has been approved.`,
        variant: 'success',
      });
      setApproveTarget(null);
      void load();
    } catch (err) {
      setNotice({
        message: extractErrorMessage(err, 'Unable to approve this user.'),
        variant: 'error',
      });
    } finally {
      setActionId(null);
    }
  }

  async function confirmReject() {
    if (!rejectTarget) return;
    setActionId(rejectTarget.id);
    try {
      await rejectUser(rejectTarget.id);
      setNotice({
        message: `${rejectTarget.full_name} has been rejected.`,
        variant: 'success',
      });
      setRejectTarget(null);
      void load();
    } catch (err) {
      setNotice({
        message: extractErrorMessage(err, 'Unable to reject this user.'),
        variant: 'error',
      });
    } finally {
      setActionId(null);
    }
  }

  const columns: DataTableColumn<AdminUser>[] = [
    {
      key: 'full_name',
      label: 'Name',
      width: '1.4fr',
      render: (item) => (
        <span className={styles.nameCell}>
          <strong>{item.full_name}</strong>
        </span>
      ),
    },
    {
      key: 'email',
      label: 'Email',
      width: '1.6fr',
      render: (item) => (
        <span className={styles.emailCell}>{item.email}</span>
      ),
    },
    {
      key: 'mobile_number',
      label: 'Mobile',
      width: '130px',
      hideOnMobile: true,
      render: (item) => item.mobile_number ?? '—',
    },
    {
      key: 'roles',
      label: 'Roles',
      width: '1fr',
      hideOnMobile: true,
      render: (item) =>
        item.roles.length > 0 ? (
          <span className={styles.roleList}>
            {item.roles.map((r) => (
              <Badge key={r} size="sm" variant="info">
                {r.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
              </Badge>
            ))}
          </span>
        ) : (
          <span className={styles.muted}>—</span>
        ),
    },
    {
      key: 'country',
      label: 'Country',
      width: '110px',
      hideOnMobile: true,
      render: (item) => item.country ?? '—',
    },
    {
      key: 'city',
      label: 'City',
      width: '110px',
      hideOnMobile: true,
      render: (item) => item.city ?? '—',
    },
    {
      key: 'email_verified_at',
      label: 'Email verified',
      width: '120px',
      hideOnMobile: true,
      render: (item) =>
        item.email_verified_at ? (
          <Badge size="sm" variant="success">Verified</Badge>
        ) : (
          <Badge size="sm" variant="neutral">Unverified</Badge>
        ),
    },
    {
      key: 'approval_status',
      label: 'Approval',
      width: '110px',
      render: (item) => (
        <Badge size="sm" variant={approvalVariant(item.approval_status)}>
          {APPROVAL_LABELS[item.approval_status]}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      label: 'Registered',
      width: '110px',
      hideOnMobile: true,
      render: (item) => (
        <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      width: '70px',
      align: 'right',
      render: (item) => {
        const actions: ActionMenuItem[] = [
          { label: 'View details', onSelect: () => setDetailTarget(item) },
        ];
        if (item.approval_status === 'PENDING') {
          actions.push({
            label: actionId === item.id ? 'Approving…' : 'Approve',
            icon: '✔',
            disabled: actionId === item.id,
            onSelect: () => setApproveTarget(item),
          });
          actions.push({
            label: actionId === item.id ? 'Rejecting…' : 'Reject',
            icon: '✕',
            danger: true,
            disabled: actionId === item.id,
            onSelect: () => setRejectTarget(item),
          });
        }
        return (
          <ActionMenu
            items={actions}
            ariaLabel={`Actions for ${item.full_name}`}
          />
        );
      },
    },
  ];

  const hasFilters = Boolean(search || approvalStatus || role || emailVerified !== undefined);

  const activeChips: { label: string; onClear: () => void }[] = [];
  if (approvalStatus) {
    activeChips.push({
      label: `Approval: ${APPROVAL_LABELS[approvalStatus]}`,
      onClear: () => updateParams({ approval_status: null, page: '1' }),
    });
  }
  if (role) {
    const roleLabel =
      ROLE_OPTIONS.find((o) => o.value === role)?.label ?? role;
    activeChips.push({
      label: `Role: ${roleLabel}`,
      onClear: () => updateParams({ role: null, page: '1' }),
    });
  }
  if (emailVerified !== undefined) {
    activeChips.push({
      label: `Email: ${emailVerified ? 'Verified' : 'Unverified'}`,
      onClear: () => updateParams({ email_verified: null, page: '1' }),
    });
  }

  const filterGroups = [
    {
      label: 'Approval status',
      value: approvalStatus ?? 'all',
      onChange: (value: string) =>
        updateParams({
          approval_status: value === 'all' ? null : value,
          page: '1',
        }),
      options: [
        { value: 'all', label: 'All' },
        ...APPROVAL_STATUSES.map((s) => ({
          value: s,
          label: APPROVAL_LABELS[s],
        })),
      ],
    },
    {
      label: 'Role',
      value: role || 'all',
      onChange: (value: string) =>
        updateParams({ role: value === 'all' ? null : value, page: '1' }),
      options: ROLE_OPTIONS,
    },
    {
      label: 'Email verification',
      value: emailVerified === undefined ? 'all' : String(emailVerified),
      onChange: (value: string) =>
        updateParams({
          email_verified: value === 'all' ? null : value,
          page: '1',
        }),
      options: [
        { value: 'all', label: 'All accounts' },
        { value: 'true', label: 'Verified' },
        { value: 'false', label: 'Unverified' },
      ],
    },
  ];

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Registered Users"
        subtitle="Review and manage public registrant accounts."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Users' }]}
      />
      <div className={styles.body}>
        {notice && (
          <Alert variant={notice.variant} onDismiss={() => setNotice(null)}>
            {notice.message}
          </Alert>
        )}

        {/* ── Toolbar ──────────────────────────────────────── */}
        <div className={styles.toolbar}>
          <SearchInput
            value={search}
            onChange={(value) =>
              updateParams({ search: value || null, page: '1' })
            }
            placeholder="Search name or email…"
            delay={300}
            containerClassName={styles.search}
          />
          <button
            type="button"
            className={[
              styles.filterToggle,
              filtersOpen ? styles['filterToggle--open'] : '',
              activeChips.length > 0 && !filtersOpen
                ? styles['filterToggle--active']
                : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
            aria-controls="users-filter-panel"
          >
            <span className={styles.filterToggleIcon}>⊟</span>
            Filters
            {activeChips.length > 0 && (
              <span className={styles.filterCount}>{activeChips.length}</span>
            )}
            <span
              className={[
                styles.chevron,
                filtersOpen ? styles['chevron--up'] : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              ▾
            </span>
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
                  <span className={styles.chipClose} aria-hidden="true">
                    ✕
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Collapsible filter panel ──────────────────────── */}
        <div
          id="users-filter-panel"
          ref={filterPanelRef}
          className={[
            styles.filterPanel,
            filtersOpen ? styles['filterPanel--open'] : '',
          ]
            .filter(Boolean)
            .join(' ')}
          aria-hidden={!filtersOpen}
        >
          {filtersOpen && (
            <div className={styles.filterPanelInner}>
              <FilterBar groups={filterGroups} />
              {hasFilters && (
                <button
                  type="button"
                  className={styles.clearAll}
                  onClick={() =>
                    updateParams({
                      search: null,
                      approval_status: null,
                      role: null,
                      email_verified: null,
                      page: null,
                    })
                  }
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}
        </div>

        {/* ── Table ──────────────────────────────────────────── */}
        <DataTable
          ariaLabel="Registered users"
          columns={columns}
          data={result?.data ?? []}
          page={page}
          pageSize={pageSize}
          rowKey={(item) => item.id}
          loading={loadState === 'loading'}
          loadingLabel="Loading users…"
          error={
            loadState === 'error'
              ? {
                  title: 'Failed to load users',
                  message: errorMessage ?? undefined,
                  onRetry: load,
                }
              : null
          }
          empty={{
            icon: '👤',
            title: hasFilters ? 'No users found' : 'No registered users yet',
            description: hasFilters
              ? 'Try adjusting your search or filters.'
              : 'Registered accounts will appear here.',
          }}
        />

        {/* ── Pagination ────────────────────────────────────── */}
        {loadState === 'success' && result && (
          <Pagination
            page={page}
            pageSize={pageSize}
            total={result.meta.total}
            onPageChange={(next) => updateParams({ page: String(next) })}
            onPageSizeChange={(size) =>
              updateParams({ page_size: String(size), page: '1' })
            }
          />
        )}
      </div>

      {/* ── Approve confirm dialog ─────────────────────────── */}
      <ConfirmDialog
        open={Boolean(approveTarget)}
        title="Approve this user?"
        message={
          approveTarget
            ? `${approveTarget.full_name} (${approveTarget.email}) will be granted access to the portal.`
            : undefined
        }
        confirmLabel={actionId ? 'Approving…' : 'Approve'}
        cancelLabel="Cancel"
        onCancel={() => setApproveTarget(null)}
        onConfirm={() => void confirmApprove()}
      />

      {/* ── Reject confirm dialog ──────────────────────────── */}
      <ConfirmDialog
        open={Boolean(rejectTarget)}
        title="Reject this user?"
        message={
          rejectTarget
            ? `${rejectTarget.full_name} (${rejectTarget.email}) will be denied access to the portal.`
            : undefined
        }
        confirmLabel={actionId ? 'Rejecting…' : 'Reject'}
        cancelLabel="Cancel"
        danger
        onCancel={() => setRejectTarget(null)}
        onConfirm={() => void confirmReject()}
      />

      {/* ── Detail dialog ──────────────────────────────────── */}
      {detailTarget && (
        <UserDetailDialog
          user={detailTarget}
          onClose={() => setDetailTarget(null)}
          onApprove={
            detailTarget.approval_status === 'PENDING'
              ? () => {
                  setDetailTarget(null);
                  setApproveTarget(detailTarget);
                }
              : undefined
          }
          onReject={
            detailTarget.approval_status === 'PENDING'
              ? () => {
                  setDetailTarget(null);
                  setRejectTarget(detailTarget);
                }
              : undefined
          }
        />
      )}
    </div>
  );
}

// ── Detail dialog ──────────────────────────────────────────────────────────

interface UserDetailDialogProps {
  user: AdminUser;
  onClose: () => void;
  onApprove?: () => void;
  onReject?: () => void;
}

function UserDetailDialog({
  user,
  onClose,
  onApprove,
  onReject,
}: UserDetailDialogProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className={styles.detailBackdrop}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className={styles.detailPanel}>
        <header className={styles.detailHeader}>
          <h2 id={titleId} className={styles.detailTitle}>
            User details
          </h2>
          <button
            ref={closeRef}
            type="button"
            className={styles.detailClose}
            onClick={onClose}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </header>

        <dl className={styles.details}>
          <dt>Full name</dt>
          <dd>{user.full_name}</dd>

          <dt>Email</dt>
          <dd>{user.email}</dd>

          <dt>Mobile</dt>
          <dd>{user.mobile_number ?? '—'}</dd>

          <dt>Roles</dt>
          <dd>
            {user.roles.length > 0 ? (
              <span className={styles.roleList}>
                {user.roles.map((r) => (
                  <Badge key={r} size="sm" variant="info">
                    {r
                      .replace(/_/g, ' ')
                      .replace(/\b\w/g, (c) => c.toUpperCase())}
                  </Badge>
                ))}
              </span>
            ) : (
              '—'
            )}
          </dd>

          <dt>Country</dt>
          <dd>{user.country ?? '—'}</dd>

          <dt>City</dt>
          <dd>{user.city ?? '—'}</dd>

          <dt>Email verified</dt>
          <dd>
            {user.email_verified_at ? (
              <>
                <Badge size="sm" variant="success">
                  Verified
                </Badge>{' '}
                <span className={styles.muted}>
                  {formatDateTime(user.email_verified_at)}
                </span>
              </>
            ) : (
              <Badge size="sm" variant="neutral">
                Unverified
              </Badge>
            )}
          </dd>

          <dt>Approval</dt>
          <dd>
            <Badge size="sm" variant={approvalVariant(user.approval_status)}>
              {APPROVAL_LABELS[user.approval_status]}
            </Badge>
          </dd>

          {user.approval_decided_at && (
            <>
              <dt>Decision recorded</dt>
              <dd>
                <time dateTime={user.approval_decided_at}>
                  {formatDateTime(user.approval_decided_at)}
                </time>
              </dd>
            </>
          )}

          <dt>Registered</dt>
          <dd>
            <time dateTime={user.created_at}>
              {formatDateTime(user.created_at)}
            </time>
          </dd>
        </dl>

        <footer className={styles.detailFooter}>
          {onApprove && (
            <Button variant="primary" onClick={onApprove}>
              Approve
            </Button>
          )}
          {onReject && (
            <Button variant="danger" onClick={onReject}>
              Reject
            </Button>
          )}
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </footer>
      </div>
    </div>
  );
}
