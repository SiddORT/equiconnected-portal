/**
 * Admin Specializations page — /admin/specializations
 *
 * Features: list, search, active/inactive filter, pagination,
 *           create (modal form), edit (modal form), activate/deactivate.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { extractErrorMessage } from '@/api/client';
import {
  listSpecializations,
  setSpecializationStatus,
} from '@/api/specializations';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageHeader } from '@/components/layout/PageHeader';
import { SpecializationForm } from '@/components/admin/SpecializationForm';
import type { LoadingState, PaginatedResponse, Specialization } from '@/types';
import styles from './SpecializationsPage.module.css';

const PAGE_SIZE = 20;

type FilterStatus = 'all' | 'active' | 'inactive';

export function SpecializationsPage() {
  // ── State ─────────────────────────────────────────────────────────────────
  const [result, setResult] = useState<PaginatedResponse<Specialization> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [page, setPage] = useState(1);

  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Specialization | null>(null);

  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Debounce search
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search]);

  // ── Load ──────────────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const params: Record<string, unknown> = { page, page_size: PAGE_SIZE };
      if (debouncedSearch) params.search = debouncedSearch;
      if (filterStatus === 'active') params.is_active = true;
      if (filterStatus === 'inactive') params.is_active = false;

      const data = await listSpecializations(params as Parameters<typeof listSpecializations>[0]);
      setResult(data);
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load specializations.'));
      setLoadState('error');
    }
  }, [page, debouncedSearch, filterStatus]);

  useEffect(() => { void load(); }, [load]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  function openCreate() { setEditTarget(null); setFormOpen(true); }
  function openEdit(spec: Specialization) { setEditTarget(spec); setFormOpen(true); }
  function closeForm() { setFormOpen(false); setEditTarget(null); }

  function handleFormSuccess() {
    closeForm();
    void load();
  }

  async function handleToggleStatus(spec: Specialization) {
    setTogglingId(spec.id);
    try {
      await setSpecializationStatus(spec.id, !spec.is_active);
      void load();
    } catch (err) {
      alert(extractErrorMessage(err, 'Failed to update status.'));
    } finally {
      setTogglingId(null);
    }
  }

  // ── Derived ───────────────────────────────────────────────────────────────
  const totalPages = result?.meta.total_pages ?? 1;
  const meta = result?.meta;

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Specializations"
        subtitle="Manage medical specialization master data used across hospitals, clinics, and doctors."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Specializations' }]}
        actions={
          <Button variant="primary" onClick={openCreate} leftIcon="＋">
            Add specialization
          </Button>
        }
      />

      <div className={styles.body}>
        {/* ── Toolbar ─────────────────────────────────────────────────────── */}
        <div className={styles.toolbar}>
          <Input
            placeholder="Search by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            leftAdornment={<span aria-hidden="true">🔍</span>}
            containerClassName={styles.searchInput}
          />

          <div className={styles.filterTabs} role="group" aria-label="Filter by status">
            {(['all', 'active', 'inactive'] as FilterStatus[]).map((f) => (
              <button
                key={f}
                type="button"
                className={`${styles.filterTab} ${filterStatus === f ? styles['filterTab--active'] : ''}`}
                onClick={() => { setFilterStatus(f); setPage(1); }}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* ── Content ─────────────────────────────────────────────────────── */}
        {loadState === 'loading' && (
          <div className={styles.centered}>
            <LoadingSpinner size="lg" label="Loading specializations…" />
          </div>
        )}

        {loadState === 'error' && (
          <ErrorState
            title="Failed to load specializations"
            message={errorMessage ?? undefined}
            onRetry={load}
          />
        )}

        {loadState === 'success' && result && (
          <>
            {result.data.length === 0 ? (
              <EmptyState
                icon="🩺"
                title={debouncedSearch || filterStatus !== 'all' ? 'No results found' : 'No specializations yet'}
                description={
                  debouncedSearch || filterStatus !== 'all'
                    ? 'Try adjusting your search or filter.'
                    : 'Add your first specialization to get started.'
                }
              />
            ) : (
              <Card padding="none" shadow="sm">
                <div role="table" aria-label="Specializations" className={styles.table}>
                  {/* Header */}
                  <div role="rowgroup">
                    <div role="row" className={`${styles.row} ${styles.headerRow}`}>
                      <span role="columnheader">Name</span>
                      <span role="columnheader">Description</span>
                      <span role="columnheader">Status</span>
                      <span role="columnheader" className={styles.actionsCol}>Actions</span>
                    </div>
                  </div>

                  {/* Rows */}
                  <div role="rowgroup">
                    {result.data.map((spec) => (
                      <div key={spec.id} role="row" className={styles.row}>
                        <span role="cell" className={styles.nameCell}>
                          {spec.name}
                        </span>
                        <span role="cell" className={styles.descCell}>
                          {spec.description ?? <span className={styles.muted}>—</span>}
                        </span>
                        <span role="cell">
                          <Badge variant={spec.is_active ? 'success' : 'neutral'} size="sm">
                            {spec.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </span>
                        <span role="cell" className={`${styles.actionsCol} ${styles.actionBtns}`}>
                          <button
                            type="button"
                            className={styles.actionBtn}
                            onClick={() => openEdit(spec)}
                            aria-label={`Edit ${spec.name}`}
                          >
                            ✏️ Edit
                          </button>
                          <button
                            type="button"
                            className={`${styles.actionBtn} ${spec.is_active ? styles['actionBtn--deactivate'] : styles['actionBtn--activate']}`}
                            onClick={() => handleToggleStatus(spec)}
                            disabled={togglingId === spec.id}
                            aria-label={spec.is_active ? `Deactivate ${spec.name}` : `Activate ${spec.name}`}
                          >
                            {togglingId === spec.id
                              ? '…'
                              : spec.is_active
                              ? '⊘ Deactivate'
                              : '✓ Activate'}
                          </button>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            )}

            {/* ── Pagination ─────────────────────────────────────────────── */}
            {meta && meta.total > PAGE_SIZE && (
              <div className={styles.pagination} aria-label="Pagination">
                <span className={styles.paginationInfo}>
                  {meta.total} total · page {meta.page} of {meta.total_pages}
                </span>
                <div className={styles.paginationBtns}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    ← Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                  >
                    Next →
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Modal form ──────────────────────────────────────────────────────── */}
      {formOpen && (
        <SpecializationForm
          initialValues={editTarget ?? undefined}
          onSuccess={handleFormSuccess}
          onCancel={closeForm}
        />
      )}
    </div>
  );
}
