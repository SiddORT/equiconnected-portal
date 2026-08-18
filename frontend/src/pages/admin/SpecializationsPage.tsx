/**
 * Admin Specializations page — /admin/specializations
 *
 * Features: list, search, active/inactive filter, pagination,
 *           create (modal form), edit (modal form), activate/deactivate.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { extractErrorMessage } from '@/api/client';
import {
  confirmImport,
  downloadImportTemplate,
  exportSpecializations,
  listSpecializations,
  previewImport,
  setSpecializationStatus,
} from '@/api/specializations';
import { CsvImportDialog } from '@/components/admin/CsvImportDialog';
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

const PAGE_SIZE_OPTIONS = [10, 25, 100] as const;

type FilterStatus = 'all' | 'active' | 'inactive';

export function SpecializationsPage() {
  // ── State ─────────────────────────────────────────────────────────────────
  const [result, setResult] = useState<PaginatedResponse<Specialization> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Specialization | null>(null);

  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

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
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (debouncedSearch) params.search = debouncedSearch;
      if (filterStatus === 'active') params.is_active = true;
      if (filterStatus === 'inactive') params.is_active = false;

      const data = await listSpecializations(params as Parameters<typeof listSpecializations>[0]);

      // Defensive guard: if the current page is beyond the last page (e.g. a
      // filter narrowed the result set), snap back to page 1 and let the
      // effect re-fire.  This makes the component self-healing regardless of
      // which code path changed the filters.
      if (page > 1 && data.meta.total_pages > 0 && page > data.meta.total_pages) {
        setPage(1);
        return;
      }

      setResult(data);
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load specializations.'));
      setLoadState('error');
    }
  }, [page, pageSize, debouncedSearch, filterStatus]);

  useEffect(() => { void load(); }, [load]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  function openCreate() { setEditTarget(null); setFormOpen(true); }
  function openEdit(spec: Specialization) { setEditTarget(spec); setFormOpen(true); }
  function closeForm() { setFormOpen(false); setEditTarget(null); }

  function handleFormSuccess() {
    closeForm();
    void load();
  }

  function handlePageSizeChange(e: React.ChangeEvent<HTMLSelectElement>) {
    setPageSize(Number(e.target.value));
    setPage(1);
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

  async function handleExport() {
    setExporting(true);
    setExportError(null);
    try {
      const params: { search?: string; is_active?: boolean } = {};
      if (debouncedSearch) params.search = debouncedSearch;
      if (filterStatus === 'active') params.is_active = true;
      if (filterStatus === 'inactive') params.is_active = false;
      await exportSpecializations(params);
    } catch (err) {
      setExportError(extractErrorMessage(err, 'Failed to export specializations.'));
    } finally {
      setExporting(false);
    }
  }

  // ── Derived ───────────────────────────────────────────────────────────────
  const totalPages = result?.meta.total_pages ?? 1;
  const meta = result?.meta;

  const paginationFrom = meta ? (page - 1) * pageSize + 1 : 0;
  const paginationTo = meta ? Math.min(page * pageSize, meta.total) : 0;

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Specializations"
        subtitle="Manage medical specialization master data used across hospitals, clinics, and doctors."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Specializations' }]}
        actions={
          <>
            <Button
              variant="outline"
              onClick={handleExport}
              loading={exporting}
              leftIcon="⬇"
            >
              Export
            </Button>
            <Button variant="outline" onClick={() => setImportOpen(true)} leftIcon="⬆">
              Import
            </Button>
            <Button variant="primary" onClick={openCreate} leftIcon="＋">
              Add specialization
            </Button>
          </>
        }
      />

      <div className={styles.body}>
        {exportError && (
          <div className={styles.exportError} role="alert">{exportError}</div>
        )}

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

          <label className={styles.pageSizeLabel}>
            Show entries:
            <select
              className={styles.pageSizeSelect}
              value={pageSize}
              onChange={handlePageSizeChange}
              aria-label="Rows per page"
            >
              {PAGE_SIZE_OPTIONS.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
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
                      <span role="columnheader" className={styles.srNoCol}>Sr. No.</span>
                      <span role="columnheader">Name</span>
                      <span role="columnheader">Description</span>
                      <span role="columnheader">Status</span>
                      <span role="columnheader" className={styles.actionsCol}>Actions</span>
                    </div>
                  </div>

                  {/* Rows */}
                  <div role="rowgroup">
                    {result.data.map((spec, index) => (
                      <div key={spec.id} role="row" className={styles.row}>
                        <span role="cell" className={`${styles.srNoCol} ${styles.srNoCell}`}>
                          {(page - 1) * pageSize + index + 1}
                        </span>
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
            {meta && (
              <div className={styles.pagination} aria-label="Pagination">
                <span className={styles.paginationInfo}>
                  Showing {paginationFrom} to {paginationTo} of {meta.total} entries
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
      {/* ── CSV import wizard ──────────────────────────────────────────────── */}
      {importOpen && (
        <CsvImportDialog
          title="Import Specializations"
          onPreview={previewImport}
          onImport={confirmImport}
          onDownloadTemplate={downloadImportTemplate}
          onClose={() => setImportOpen(false)}
          onImported={() => { void load(); }}
        />
      )}

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
