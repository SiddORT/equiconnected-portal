/**
 * CsvImportDialog — generic multi-step CSV import wizard.
 *
 * Steps: Upload → Preview (with per-row validation) → Result.
 * Generic and prop-configured so future modules (Hospitals, Clinics, …)
 * can reuse it; currently wired up only for Specializations.
 */
import { useEffect, useId, useRef, useState } from 'react';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { triggerCsvDownload } from '@/utils/csvExport';
import type { ImportPreviewResponse, ImportResult, ImportRowPreview, ImportRowState } from '@/types';
import styles from './CsvImportDialog.module.css';

interface CsvImportDialogProps {
  title: string;
  /** Column labels for the preview table (Name / Description / Status are rendered from row data). */
  previewColumns?: string[];
  maxFileSizeMb?: number;
  onPreview: (file: File) => Promise<ImportPreviewResponse>;
  onImport: (rows: ImportRowPreview[]) => Promise<ImportResult>;
  onDownloadTemplate: () => Promise<void>;
  onClose: () => void;
  /** Called after a successful import so the parent can refresh its list. */
  onImported?: (result: ImportResult) => void;
}

type Step = 'upload' | 'preview' | 'result';

const STATE_BADGE: Record<ImportRowState, { variant: 'success' | 'warning' | 'error'; label: string }> = {
  valid: { variant: 'success', label: 'Valid' },
  duplicate: { variant: 'warning', label: 'Duplicate' },
  invalid: { variant: 'error', label: 'Invalid' },
};

function buildErrorReport(rows: ImportRowPreview[]): Blob {
  const escape = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const lines = ['Row,Name,Description,Status,State,Reason'];
  for (const r of rows) {
    if (r.state === 'valid') continue;
    lines.push(
      [String(r.row_num), r.name, r.description ?? '', r.status, r.state, r.reason ?? '']
        .map(escape)
        .join(',')
    );
  }
  return new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
}

