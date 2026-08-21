import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getActivityLogs } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { Input } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Pagination';
import type { ActivityLog, LoadingState, PaginatedResponse } from '@/types';
import styles from './ActivityLogsPage.module.css';

function valueLabel(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

export function ActivityLogsPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const dateFrom = searchParams.get('date_from') ?? '';
  const dateTo = searchParams.get('date_to') ?? '';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pageSize = [10, 25, 50, 100].includes(Number(searchParams.get('page_size')))
    ? Number(searchParams.get('page_size'))
    : 25;
  const [result, setResult] = useState<PaginatedResponse<ActivityLog> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const load = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const response = await getActivityLogs({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: pageSize,
      });
      setResult(response);
      setLoadState('success');
    } catch (error) {
      setErrorMessage(extractErrorMessage(error, 'Failed to load activity logs.'));
      setLoadState('error');
    }
  }, [dateFrom, dateTo, page, pageSize]);

  useEffect(() => { void load(); }, [load]);

  const columns = useMemo<DataTableColumn<ActivityLog>[]>(() => [
    {
      key: 'created_at',
      label: 'When',
      width: '1.25fr',
      render: (event) => <time dateTime={event.created_at}>{formatTimestamp(event.created_at)}</time>,
    },
    {
      key: 'actor',
      label: 'Actor',
      width: '1fr',
      render: (event) => (
        <span className={styles.actor}>
          <strong>{event.actor.name}</strong>
          {event.actor.email && <small>{event.actor.email}</small>}
        </span>
      ),
    },
    {
      key: 'action',
      label: 'Activity',
      width: '2fr',
      render: (event) => (
        <span className={styles.activity}>
          <Badge size="sm" variant={event.action.includes('failed') ? 'error' : 'info'}>
            {event.action.replace(/_/g, ' ')}
          </Badge>
          <span>{event.summary}</span>
        </span>
      ),
    },
    {
      key: 'changes',
      label: 'Details',
      width: '1.7fr',
      hideOnMobile: true,
      render: (event) => event.changes.length ? (
        <details className={styles.changes}>
          <summary>{event.changes.length} changed field{event.changes.length === 1 ? '' : 's'}</summary>
          <dl>
            {event.changes.map((change, index) => (
              <div key={`${change.field}-${index}`}>
                <dt>{change.field.replace(/_/g, ' ')}</dt>
                <dd><s>{valueLabel(change.before)}</s> → {valueLabel(change.after)}</dd>
              </div>
            ))}
          </dl>
        </details>
      ) : <span className={styles.muted}>No field values recorded</span>,
    },
  ], []);

  const data = result?.data ?? [];
  const meta = result?.meta;
  return (
    <div className={styles.shell}>
      <PageHeader
        title="Activity Logs"
        subtitle="A chronological history of meaningful administrator and invitation activity."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Activity Logs' }]}
      />
      <div className={styles.body}>
        <form className={styles.filters} onSubmit={(event) => event.preventDefault()}>
          <Input
            type="date"
            label="From date"
            value={dateFrom}
            max={dateTo || undefined}
            onChange={(event) => updateParams({ date_from: event.target.value || null, page: '1' })}
          />
          <Input
            type="date"
            label="To date"
            value={dateTo}
            min={dateFrom || undefined}
            onChange={(event) => updateParams({ date_to: event.target.value || null, page: '1' })}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!dateFrom && !dateTo}
            onClick={() => updateParams({ date_from: null, date_to: null, page: '1' })}
          >
            Clear dates
          </Button>
        </form>

        <DataTable
          columns={columns}
          data={data}
          page={page}
          pageSize={pageSize}
          rowKey={(event) => event.id}
          loading={loadState === 'loading'}
          loadingLabel="Loading activity logs…"
          error={loadState === 'error' ? {
            title: 'Failed to load activity logs',
            message: errorMessage ?? undefined,
            onRetry: load,
          } : null}
          empty={{
            icon: '📋',
            title: 'No activity logs found',
            description: dateFrom || dateTo
              ? 'Try clearing or widening the date range.'
              : 'Activity will appear here as portal actions are completed.',
          }}
          ariaLabel="Activity logs"
        />
        {loadState === 'success' && meta && meta.total > 0 && (
          <Pagination
            page={meta.page}
            pageSize={meta.page_size}
            total={meta.total}
            onPageChange={(nextPage) => updateParams({ page: String(nextPage) })}
            onPageSizeChange={(nextSize) => updateParams({ page_size: String(nextSize), page: '1' })}
          />
        )}
      </div>
    </div>
  );
}