import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { listAdminUsers } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { ActionMenu, type ActionMenuItem } from '@/components/ui/ActionMenu';
import { ViewIcon } from '@/components/ui/AdminIcons';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import type { AdminUser, LoadingState, PaginatedResponse } from '@/types';
import styles from './UsersPage.module.css';

const ROLE_OPTIONS = [
  { value: 'all', label: 'All roles' },
  { value: 'horse_owner', label: 'Horse Owner' },
  { value: 'stable_manager', label: 'Stable Manager' },
];


export function UsersPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') ?? '';
  const role = searchParams.get('role') ?? '';
  const emailVerifiedParam = searchParams.get('email_verified');
  const emailVerified =
    emailVerifiedParam === 'true' ? true : emailVerifiedParam === 'false' ? false : undefined;
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pageSize = [10, 25, 100].includes(Number(searchParams.get('page_size')))
    ? Number(searchParams.get('page_size'))
    : 10;

  const [result, setResult] = useState<PaginatedResponse<AdminUser> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [detailTarget, setDetailTarget] = useState<AdminUser | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filterPanelRef = useRef<HTMLDivElement>(null);

  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      Object.entries(updates).forEach(([key, value]) => {
        if (value) next.set(key, value);
        else next.delete(key);
      });
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
        role: role || undefined,
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
      setErrorMessage(extractErrorMessage(error, 'Failed to load registered accounts.'));
      setLoadState('error');
    }
  }, [search, role, emailVerified, page, pageSize, updateParams]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: DataTableColumn<AdminUser>[] = [
    {
      key: 'full_name',
      label: 'Name',
      width: '1.4fr',
      render: (item) => <strong>{item.full_name}</strong>,
    },
    {
      key: 'email',
      label: 'Email',
      width: '1.6fr',
      render: (item) => <span className={styles.emailCell}>{item.email}</span>,
    },
    {
      key: 'roles',
      label: 'Roles',
      width: '1fr',
      hideOnMobile: true,
      render: (item) => (
        <span className={styles.roleList}>
          {item.roles.map((name) => (
            <Badge key={name} size="sm" variant="info">
              {name.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())}
            </Badge>
          ))}
        </span>
      ),
    },
    {
      key: 'email_verified_at',
      label: 'Email verified',
      width: '130px',
      hideOnMobile: true,
      render: (item) =>
        item.email_verified_at ? (
          <Badge size="sm" variant="success">Verified</Badge>
        ) : (
          <Badge size="sm" variant="neutral">Unverified</Badge>
        ),
    },
    {
      key: 'created_at',
      label: 'Registered',
      width: '110px',
      hideOnMobile: true,
      render: (item) => <time dateTime={item.created_at}>{formatTimestamp(item.created_at)}</time>,
    },
    {
      key: 'actions',
      label: 'Actions',
      width: '70px',
      align: 'right',
      render: (item) => {
        const actions: ActionMenuItem[] = [
          { label: 'View details', icon: <ViewIcon />, onSelect: () => setDetailTarget(item) },
        ];
        return <ActionMenu items={actions} ariaLabel={`Actions for ${item.full_name}`} />;
      },
    },
  ];

  const hasFilters = Boolean(search || role || emailVerified !== undefined);

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Registered accounts"
        subtitle="View public member registrations and their email-verification state."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Users' }]}
      />

      <div className={styles.body}>
        <div className={styles.toolbar}>
          <SearchInput
            value={search}
            onChange={(value) => updateParams({ search: value || null, page: '1' })}
            placeholder="Search name or email"
            aria-label="Search registered accounts"
          />
          <Button
            variant="secondary"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
            aria-controls="account-filters"
          >
            Filters
          </Button>
        </div>

        {filtersOpen && (
          <div id="account-filters" ref={filterPanelRef}>
            <FilterBar
              groups={[
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
              ]}
            />
          </div>
        )}

        <DataTable
          columns={columns}
          data={result?.data ?? []}
          page={page}
          pageSize={pageSize}
          rowKey={(item) => item.id}
          loading={loadState === 'loading'}
          error={
            loadState === 'error'
              ? { title: 'Failed to load registered accounts', message: errorMessage ?? undefined, onRetry: load }
              : null
          }
          empty={{
            icon: '👤',
            title: hasFilters ? 'No accounts found' : 'No registered accounts yet',
            description: hasFilters
              ? 'Try adjusting your search or filters.'
              : 'Public member registrations will appear here.',
          }}
        />

        {loadState === 'success' && result && result.meta.total > 0 && (
          <Pagination
            page={page}
            pageSize={pageSize}
            total={result.meta.total}
            onPageChange={(next) => updateParams({ page: String(next) })}
            onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })}
          />
        )}
      </div>

      {detailTarget && (
        <UserDetailDialog user={detailTarget} onClose={() => setDetailTarget(null)} />
      )}
    </div>
  );
}

function UserDetailDialog({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const { formatTimestamp } = useTimeSettings();
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
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
          <h2 id={titleId} className={styles.detailTitle}>Account details</h2>
          <button ref={closeRef} type="button" className={styles.detailClose} onClick={onClose} aria-label="Close dialog">✕</button>
        </header>
        <dl className={styles.details}>
          <dt>Full name</dt><dd>{user.full_name}</dd>
          <dt>Email</dt><dd>{user.email}</dd>
          <dt>Mobile</dt><dd>{user.mobile_number ?? '—'}</dd>
          <dt>Roles</dt><dd className={styles.roleList}>{user.roles.map((name) => <Badge key={name} size="sm" variant="info">{name.replace(/_/g, ' ')}</Badge>)}</dd>
          <dt>Country</dt><dd>{user.country ?? '—'}</dd>
          <dt>City</dt><dd>{user.city ?? '—'}</dd>
          <dt>Email verification</dt>
          <dd>
            {user.email_verified_at ? (
              <><Badge size="sm" variant="success">Verified</Badge> <span className={styles.muted}>{formatTimestamp(user.email_verified_at)}</span></>
            ) : <Badge size="sm" variant="neutral">Unverified</Badge>}
          </dd>
          <dt>Registered</dt><dd><time dateTime={user.created_at}>{formatTimestamp(user.created_at)}</time></dd>
        </dl>
        <footer className={styles.detailFooter}><Button variant="ghost" onClick={onClose}>Close</Button></footer>
      </div>
    </div>
  );
}