export function CsvImportDialog({
  title,
  previewColumns = ['Row', 'Name', 'Description', 'Status', 'Result'],
  maxFileSizeMb = 5,
  onPreview,
  onImport,
  onDownloadTemplate,
  onClose,
  onImported,
}: CsvImportDialogProps) {
  const titleId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<Step>('upload');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    const handle = (e: KeyboardEvent) => { if (e.key === 'Escape' && !busy) onClose(); };
    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, [onClose, busy]);

  async function handleFile(file: File) {
    setError(null);
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Please choose a .csv file.');
      return;
    }
    if (file.size > maxFileSizeMb * 1024 * 1024) {
      setError(`File exceeds the ${maxFileSizeMb} MB size limit.`);
      return;
    }
    setBusy(true);
    try {
      const data = await onPreview(file);
      setPreview(data);
      setStep('preview');
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to validate the file. Please check the format.'));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      const res = await onImport(preview.rows);
      setResult(res);
      setStep('result');
      onImported?.(res);
    } catch (err) {
      setError(extractErrorMessage(err, 'Import failed. No rows were saved.'));
    } finally {
      setBusy(false);
    }
  }

  async function handleTemplate() {
    setError(null);
    try {
      await onDownloadTemplate();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to download the template.'));
    }
  }

  function handleErrorReport() {
    const rows = result?.row_details ?? preview?.rows ?? [];
    triggerCsvDownload(buildErrorReport(rows), 'import-error-report.csv');
  }

  const skippedCount = (result?.skipped ?? 0) + (result?.errors ?? 0) > 0
    ? (result?.row_details ?? []).filter((r) => r.state !== 'valid').length
    : 0;

  return (
    <div className={styles.backdrop} role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className={styles.panel}>
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>{title}</h2>
          <button type="button" className={styles.closeBtn} aria-label="Close" onClick={onClose} disabled={busy}>
            ✕
          </button>
        </header>

        <div className={styles.body}>
          {error && <Alert variant="error">{error}</Alert>}

          {/* ── Step 1: Upload ─────────────────────────────────────────── */}
          {step === 'upload' && (
            <>
              <p className={styles.helpText}>
                Upload a UTF-8 CSV file with columns <strong>Name</strong>, <strong>Description</strong>,{' '}
                <strong>Status</strong> (ACTIVE or INACTIVE). Maximum size: {maxFileSizeMb} MB.
              </p>
              <button
                type="button"
                className={`${styles.dropzone} ${dragOver ? styles['dropzone--active'] : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) void handleFile(file);
                }}
                disabled={busy}
              >
                {busy ? (
                  <LoadingSpinner size="md" label="Validating file…" />
                ) : (
                  <>
                    <span className={styles.dropIcon} aria-hidden="true">📄</span>
                    <span>Click to choose a CSV file, or drag &amp; drop it here</span>
                  </>
                )}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                className={styles.hiddenInput}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleFile(file);
                  e.target.value = '';
                }}
              />
              <button type="button" className={styles.templateLink} onClick={handleTemplate}>
                ⬇ Download Template
              </button>
            </>
          )}

          {/* ── Step 2: Preview & confirm ──────────────────────────────── */}
          {step === 'preview' && preview && (
            <>
              <div className={styles.summary}>
                <span className={styles.summaryItem}>Total rows: <strong>{preview.total}</strong></span>
                <span className={styles.summaryItem}>Valid: <strong className={styles.ok}>{preview.valid}</strong></span>
                <span className={styles.summaryItem}>Duplicates: <strong className={styles.warn}>{preview.duplicate}</strong></span>
                <span className={styles.summaryItem}>Invalid: <strong className={styles.bad}>{preview.invalid}</strong></span>
              </div>

              {preview.valid === 0 && (
                <Alert variant="warning">
                  No rows can be imported. Fix the issues below and upload the file again.
                </Alert>
              )}

              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      {previewColumns.map((c) => <th key={c}>{c}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((r) => (
                      <tr key={r.row_num} className={r.state !== 'valid' ? styles.rowProblem : undefined}>
                        <td>{r.row_num}</td>
                        <td>{r.name || <span className={styles.muted}>—</span>}</td>
                        <td className={styles.descCell}>{r.description ?? <span className={styles.muted}>—</span>}</td>
                        <td>{r.status || <span className={styles.muted}>—</span>}</td>
                        <td>
                          <Badge variant={STATE_BADGE[r.state].variant} size="sm">
                            {STATE_BADGE[r.state].label}
                          </Badge>
                          {r.reason && <span className={styles.reason}>{r.reason}</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* ── Step 3: Result ─────────────────────────────────────────── */}
          {step === 'result' && result && (
            <>
              <Alert variant={result.imported > 0 ? 'success' : 'warning'} title="Import complete">
                Imported: <strong>{result.imported}</strong> · Skipped:{' '}
                <strong>{result.skipped}</strong> · Errors: <strong>{result.errors}</strong>
              </Alert>
              {skippedCount > 0 && (
                <button type="button" className={styles.templateLink} onClick={handleErrorReport}>
                  ⬇ Download error report ({skippedCount} row{skippedCount === 1 ? '' : 's'})
                </button>
              )}
            </>
          )}
        </div>

        <footer className={styles.footer}>
          {step === 'upload' && (
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
          )}
          {step === 'preview' && preview && (
            <>
              <Button type="button" variant="ghost" onClick={() => { setStep('upload'); setPreview(null); setError(null); }} disabled={busy}>
                ← Choose another file
              </Button>
              <Button type="button" variant="primary" onClick={handleConfirm} loading={busy} disabled={preview.valid === 0}>
                Import {preview.valid} specialization{preview.valid === 1 ? '' : 's'}
              </Button>
            </>
          )}
          {step === 'result' && (
            <Button type="button" variant="primary" onClick={onClose}>Done</Button>
          )}
        </footer>
      </div>
    </div>
  );
}
