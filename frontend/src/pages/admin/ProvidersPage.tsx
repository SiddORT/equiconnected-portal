/**
 * Admin Providers page — /admin/providers
 * Server-side search / filters / pagination via query params.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import {
  listProviders,
  updateProviderPublication,
  updateProviderStatus,
} from '@/api/providers';
import { ActionMenu } from '@/components/ui/ActionMenu';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import { PageHeader } from '@/components/layout/PageHeader';
import type {
  LoadingState,
  PaginatedResponse,
  ProviderListItem,
  ProviderListParams,
  ProviderStatus,
  ProviderType,
  PublicationStatus,
  VisitStability,
} from '@/types';
import styles from './ProvidersPage.module.css';

const TYPE_LABELS: Record<ProviderType, string> = {
  HOSPITAL: 'Hospital',
  CLINIC: 'Clinic',
  DOCTOR: 'Doctor',
};

export function ProvidersPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialType = searchParams.get('provider_type');

  const [result, setResult] = useState<PaginatedResponse<ProviderListItem> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState(
    initialType && initialType in TYPE_LABELS ? initialType : 'all'
  );
  const [stabilityFilter, setStabilityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [publicationFilter, setPublicationFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const [busyId, setBusyId] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filterPanelRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const params: ProviderListParams = { page, page_size: pageSize };
      if (search) params.search = search;
      if (typeFilter !== 'all') params.provider_type = typeFilter as ProviderType;
      if (stabilityFilter !== 'all') params.visit_stability = stabilityFilter as VisitStability;
      if (statusFilter !== 'all') params.status = statusFilter as ProviderStatus;
      if (publicationFilter !== 'all') params.publication_status = publicationFilter as PublicationStatus;

      const data = await listProviders(params);

      // Page-out-of-range guard: snap back to page 1 when past the last page.
      if (page > 1 && data.meta.total_pages > 0 && page > data.meta.total_pages) {
        setPage(1);
        return;
      }

      setResult(data);
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load providers.'));
      setLoadState('error');
    }
  }, [page, pageSize, search, typeFilter, stabilityFilter, statusFilter, publicationFilter]);

  useEffect(() => { void load(); }, [load]);

  function resetAnd(setter: (v: string) => void) {
    return (v: string) => { setter(v); setPage(1); };
  }

  async function handleToggleStatus(p: ProviderListItem) {
    setBusyId(p.id);
    try {
      await updateProviderStatus(p.id, p.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE');
      void load();
    } catch (err) {
      alert(extractErrorMessage(err, 'Failed to update status.'));
    } finally {
      setBusyId(null);
    }
  }

  async function handleTogglePublication(p: ProviderListItem) {
    setBusyId(p.id);
    try {
      await updateProviderPublication(
        p.id,
        p.publication_status === 'PUBLISHED' ? 'UNPUBLISHED' : 'PUBLISHED'
      );
      void load();
    } catch (err) {
      alert(extractErrorMessage(err, 'Failed to update publication status.'));
    } finally {
      setBusyId(null);
    }
  }

  const columns: DataTableColumn<ProviderListItem>[] = [
    {
      key: 'provider',
      label: 'Provider',
      width: '1.8fr',
      render: (p) => (
        <span className={styles.providerCell}>
          <span className={styles.providerAvatar}>
            {p.thumbnail_url
              ? <img src={p.thumbnail_url} alt="" className={styles.providerAvatarImg} />
              : <span className={styles.providerAvatarFallback}>{p.name.charAt(0).toUpperCase()}</span>
            }
          </span>
          <span className={styles.providerInfo}>
            <Link to={`/admin/providers/${p.id}`} className={styles.providerName}>
              {p.name}
            </Link>
            <Badge variant="info" size="sm">{TYPE_LABELS[p.provider_type]}</Badge>
          </span>
        </span>
      ),
    },
    {
      key: 'visit_stability',
      label: 'Visit Stable',
      width: '130px',
      hideOnMobile: true,
      render: (p) => (
        <Badge variant={p.visit_stability === 'STABLE_VISIT' ? 'success' : 'warning'} size="sm">
          {p.visit_stability === 'STABLE_VISIT' ? 'Stable' : 'Not stable'}
        </Badge>
      ),
    },
    {
      key: 'contact',
      label: 'Contact',
      width: '1.4fr',
      hideOnMobile: true,
      render: (p) => (
        <span className={styles.contactCell}>
          {p.email ?? p.phone ?? <span className={styles.muted}>—</span>}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      width: '100px',
      render: (p) => (
        <Badge variant={p.status === 'ACTIVE' ? 'success' : 'neutral'} size="sm">
          {p.status === 'ACTIVE' ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      key: 'publication_status',
      label: 'Publication',
      width: '120px',
      hideOnMobile: true,
      render: (p) => (
        <Badge variant={p.publication_status === 'PUBLISHED' ? 'info' : 'neutral'} size="sm">
          {p.publication_status === 'PUBLISHED' ? 'Published' : 'Unpublished'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      label: 'Created',
      width: '110px',
      hideOnMobile: true,
      render: (p) => (
        <span className={styles.dateCell}>
          {new Date(p.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      width: '70px',
      align: 'right',
      render: (p) => (
        <ActionMenu
          ariaLabel={`Actions for ${p.name}`}
          items={[
            { label: 'View', icon: '👁', onSelect: () => navigate(`/admin/providers/${p.id}`) },
            { label: 'Edit', icon: '✏️', onSelect: () => navigate(`/admin/providers/${p.id}/edit`) },
            {
              label: p.status === 'ACTIVE' ? 'Deactivate' : 'Activate',
              icon: p.status === 'ACTIVE' ? '⊘' : '✓',
              danger: p.status === 'ACTIVE',
              disabled: busyId === p.id,
              onSelect: () => handleToggleStatus(p),
            },
            {
              label: p.publication_status === 'PUBLISHED' ? 'Unpublish' : 'Publish',
              icon: p.publication_status === 'PUBLISHED' ? '📕' : '📗',
              disabled: busyId === p.id,
              onSelect: () => handleTogglePublication(p),
            },
          ]}
        />
      ),
    },
  ];

  const meta = result?.meta;
  const hasData = (meta?.total ?? 0) > 0;

  const hasFilters =
    Boolean(search) ||
    typeFilter !== 'all' ||
    stabilityFilter !== 'all' ||
    statusFilter !== 'all' ||
    publicationFilter !== 'all';

  // Active filter chips shown in toolbar when filter panel is collapsed.
  const activeChips: { label: string; onClear: () => void }[] = [];
  if (typeFilter !== 'all') {
    const label = { HOSPITAL: 'Hospitals', CLINIC: 'Clinics', DOCTOR: 'Doctors' }[typeFilter] ?? typeFilter;
    activeChips.push({ label: `Type: ${label}`, onClear: () => { setTypeFilter('all'); setPage(1); } });
  }
  if (stabilityFilter !== 'all') {
    const label = stabilityFilter === 'STABLE_VISIT' ? 'Yes' : 'No';
    activeChips.push({ label: `Stable visit: ${label}`, onClear: () => { setStabilityFilter('all'); setPage(1); } });
  }
  if (statusFilter !== 'all') {
    const label = statusFilter === 'ACTIVE' ? 'Active' : 'Inactive';
    activeChips.push({ label: `Status: ${label}`, onClear: () => { setStatusFilter('all'); setPage(1); } });
  }
  if (publicationFilter !== 'all') {
    const label = publicationFilter === 'PUBLISHED' ? 'Published' : 'Unpublished';
    activeChips.push({ label: `Publication: ${label}`, onClear: () => { setPublicationFilter('all'); setPage(1); } });
  }

  const filterGroups = [
    {
      label: 'Provider type',
      options: [
        { value: 'all', label: 'All types' },
        { value: 'HOSPITAL', label: 'Hospitals' },
        { value: 'CLINIC', label: 'Clinics' },
        { value: 'DOCTOR', label: 'Doctors' },
      ],
      value: typeFilter,
      onChange: resetAnd(setTypeFilter),
    },
    {
      label: 'Stable visit',
      options: [
        { value: 'all', label: 'All visits' },
        { value: 'STABLE_VISIT', label: 'Yes' },
        { value: 'NOT_STABLE_VISIT', label: 'No' },
      ],
      value: stabilityFilter,
      onChange: resetAnd(setStabilityFilter),
    },
    {
      label: 'Status',
      options: [
        { value: 'all', label: 'All statuses' },
        { value: 'ACTIVE', label: 'Active' },
        { value: 'INACTIVE', label: 'Inactive' },
      ],
      value: statusFilter,
      onChange: resetAnd(setStatusFilter),
    },
    {
      label: 'Publication',
      options: [
        { value: 'all', label: 'All publication' },
        { value: 'PUBLISHED', label: 'Published' },
        { value: 'UNPUBLISHED', label: 'Unpublished' },
      ],
      value: publicationFilter,
      onChange: resetAnd(setPublicationFilter),
    },
  ];

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Providers"
        subtitle="Manage hospitals, clinics, and doctors — profiles, locations, photos, and publication."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Providers' }]}
        actions={
          <Button variant="primary" onClick={() => navigate('/admin/providers/new')} leftIcon="＋">
            Add provider
          </Button>
        }
      />

      <div className={styles.body}>
        {/* ── Toolbar: search + filter toggle ─────────────────────────────── */}
        <div className={styles.toolbar}>
          <SearchInput
            placeholder="Search by name…"
            value={search}
            onChange={(v) => { setSearch(v); setPage(1); }}
            containerClassName={styles.searchInput}
          />

          <button
            type="button"
            className={`${styles.filterToggle} ${filtersOpen ? styles['filterToggle--open'] : ''} ${activeChips.length > 0 && !filtersOpen ? styles['filterToggle--active'] : ''}`}
            onClick={() => setFiltersOpen((o) => !o)}
            aria-expanded={filtersOpen}
          >
            <span className={styles.filterToggleIcon}>⊟</span>
            Filters
            {activeChips.length > 0 && (
              <span className={styles.filterCount}>{activeChips.length}</span>
            )}
            <span className={`${styles.chevron} ${filtersOpen ? styles['chevron--up'] : ''}`}>▾</span>
          </button>

          {/* Active filter chips — visible only when panel is collapsed */}
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

        {/* ── Collapsible filter panel ─────────────────────────────────────── */}
        <div
          ref={filterPanelRef}
          className={`${styles.filterPanel} ${filtersOpen ? styles['filterPanel--open'] : ''}`}
          aria-hidden={!filtersOpen}
        >
          <div className={styles.filterPanelInner}>
            <FilterBar groups={filterGroups} />
            {hasFilters && (
              <button
                type="button"
                className={styles.clearAll}
                onClick={() => {
                  setTypeFilter('all');
                  setStabilityFilter('all');
                  setStatusFilter('all');
                  setPublicationFilter('all');
                  setPage(1);
                }}
              >
                Clear all filters
              </button>
            )}
          </div>
        </div>

        {/* ── Data table ──────────────────────────────────────────────────── */}
        <DataTable
          ariaLabel="Providers"
          columns={columns}
          data={result?.data ?? []}
          page={page}
          pageSize={pageSize}
          rowKey={(p) => p.id}
          loading={loadState === 'loading'}
          loadingLabel="Loading providers…"
          error={
            loadState === 'error'
              ? { title: 'Failed to load providers', message: errorMessage ?? undefined, onRetry: load }
              : null
          }
          empty={{
            icon: '🏥',
            title: hasFilters ? 'No results found' : 'No providers yet',
            description: hasFilters
              ? 'Try adjusting your search or filters.'
              : 'Add your first provider to get started.',
            action: !hasFilters ? (
              <Button variant="primary" onClick={() => navigate('/admin/providers/new')}>
                Add provider
              </Button>
            ) : undefined,
          }}
        />

        {/* ── Pagination — only when records exist ────────────────────────── */}
        {loadState === 'success' && meta && hasData && (
          <Pagination
            page={page}
            pageSize={pageSize}
            total={meta.total}
            onPageChange={setPage}
            onPageSizeChange={(size) => { setPageSize(size); setPage(1); }}
          />
        )}
      </div>
    </div>
  );
}
