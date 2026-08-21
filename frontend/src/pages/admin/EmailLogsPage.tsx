import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getEmailDeliveryLogs } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { Input } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import type {
  EmailDeliveryLog,
  EmailLogFilterMode,
  LoadingState,
  PaginatedResponse,
} from '@/types';
import styles from './EmailLogsPage.module.css';

const FILTER_OPTIONS = [
  { value: '', label: 'All dates' },
  { value: 'day', label: 'Specific day' },
  { value: 'month', label: 'Month' },
  { value: 'year', label: 'Year' },
  { value: 'range', label: 'Custom range' },
];

function purposeLabel(purpose: EmailDeliveryLog['purpose']): string {
  if (purpose === 'provider_invitation') return 'Provider profile invitation';
  if (purpose === 'provider_portal_access') return 'Provider portal access';
  if (purpose === 'subscriber_confirmation') return 'Subscriber confirmation';
  return 'Account verification';
}

function selectedPeriod(
  mode: EmailLogFilterMode | '',
  date: string,
  month: string,
  year: string,
  dateFrom: string,
  dateTo: string,
): string {
  if (mode === 'day' && date) return `Showing ${date}`;
  if (mode === 'month' && month) return `Showing ${month}`;
  if (mode === 'year' && year) return `Showing ${year}`;
  if (mode === 'range' && dateFrom && dateTo) return `Showing ${dateFrom} through ${dateTo}`;
  return 'Showing all email attempts';
}

function isFilterComplete(
  mode: EmailLogFilterMode | '',
  date: string,
  month: string,
  year: string,
  dateFrom: string,
  dateTo: string,
): boolean {
  return (
    !mode
    || (mode === 'day' && !!date)
    || (mode === 'month' && !!month)
    || (mode === 'year' && !!year)
    || (mode === 'range' && !!dateFrom && !!dateTo)
  );
}

