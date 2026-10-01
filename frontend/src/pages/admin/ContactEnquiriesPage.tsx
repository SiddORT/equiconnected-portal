import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { getContactEnquiry, listContactEnquiries } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { ErrorState } from '@/components/ui/ErrorState';
import { FilterBar } from '@/components/ui/FilterBar';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Pagination } from '@/components/ui/Pagination';
import { SearchInput } from '@/components/ui/SearchInput';
import type {
  ContactEnquiry,
  ContactEnquiryType,
  LoadingState,
  PaginatedResponse,
} from '@/types';
import styles from './ContactEnquiriesPage.module.css';

const ENQUIRY_TYPE_OPTIONS: Array<{ value: ContactEnquiryType | 'all'; label: string }> = [
  { value: 'all', label: 'All types' },
  { value: 'general', label: 'General enquiry' },
  { value: 'listing', label: 'Listing my practice' },
  { value: 'partnership', label: 'Partnership' },
  { value: 'other', label: 'Other' },
];

function enquiryTypeLabel(value: ContactEnquiryType): string {
  return ENQUIRY_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

function listPath(params: URLSearchParams): string {
  const query = params.toString();
  return `/admin/contact-enquiries${query ? `?${query}` : ''}`;
}

function detailPath(id: string, params: URLSearchParams): string {
  const query = params.toString();
  return `/admin/contact-enquiries/${id}${query ? `?${query}` : ''}`;
}

export function ContactEnquiriesPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') ?? '';
  const rawType = searchParams.get('enquiry_type');
  const enquiryType = rawType && ENQUIRY_TYPE_OPTIONS.some((option) => option.value === rawType)
    ? (rawType === 'all' ? '' : rawType as ContactEnquiryType)
    : '';
  const dateFrom = searchParams.get('date_from') ?? '';
  const dateTo = searchParams.get('date_to') ?? '';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const requestedPageSize = Number(searchParams.get('page_size'));
  const pageSize = [10, 25, 100].includes(requestedPageSize) ? requestedPageSize : 25;
  const [result, setResult] = useState<PaginatedResponse<ContactEnquiry> | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(Boolean(enquiryType || dateFrom || dateTo));
  const queryKey = `${search}|${enquiryType}|${dateFrom}|${dateTo}|${page}|${pageSize}`;
  const currentQueryKeyRef = useRef(queryKey);
  currentQueryKeyRef.current = queryKey;
  const invalidDateRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);

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
    const requestedQueryKey = queryKey;
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setResult(null);
      setErrorMessage(null);
      setLoadState('success');
      return;
    }

    setLoadState('loading');
    setErrorMessage(null);
    try {
      const response = await listContactEnquiries({
        search: search || undefined,
        enquiry_type: enquiryType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: pageSize,
      });
      if (currentQueryKeyRef.current !== requestedQueryKey) return;
      if (page > response.meta.total_pages && response.meta.total > 0) {
        updateParams({ page: '1' });
        return;
      }
      setResult(response);
      setLoadState('success');
    } catch (error) {
      if (currentQueryKeyRef.current !== requestedQueryKey) return;
      setErrorMessage(extractErrorMessage(error, 'Failed to load contact enquiries.'));
      setLoadState('error');
    }
  }, [dateFrom, dateTo, enquiryType, page, pageSize, queryKey, search, updateParams]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: DataTableColumn<ContactEnquiry>[] = [
    {
      key: 'name',
      label: 'Sender',
      width: '1.2fr',
      render: (enquiry) => <strong className={styles.cellText}>{enquiry.name}</strong>,
    },
    {
      key: 'email',
      label: 'Email',
      width: '1.45fr',
      render: (enquiry) => <span className={`${styles.cellText} ${styles.emailCell}`}>{enquiry.email}</span>,
    },
    {
      key: 'enquiry_type',
      label: 'Enquiry type',
      width: '1.25fr',
      render: (enquiry) => (
        <Badge size="sm" variant="info">
          {enquiryTypeLabel(enquiry.enquiry_type)}
        </Badge>
      ),
    },
    {
      key: 'phone',
      label: 'Phone',
      width: '1.1fr',
      render: (enquiry) => <span className={styles.cellText}>{enquiry.phone || 'Not provided'}</span>,
    },
    {
      key: 'submitted_at',
      label: 'Submitted',
      width: '155px',
      render: (enquiry) => (
        <time dateTime={enquiry.submitted_at} className={styles.cellText}>
          {formatTimestamp(enquiry.submitted_at)}
        </time>
      ),
    },
    {
      key: 'actions',
      label: 'Action',
      width: '82px',
      align: 'right',
      render: (enquiry) => (
        <Link
          to={detailPath(enquiry.id, searchParams)}
          className={styles.viewLink}
          aria-label={`View contact enquiry from ${enquiry.name}`}
        >
          View
        </Link>
      ),
    },
  ];

  const hasFilters = Boolean(search || enquiryType || dateFrom || dateTo);

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Contact Enquiries"
        subtitle="Messages submitted through the public contact form."
        breadcrumbs={[
          { label: 'Admin', href: '/admin/dashboard' },
          { label: 'Enquiries', href: '/admin/contact-enquiries' },
          { label: 'Contact Enquiries' },
        ]}
      />

      <div className={styles.body}>
        <div className={styles.toolbar}>
          <SearchInput
            value={search}
            onChange={(value) => updateParams({ search: value || null, page: '1' })}
            placeholder="Search name, email, phone, or message"
            aria-label="Search contact enquiries"
          />
          <Button
            variant="secondary"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
            aria-controls="contact-enquiry-filters"
          >
            Filters
          </Button>
        </div>

        {filtersOpen && (
          <div id="contact-enquiry-filters" className={styles.filterPanel}>
            <FilterBar
              groups={[
                {
                  label: 'Enquiry type',
                  value: enquiryType || 'all',
                  onChange: (value) =>
                    updateParams({
                      enquiry_type: value === 'all' ? null : value,
                      page: '1',
                    }),
                  options: ENQUIRY_TYPE_OPTIONS,
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
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={!hasFilters}
                onClick={() =>
                  updateParams({
                    search: null,
                    enquiry_type: null,
                    date_from: null,
                    date_to: null,
                    page: '1',
                  })
                }
              >
                Clear all filters
              </Button>
            </div>
          </div>
        )}

        {invalidDateRange && (
          <p className={styles.filterError} role="alert">
            Submitted from must be on or before submitted to.
          </p>
        )}

        <div className={styles.tableViewport}>
          <DataTable
            columns={columns}
            data={result?.data ?? []}
            page={page}
            pageSize={pageSize}
            rowKey={(enquiry) => enquiry.id}
            loading={loadState === 'loading'}
            loadingLabel="Loading contact enquiries…"
            error={
              loadState === 'error'
                ? {
                    title: 'Failed to load contact enquiries',
                    message: errorMessage ?? undefined,
                    onRetry: load,
                  }
                : null
            }
            empty={{
              icon: '✉',
              title: hasFilters ? 'No contact enquiries found' : 'No contact enquiries yet',
              description: hasFilters
                ? 'Try adjusting or clearing your search or filters.'
                : 'New messages submitted through the contact form will appear here.',
            }}
            ariaLabel="Contact enquiries"
          />
        </div>
        {loadState === 'success' && result && result.meta.total > 0 && (
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

export function ContactEnquiryDetailPage() {
  const { formatTimestamp } = useTimeSettings();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const [enquiry, setEnquiry] = useState<ContactEnquiry | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const requestId = useRef(0);
  const backToList = listPath(searchParams);

  const load = useCallback(async () => {
    const request = ++requestId.current;
    setLoadState('loading');
    setErrorMessage(null);
    if (!id) {
      setErrorMessage('Contact enquiry was not found.');
      setLoadState('error');
      return;
    }
    try {
      const response = await getContactEnquiry(id);
      if (request !== requestId.current) return;
      setEnquiry(response);
      setLoadState('success');
    } catch (error) {
      if (request !== requestId.current) return;
      setErrorMessage(extractErrorMessage(error, 'Failed to load this contact enquiry.'));
      setLoadState('error');
    }
  }, [id]);

  useEffect(() => {
    void load();
    return () => {
      requestId.current += 1;
    };
  }, [load]);

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Contact Enquiry"
        subtitle="Submitted contact form details."
        breadcrumbs={[
          { label: 'Admin', href: '/admin/dashboard' },
          { label: 'Enquiries', href: '/admin/contact-enquiries' },
          { label: 'Contact Enquiries', href: backToList },
          { label: 'Details' },
        ]}
      />
      <div className={styles.body}>
        <Link to={backToList} className={styles.backLink}>
          ← Back to contact enquiries
        </Link>

        {loadState === 'loading' && (
          <div className={styles.detailLoading}>
            <LoadingSpinner size="lg" label="Loading contact enquiry…" />
          </div>
        )}
        {loadState === 'error' && (
          <ErrorState
            title="Unable to load contact enquiry"
            message={errorMessage ?? 'Please try again.'}
            onRetry={() => void load()}
          />
        )}
        {loadState === 'success' && enquiry && (
          <Card className={styles.detailCard} padding="lg">
            <dl className={styles.details}>
              <dt>Full name</dt>
              <dd>{enquiry.name}</dd>
              <dt>Email</dt>
              <dd><a href={`mailto:${enquiry.email}`}>{enquiry.email}</a></dd>
              <dt>Enquiry type</dt>
              <dd><Badge size="sm" variant="info">{enquiryTypeLabel(enquiry.enquiry_type)}</Badge></dd>
              <dt>Phone</dt>
              <dd>{enquiry.phone || 'Not provided'}</dd>
              <dt>Submitted</dt>
              <dd>
                <time dateTime={enquiry.submitted_at}>{formatTimestamp(enquiry.submitted_at)}</time>
              </dd>
              <dt>Message</dt>
              <dd className={styles.message}>{enquiry.message}</dd>
            </dl>
          </Card>
        )}
      </div>
    </div>
  );
}