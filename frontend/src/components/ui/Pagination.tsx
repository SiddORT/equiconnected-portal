/**
 * Pagination — "Show entries" dropdown, info string, and Previous/Next buttons.
 * Shared by all paginated admin tables.
 */
import { Button } from './Button';
import styles from './Pagination.module.css';

export const PAGE_SIZE_OPTIONS = [10, 25, 100] as const;

/** Sr. No. for a row: cross-page numbering shared by DataTable and pages. */
export function srNo(page: number, pageSize: number, rowIndex: number): number {
  return (page - 1) * pageSize + rowIndex + 1;
}

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange, onPageSizeChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className={styles.pagination} aria-label="Pagination">
      <label className={styles.pageSizeLabel}>
        Show entries:
        <select
          className={styles.pageSizeSelect}
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          aria-label="Rows per page"
        >
          {PAGE_SIZE_OPTIONS.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </label>

      <span className={styles.paginationInfo}>
        Showing {from} to {to} of {total} entries
      </span>

      <div className={styles.paginationBtns}>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page === 1}
        >
          ← Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
        >
          Next →
        </Button>
      </div>
    </div>
  );
}