export function EmailLogsPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const rawMode = searchParams.get('filter_mode');
  const filterMode: EmailLogFilterMode | '' =
    rawMode === 'day' || rawMode === 'month' || rawMode === 'year' || rawMode === 'range'
      ? rawMode
      : '';
  const filterDate = searchParams.get('date') ?? '';
  const filterMonth = searchParams.get('month') ?? '';
  const filterYear = searchParams.get('year') ?? '';
  const dateFrom = searchParams.get('date_from') ?? '';
  const dateTo = searchParams.get('date_to') ?? '';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pageSize = [10, 25, 50, 100].includes(Number(searchParams.get('page_size')))
    ? Number(searchParams.get('page_size'))
    : 25;
  const [result, setResult] = useState<PaginatedResponse<EmailDeliveryLog> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const filterIsComplete = isFilterComplete(
    filterMode, filterDate, filterMonth, filterYear, dateFrom, dateTo,
  );

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const load = useCallback(async () => {
    if (!filterIsComplete) {
      setErrorMessage(null);
      setLoadState('success');
      return;
    }
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const [monthYear, monthValue] = filterMonth.split('-');
      const response = await getEmailDeliveryLogs({
        filter_mode: filterMode || undefined,
        date: filterMode === 'day' ? filterDate || undefined : undefined,
        month: filterMode === 'month' && monthValue ? Number(monthValue) : undefined,
        year: filterMode === 'month' && monthYear
          ? Number(monthYear)
          : filterMode === 'year' && filterYear
            ? Number(filterYear)
            : undefined,
        date_from: filterMode === 'range' ? dateFrom || undefined : undefined,
        date_to: filterMode === 'range' ? dateTo || undefined : undefined,
        page,
        page_size: pageSize,
      });
      setResult(response);
      setLoadState('success');
    } catch (error) {
      setErrorMessage(extractErrorMessage(error, 'Failed to load email logs.'));
      setLoadState('error');
    }
  }, [
    dateFrom, dateTo, filterDate, filterIsComplete, filterMode, filterMonth, filterYear, page, pageSize,
  ]);

  useEffect(() => { void load(); }, [load]);

  const setFilterMode = (nextMode: string) => {
    updateParams({
      filter_mode: nextMode || null,
      date: null,
      month: null,
      year: null,
      date_from: null,
      date_to: null,
      page: '1',
    });
  };

  const columns = useMemo<DataTableColumn<EmailDeliveryLog>[]>(() => [
    {
      key: 'created_at',
      label: 'Sent',
      width: '1.3fr',
      render: (entry) => <time dateTime={entry.created_at}>{formatTimestamp(entry.created_at)}</time>,
    },
    {
      key: 'recipient_email',
      label: 'To',
      width: '1.2fr',
      render: (entry) => <span className={styles.address}>{entry.recipient_email}</span>,
    },
    {
      key: 'purpose',
      label: 'For',
      width: '1.25fr',
      render: (entry) => purposeLabel(entry.purpose),
    },
    {
      key: 'status',
      label: 'Status',
      width: '1.2fr',
      render: (entry) => (
        <span className={styles.status}>
          <Badge
            size="sm"
            variant={
              entry.status === 'success'
                ? 'success'
                : entry.status === 'pending'
                  ? 'warning'
                  : 'error'
            }
          >
            {entry.status === 'success'
              ? 'Accepted by SMTP'
              : entry.status === 'pending'
                ? 'Outcome pending'
                : 'Failed'}
          </Badge>
          {entry.failure_message && <small>{entry.failure_message}</small>}
        </span>
      ),
    },
  ], [formatTimestamp]);

  const data = result?.data ?? [];
  const meta = result?.meta;
  const incompleteFilter = !filterIsComplete;

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Email Logs"
        subtitle="SMTP handoff attempts for invitations, account verification, and subscriber confirmations."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Email Logs' }]}
      />
      <div className={styles.body}>
        <form className={styles.filters} onSubmit={(event) => event.preventDefault()}>
          <Select
            label="Date filter"
            value={filterMode}
            options={FILTER_OPTIONS}
            onChange={(event) => setFilterMode(event.target.value)}
          />
          {filterMode === 'day' && (
            <Input
              type="date"
              label="Day"
              value={filterDate}
              onChange={(event) => updateParams({ date: event.target.value || null, page: '1' })}
            />
          )}
          {filterMode === 'month' && (
            <Input
              type="month"
              label="Month"
              value={filterMonth}
              onChange={(event) => updateParams({ month: event.target.value || null, page: '1' })}
            />
          )}
          {filterMode === 'year' && (
            <Input
              type="number"
              label="Year"
              value={filterYear}
              min="2000"
              max="9999"
              inputMode="numeric"
              onChange={(event) => updateParams({ year: event.target.value || null, page: '1' })}
            />
          )}
          {filterMode === 'range' && (
            <>
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
            </>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!filterMode}
            onClick={() => setFilterMode('')}
          >
            Clear filter
          </Button>
        </form>
        <p className={styles.period} aria-live="polite">
          {incompleteFilter ? 'Choose the remaining date value to apply this filter.' : selectedPeriod(
            filterMode, filterDate, filterMonth, filterYear, dateFrom, dateTo,
          )}
        </p>

        <DataTable
          columns={columns}
          data={data}
          page={page}
          pageSize={pageSize}
          rowKey={(entry) => entry.id}
          loading={loadState === 'loading'}
          loadingLabel="Loading email logs…"
          error={loadState === 'error' ? {
            title: 'Failed to load email logs',
            message: errorMessage ?? undefined,
            onRetry: load,
          } : null}
          empty={{
            icon: '✉',
            title: 'No email attempts found',
            description: filterMode
              ? 'Try clearing or widening the selected period.'
              : 'Future transactional email attempts will appear here.',
          }}
          ariaLabel="Email delivery logs"
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