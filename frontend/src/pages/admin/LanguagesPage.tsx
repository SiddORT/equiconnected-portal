import { useCallback, useEffect, useState } from 'react';
import { extractErrorMessage } from '@/api/client';
import { deleteLanguage, listLanguages, updateLanguage } from '@/api/languages';
import { LanguageForm } from '@/components/admin/LanguageForm';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import { PageHeader } from '@/components/layout/PageHeader';
import type { Language, LoadingState, PaginatedResponse } from '@/types';
import styles from './LanguagesPage.module.css';

type Status = 'all' | 'active' | 'inactive';

export function LanguagesPage() {
  const [result, setResult] = useState<PaginatedResponse<Language> | null>(null);
  const [state, setState] = useState<LoadingState>('loading');
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<Status>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Language | undefined>();
  const [confirmTarget, setConfirmTarget] = useState<Language | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState('loading'); setError(null);
    try {
      const response = await listLanguages({
        search: search || undefined, is_active: status === 'all' ? undefined : status === 'active',
        page, page_size: pageSize,
      });
      if (page > 1 && response.meta.total_pages > 0 && page > response.meta.total_pages) { setPage(1); return; }
      setResult(response); setState('success');
    } catch (err) { setError(extractErrorMessage(err, 'Failed to load languages.')); setState('error'); }
  }, [search, status, page, pageSize]);
  useEffect(() => { void load(); }, [load]);

  async function toggle(language: Language) {
    setBusyId(language.id);
    try { await updateLanguage(language.id, { is_active: !language.is_active }); void load(); }
    catch (err) { alert(extractErrorMessage(err, 'Failed to update language status.')); }
    finally { setBusyId(null); }
  }
  async function remove() {
    if (!confirmTarget) return;
    setBusyId(confirmTarget.id);
    try { await deleteLanguage(confirmTarget.id); setConfirmTarget(null); void load(); }
    catch (err) { alert(extractErrorMessage(err, 'Failed to deactivate language.')); }
    finally { setBusyId(null); }
  }
  const columns: DataTableColumn<Language>[] = [
    { key: 'name', label: 'Language', width: '1.5fr', render: (item) => <span className={styles.name}>{item.name}</span> },
    { key: 'code', label: 'Code', width: '1fr', render: (item) => <code className={styles.code}>{item.code}</code> },
    { key: 'status', label: 'Status', width: '120px', render: (item) => <Badge variant={item.is_active ? 'success' : 'neutral'} size="sm">{item.is_active ? 'Active' : 'Inactive'}</Badge> },
    { key: 'actions', label: 'Actions', width: '240px', align: 'right', render: (item) => <span className={styles.actions}>
      <button type="button" className={styles.action} onClick={() => { setEditTarget(item); setFormOpen(true); }} aria-label={`Edit ${item.name}`}>✏️ Edit</button>
      <button type="button" className={`${styles.action} ${item.is_active ? styles.deactivate : styles.activate}`} disabled={busyId === item.id} onClick={() => void toggle(item)} aria-label={item.is_active ? `Deactivate ${item.name}` : `Reactivate ${item.name}`}>{busyId === item.id ? '…' : item.is_active ? '⊘ Deactivate' : '✓ Reactivate'}</button>
      {item.is_active && <button type="button" className={`${styles.action} ${styles.delete}`} disabled={busyId === item.id} onClick={() => setConfirmTarget(item)} aria-label={`Delete ${item.name}`}>Delete</button>}
    </span> },
  ];
  return <div className={styles.shell}>
    <PageHeader title="Languages" subtitle="Manage language master data available across the platform." breadcrumbs={[{ label: 'Admin' }, { label: 'Languages' }]} actions={<Button variant="primary" onClick={() => { setEditTarget(undefined); setFormOpen(true); }} leftIcon="＋">Add language</Button>} />
    <div className={styles.body}>
      <div className={styles.toolbar}><SearchInput placeholder="Search by name or code…" value={search} onChange={(value) => { setSearch(value); setPage(1); }} delay={300} containerClassName={styles.search} /><FilterBar groups={[{ label: 'Filter by status', options: [{ value: 'all', label: 'All' }, { value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }], value: status, onChange: (value) => { setStatus(value as Status); setPage(1); } }]} /></div>
      <DataTable ariaLabel="Languages" columns={columns} data={result?.data ?? []} page={page} pageSize={pageSize} rowKey={(item) => item.id} loading={state === 'loading'} loadingLabel="Loading languages…" error={state === 'error' ? { title: 'Failed to load languages', message: error ?? undefined, onRetry: load } : null} empty={{ icon: '🌐', title: search || status !== 'all' ? 'No results found' : 'No languages yet', description: 'Add a language to get started.' }} />
      {state === 'success' && result?.meta && <Pagination page={page} pageSize={pageSize} total={result.meta.total} onPageChange={setPage} onPageSizeChange={(size) => { setPageSize(size); setPage(1); }} />}
    </div>
    {formOpen && <LanguageForm initialValues={editTarget} onSuccess={() => { setFormOpen(false); setEditTarget(undefined); void load(); }} onCancel={() => { setFormOpen(false); setEditTarget(undefined); }} />}
    <ConfirmDialog open={Boolean(confirmTarget)} title="Deactivate language?" message={confirmTarget ? `This will remove ${confirmTarget.name} from active language selections.` : undefined} confirmLabel="Deactivate language" danger onCancel={() => setConfirmTarget(null)} onConfirm={() => void remove()} />
  </div>;
}