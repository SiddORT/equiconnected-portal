/**
 * DataTable — generic admin table with Sr. No. column, loading/empty/error
 * states, and column-driven cell rendering. No module-specific logic inside.
 */
import React from 'react';
import { Card } from './Card';
import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';
import { LoadingSpinner } from './LoadingSpinner';
import { srNo } from './Pagination';
import styles from './DataTable.module.css';

export interface DataTableColumn<T> {
  key: string;
  label: string;
  /** Custom cell renderer; defaults to `String(row[key])`. */
  render?: (row: T, rowIndex: number) => React.ReactNode;
  /** CSS grid track for the column, e.g. '1.5fr' or '120px'. Default '1fr'. */
  width?: string;
  /** Hide this column below 768px. */
  hideOnMobile?: boolean;
  align?: 'left' | 'center' | 'right';
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  /** Used for cross-page Sr. No. numbering. */
  page: number;
  pageSize: number;
  rowKey: (row: T) => string;
  loading?: boolean;
  loadingLabel?: string;
  empty?: { icon?: React.ReactNode; title: string; description?: string; action?: React.ReactNode };
  error?: { title?: string; message?: string; onRetry?: () => void } | null;
  ariaLabel?: string;
}

export function DataTable<T>({
  columns,
  data,
  page,
  pageSize,
  rowKey,
  loading = false,
  loadingLabel = 'Loading…',
  empty,
  error,
  ariaLabel = 'Data table',
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className={styles.centered}>
        <LoadingSpinner size="lg" label={loadingLabel} />
      </div>
    );
  }

  if (error) {
    return <ErrorState title={error.title} message={error.message} onRetry={error.onRetry} />;
  }

  if (data.length === 0) {
    return (
      <EmptyState
        icon={empty?.icon}
        title={empty?.title ?? 'No records found'}
        description={empty?.description}
        action={empty?.action}
      />
    );
  }

  const gridTemplateColumns = ['48px', ...columns.map((c) => c.width ?? '1fr')].join(' ');

  const cellClass = (col: DataTableColumn<T>) =>
    [
      styles.cell,
      col.align === 'center' ? styles['cell--center'] : '',
      col.align === 'right' ? styles['cell--right'] : '',
      col.hideOnMobile ? styles['cell--hideMobile'] : '',
    ]
      .filter(Boolean)
      .join(' ');

  return (
    <Card padding="none" shadow="sm">
      <div role="table" aria-label={ariaLabel} className={styles.table}>
        <div role="rowgroup">
          <div role="row" className={`${styles.row} ${styles.headerRow}`} style={{ gridTemplateColumns }}>
            <span role="columnheader" className={styles.srNoCol}>Sr. No.</span>
            {columns.map((col) => (
              <span key={col.key} role="columnheader" className={cellClass(col)}>
                {col.label}
              </span>
            ))}
          </div>
        </div>

        <div role="rowgroup">
          {data.map((row, index) => (
            <div key={rowKey(row)} role="row" className={styles.row} style={{ gridTemplateColumns }}>
              <span role="cell" className={`${styles.srNoCol} ${styles.srNoCell}`}>
                {srNo(page, pageSize, index)}
              </span>
              {columns.map((col) => (
                <span key={col.key} role="cell" className={cellClass(col)}>
                  {col.render
                    ? col.render(row, index)
                    : String((row as Record<string, unknown>)[col.key] ?? '—')}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
