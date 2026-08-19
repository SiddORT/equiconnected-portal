/**
 * Admin Doctors page — /admin/doctors
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { listDoctors, updateDoctorStatus, updateDoctorPublication } from '@/api/doctors';
import { listProviders } from '@/api/providers';
import { listSpecializations } from '@/api/specializations';
import { ActionMenu } from '@/components/ui/ActionMenu';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import { PageHeader } from '@/components/layout/PageHeader';
import type { LoadingState, PaginatedResponse, Specialization } from '@/types';
import type { DoctorListItem } from '@/types/doctor';
import styles from './DoctorsPage.module.css';

const STABILITY_OPTS = [
  { value: 'all', label: 'All stability' },
  { value: 'STABLE_VISIT', label: 'Stable' },
  { value: 'NOT_STABLE_VISIT', label: 'Not stable' },
];
const STATUS_OPTS = [
  { value: 'all', label: 'All status' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'INACTIVE', label: 'Inactive' },
];
const PUB_OPTS = [
  { value: 'all', label: 'All' },
  { value: 'PUBLISHED', label: 'Published' },
  { value: 'UNPUBLISHED', label: 'Unpublished' },
];

export function DoctorsPage() {
  const navigate = useNavigate();

  const [result, setResult] = useState<PaginatedResponse<DoctorListItem> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [stabilityFilter, setStabilityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [publicationFilter, setPublicationFilter] = useState('all');
  const [specFilter, setSpecFilter] = useState('all');
  const [orgFilter, setOrgFilter] = useState('all');

  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const [allSpecs, setAllSpecs] = useState<Specialization[]>([]);
  const [allOrgs, setAllOrgs] = useState<{ id: string; name: string }[]>([]);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  const load = useCallback(async () => {
    setLoadState('loading');
    try {
      const params: Record<string, unknown> = { page, page_size: PAGE_SIZE };
      if (debouncedSearch) params.search = debouncedSearch;
      if (stabilityFilter !== 'all') params.visit_stability = stabilityFilter;
      if (statusFilter !== 'all') params.status = statusFilter;
      if (publicationFilter !== 'all') params.publication_status = publicationFilter;
      if (specFilter !== 'all') params.specialization_id = specFilter;
      if (orgFilter !== 'all') params.organization_id = orgFilter;
      setResult(await listDoctors(params as Parameters<typeof listDoctors>[0]));
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load doctors.'));
      setLoadState('error');
    }
  }, [page, debouncedSearch, stabilityFilter, statusFilter, publicationFilter, specFilter, orgFilter]);

  useEffect(() => { void load(); }, [load]);

  // Load filter options once
  useEffect(() => {
    listSpecializations({ page_size: 200 }).then((r) => setAllSpecs(r.data)).catch(() => {});
    listProviders({ page_size: 200 }).then((r) =>
      setAllOrgs(
        r.data
          .filter((p) => p.provider_type === 'HOSPITAL' || p.provider_type === 'CLINIC')
          .map((p) => ({ id: p.id, name: p.name }))
      )
    ).catch(() => {});
  }, []);

  async function handleToggleStatus(d: DoctorListItem) {
    const next = d.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    try { await updateDoctorStatus(d.id, next); await load(); } catch { /* ignore */ }
  }

  async function handleTogglePublication(d: DoctorListItem) {
    const next = d.publication_status === 'PUBLISHED' ? 'UNPUBLISHED' : 'PUBLISHED';
    try { await updateDoctorPublication(d.id, next); await load(); } catch { /* ignore */ }
  }

  const columns: DataTableColumn<DoctorListItem>[] = [
    {
      key: 'doctor',
      label: 'Doctor',
      width: '2fr',
      render: (d) => (
        <span className={styles.doctorCell}>
          <span className={styles.avatar}>
            {d.thumbnail_url
              ? <img src={d.thumbnail_url} alt="" className={styles.avatarImg} />
              : <span className={styles.avatarFallback}>{d.name.charAt(0).toUpperCase()}</span>
            }
          </span>
          <span className={styles.doctorInfo}>
            <Link to={`/admin/doctors/${d.id}`} className={styles.doctorName}>{d.name}</Link>
            {d.professional_title && (
              <span className={styles.doctorTitle}>{d.professional_title}</span>
            )}
          </span>
        </span>
      ),
    },
    {
      key: 'specializations',
      label: 'Specializations',
      width: '1.8fr',
      hideOnMobile: true,
      render: (d) =>
        d.specializations.length === 0
          ? <span className={styles.muted}>—</span>
          : (
            <span className={styles.pillRow}>
              {d.specializations.slice(0, 3).map((s) => (
                <Badge key={s.id} variant="info" size="sm">{s.name}</Badge>
              ))}
              {d.specializations.length > 3 && (
                <span className={styles.muted}>+{d.specializations.length - 3}</span>
              )}
            </span>
          ),
    },
    {
      key: 'primary_org',
      label: 'Primary Org',
      width: '1.5fr',
      hideOnMobile: true,
      render: (d) => d.primary_organization
        ? <span className={styles.orgName}>{d.primary_organization.name}</span>
        : <span className={styles.muted}>—</span>,
    },
    {
      key: 'visit_stability',
      label: 'Visit Stability',
      width: '120px',
      hideOnMobile: true,
      render: (d) => (
        <Badge variant={d.visit_stability === 'STABLE_VISIT' ? 'success' : 'warning'} size="sm">
          {d.visit_stability === 'STABLE_VISIT' ? 'Stable' : 'Not stable'}
        </Badge>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      width: '100px',
      render: (d) => (
        <Badge variant={d.status === 'ACTIVE' ? 'success' : 'neutral'} size="sm">
          {d.status === 'ACTIVE' ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      key: 'publication',
      label: 'Publication',
      width: '120px',
      hideOnMobile: true,
      render: (d) => (
        <Badge variant={d.publication_status === 'PUBLISHED' ? 'info' : 'neutral'} size="sm">
          {d.publication_status === 'PUBLISHED' ? 'Published' : 'Unpublished'}
        </Badge>
      ),
    },
    {
      key: 'created',
      label: 'Created',
      width: '110px',
      hideOnMobile: true,
      render: (d) => new Date(d.created_at).toLocaleDateString('en-GB'),
    },
    {
      key: 'actions',
      label: 'Actions',
      width: '80px',
      align: 'right',
      render: (d) => (
        <ActionMenu
          ariaLabel={`Actions for ${d.name}`}
          items={[
            { label: 'View', onSelect: () => navigate(`/admin/doctors/${d.id}`) },
            { label: 'Edit', onSelect: () => navigate(`/admin/doctors/${d.id}/edit`) },
            { label: '—', onSelect: () => {}, disabled: true },
            {
              label: d.status === 'ACTIVE' ? 'Mark inactive' : 'Mark active',
              onSelect: () => handleToggleStatus(d),
            },
            {
              label: d.publication_status === 'PUBLISHED' ? 'Unpublish' : 'Publish',
              onSelect: () => handleTogglePublication(d),
            },
          ]}
        />
      ),
    },
  ];

  const specOpts = [
    { value: 'all', label: 'All specializations' },
    ...allSpecs.map((s) => ({ value: s.id, label: s.name })),
  ];
  const orgOpts = [
    { value: 'all', label: 'All organizations' },
    ...allOrgs.map((o) => ({ value: o.id, label: o.name })),
  ];

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Doctors"
        subtitle="Manage doctor profiles and their hospital/clinic affiliations."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Doctors' }]}
        actions={
          <Button variant="primary" onClick={() => navigate('/admin/doctors/new')}>
            + Add doctor
          </Button>
        }
      />

      <div className={styles.body}>
        <div className={styles.toolbar}>
          <SearchInput
            value={search}
            onChange={(v) => setSearch(v)}
            placeholder="Search by name or title…"
          />
          <FilterBar
            groups={[
              { label: 'Specialization', options: specOpts, value: specFilter, onChange: (v) => { setSpecFilter(v); setPage(1); } },
              { label: 'Organization', options: orgOpts, value: orgFilter, onChange: (v) => { setOrgFilter(v); setPage(1); } },
              { label: 'Stability', options: STABILITY_OPTS, value: stabilityFilter, onChange: (v) => { setStabilityFilter(v); setPage(1); } },
              { label: 'Status', options: STATUS_OPTS, value: statusFilter, onChange: (v) => { setStatusFilter(v); setPage(1); } },
              { label: 'Publication', options: PUB_OPTS, value: publicationFilter, onChange: (v) => { setPublicationFilter(v); setPage(1); } },
            ]}
          />
        </div>

        <DataTable
          columns={columns}
          data={result?.data ?? []}
          page={page}
          pageSize={PAGE_SIZE}
          rowKey={(d) => d.id}
          loading={loadState === 'loading'}
          loadingLabel="Loading doctors…"
          empty={{ icon: '👨‍⚕️', title: 'No doctors yet', description: 'Add your first doctor profile.', action: <Button variant="primary" size="sm" onClick={() => navigate('/admin/doctors/new')}>+ Add doctor</Button> }}
          error={loadState === 'error' ? { title: 'Failed to load doctors', message: errorMessage ?? undefined, onRetry: load } : null}
          ariaLabel="Doctors table"
        />

        {result && (
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={result.meta.total}
            onPageChange={setPage}
            onPageSizeChange={() => {}}
          />
        )}
      </div>
    </div>
  );
}
