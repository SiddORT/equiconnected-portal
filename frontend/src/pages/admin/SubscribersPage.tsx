import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { exportSubscribers, listSubscribers } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { Input } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import type {
  LoadingState,
  PaginatedResponse,
  Subscriber,
  SubscriberRegistrationType,
} from '@/types';
import styles from './SubscribersPage.module.css';

const TYPE_OPTIONS: Array<{ value: SubscriberRegistrationType | 'all'; label: string }> = [
  { value: 'all', label: 'All types' },
  { value: 'VET', label: 'Vet' },
  { value: 'HORSE_OWNER', label: 'Horse Owner' },
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'CLINIC', label: 'Clinic' },
  { value: 'STABLE_MANAGER', label: 'Stable Manager' },
  { value: 'OTHER', label: 'Other' },
];

function registrationTypeLabel(value: SubscriberRegistrationType): string {
  return TYPE_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export function SubscribersPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') ?? '';
  const rawType = searchParams.get('registration_type');
  const registrationType = rawType !== 'all' && TYPE_OPTIONS.some((option) => option.value === rawType)
    ? (rawType as SubscriberRegistrationType)
    : '';
  const dateFrom = searchParams.get('date_from') ?? '';
  const dateTo = searchParams.get('date_to') ?? '';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pageSize = [10, 25, 50, 100].includes(Number(searchParams.get('page_size')))
    ? Number(searchParams.get('page_size'))
    : 25;
  const [result, setResult] = useState<PaginatedResponse<Subscriber> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(Boolean(registrationType || dateFrom || dateTo));
  const filterPanelRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      Object.entries(updates).forEach(([key, value]) => {
        if (value) next.set(key, value);
        else next.delete(key);
      });
      setSearchParams(next);
    },
    [searchParams, setSearchParams]
  );

  const load = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const response = await listSubscribers({
        search: search || undefined,
        registration_type: registrationType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: pageSize,
      });
      if (page > response.meta.total_pages && response.meta.total > 0) {
        updateParams({ page: '1' });
        return;
      }
      setResult(response);
      setLoadState('success');
    } catch (error) {
      setErrorMessage(extractErrorMessage(error, 'Failed to load subscribers.'));
      setLoadState('error');
    }
  }, [dateFrom, dateTo, page, pageSize, registrationType, search, updateParams]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: DataTableColumn<Subscriber>[] = [
    {
      key: 'email',
      label: 'Email address',
      width: '1.8fr',
      render: (subscriber) => <span className={styles.emailCell}>{subscriber.email}</span>,
    },
    {
      key: 'registration_type',
      label: 'Register as',
      width: '1.2fr',
      render: (subscriber) => (
        <Badge size="sm" variant="info">
          {registrationTypeLabel(subscriber.registration_type)}
        </Badge>
      ),
    },
    {
      key: 'submitted_at',
      label: 'Submitted',
      width: '150px',
      hideOnMobile: true,
      render: (subscriber) => (
        <time dateTime={subscriber.submitted_at}>
          {formatTimestamp(subscriber.submitted_at)}
        </time>
      ),
    },
  ];

  const hasFilters = Boolean(search || registrationType || dateFrom || dateTo);

  const handleExport = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      await exportSubscribers({
        search: search || undefined,
        registration_type: registrationType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
    } catch (error) {
      setExportError(extractErrorMessage(error, 'Unable to prepare the subscriber export. Please try again.'));
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Subscribers"
        subtitle="People who asked EquiConnected to reach out before launch."
        breadcrumbs={[{ label: 'Admin' }, { label: 'Subscribers' }]}
      />
      <div className={styles.body}>
        <div className={styles.toolbar}>
          <SearchInput
            value={search}
            onChange={(value) => updateParams({ search: value || null, page: '1' })}
            placeholder="Search email address"
            aria-label="Search subscribers"
          />
          <Button
            variant="secondary"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
            aria-controls="subscriber-filters"
          >
            Filters
          </Button>
          <Button
            variant="outline"
            onClick={() => void handleExport()}
            loading={isExporting}
          >
            {isExporting ? 'Preparing export…' : 'Export CSV'}
          </Button>
        </div>
        {filtersOpen && (
          <div id="subscriber-filters" ref={filterPanelRef} className={styles.filterPanel}>
            <FilterBar
              groups={[
                {
                  label: 'Registration type',
                  value: registrationType || 'all',
                  onChange: (value: string) =>
                    updateParams({
                      registration_type: value === 'all' ? null : value,
                      page: '1',
                    }),
                  options: TYPE_OPTIONS,
                },
              ]}
            />
            <div className={styles.dateFilters}>
              <Input
                type="date"
                label="Submitted from"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(event) =>
                  updateParams({ date_from: event.target.value || null, page: '1' })
                }
              />
              <Input
                type="date"
                label="Submitted to"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(event) =>
                  updateParams({ date_to: event.target.value || null, page: '1' })
                }
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
            </div>
          </div>
        )}
        {exportError && <p className={styles.exportError} role="alert">{exportError}</p>}
        <DataTable
          columns={columns}
          data={result?.data ?? []}
          page={page}
          pageSize={pageSize}
          rowKey={(subscriber) => subscriber.id}
          loading={loadState === 'loading'}
          loadingLabel="Loading subscribers…"
          error={
            loadState === 'error'
              ? { title: 'Failed to load subscribers', message: errorMessage ?? undefined, onRetry: load }
              : null
          }
          empty={{
            icon: '✉',
            title: hasFilters ? 'No subscribers found' : 'No subscribers yet',
            description: hasFilters
              ? 'Try adjusting or clearing your search, type, or submitted-date filters.'
              : 'New launch registrations will appear here.',
          }}
          ariaLabel="Subscribers"
        />
        {loadState === 'success' && result && (
          <Pagination
            page={page}
            pageSize={pageSize}
            total={result.meta.total}
            onPageChange={(next) => updateParams({ page: String(next) })}
            onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })}
          />
        )}
      </div>
    </div>
  );
}