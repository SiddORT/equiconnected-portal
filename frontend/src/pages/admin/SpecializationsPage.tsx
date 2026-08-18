/**
 * Admin Specializations page — /admin/specializations
 *
 * Features: list, search, active/inactive filter, pagination,
 *           create (modal form), edit (modal form), activate/deactivate.
 *
 * Uses the shared DataTable / FilterBar / Pagination / SearchInput components.
 */
import { useCallback, useEffect, useState } from 'react';
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
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import { PageHeader } from '@/components/layout/PageHeader';
import { SpecializationForm } from '@/components/admin/SpecializationForm';
import type { LoadingState, PaginatedResponse, Specialization } from '@/types';
import styles from './SpecializationsPage.module.css';

type FilterStatus = 'all' | 'active' | 'inactive';

export function SpecializationsPage() {
  // ── State ─────────────────────────────────────────────────────────────────
  const [result, setResult] = useState<PaginatedResponse<Specialization> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Specialization | null>(null);

  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

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

      // Page-out-of-range guard: if the current page is beyond the last page
      // (e.g. a filter narrowed the result set), snap back to page 1 and let
      // the effect re-fire.
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

  function handleSearchChange(value: string) {
    setDebouncedSearch(value);
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

  // ── Table config ──────────────────────────────────────────────────────────
  const columns: DataTableColumn<Specialization>[] = [
    {
      key: 'name',
      label: 'Name',
      width: '1.5fr',
      render: (spec) => <span className={styles.nameCell}>{spec.name}</span>,
    },
    {
      key: 'description',
      label: 'Description',
      width: '2fr',
      hideOnMobile: true,
      render: (spec) => (
        <span className={styles.descCell}>
          {spec.description ?? <span className={styles.muted}>—</span>}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      width: '120px',
      render: (spec) => (
        <Badge variant={spec.is_active ? 'success' : 'neutral'} size="sm">
          {spec.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      width: '200px',
      align: 'right',
      render: (spec) => (
        <span className={styles.actionBtns}>
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
            {togglingId === spec.id ? '…' : spec.is_active ? '⊘ Deactivate' : '✓ Activate'}
          </button>
        </span>
      ),
    },
  ];

  const meta = result?.meta;

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
          <SearchInput
            placeholder="Search by name…"
            value={debouncedSearch}
            onChange={handleSearchChange}
            delay={300}
            containerClassName={styles.searchInput}
          />

          <FilterBar
            groups={[
              {
                label: 'Filter by status',
                options: [
                  { value: 'all', label: 'All' },
                  { value: 'active', label: 'Active' },
                  { value: 'inactive', label: 'Inactive' },
                ],
                value: filterStatus,
                onChange: (v) => { setFilterStatus(v as FilterStatus); setPage(1); },
              },
            ]}
          />
        </div>

        {/* ── Content ─────────────────────────────────────────────────────── */}
        <DataTable
          ariaLabel="Specializations"
          columns={columns}
          data={result?.data ?? []}
          page={page}
          pageSize={pageSize}
          rowKey={(spec) => spec.id}
          loading={loadState === 'loading'}
          loadingLabel="Loading specializations…"
          error={
            loadState === 'error'
              ? {
                  title: 'Failed to load specializations',
                  message: errorMessage ?? undefined,
                  onRetry: load,
                }
              : null
          }
          empty={{
            icon: '🩺',
            title: debouncedSearch || filterStatus !== 'all' ? 'No results found' : 'No specializations yet',
            description:
              debouncedSearch || filterStatus !== 'all'
                ? 'Try adjusting your search or filter.'
                : 'Add your first specialization to get started.',
          }}
        />

        {/* ── Pagination ──────────────────────────────────────────────────── */}
        {loadState === 'success' && meta && (
          <Pagination
            page={page}
            pageSize={pageSize}
            total={meta.total}
            onPageChange={setPage}
            onPageSizeChange={(size) => { setPageSize(size); setPage(1); }}
          />
        )}
      </div>

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

      {/* ── Modal form ─────────────────────────────────────────────────────── */}
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
