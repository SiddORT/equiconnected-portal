import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type DataTableColumn } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { PageHeader } from '@/components/layout/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import type { AdminProviderReview, PaginatedResponse } from '@/types';
import styles from './ReviewsPage.module.css';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function readPositiveInteger(value: string | null, fallback: number, max: number) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 1 && parsed <= max ? parsed : fallback;
}

export function ReviewsPage() {
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [result, setResult] = useState<PaginatedResponse<AdminProviderReview> | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const rawProviderId = searchParams.get('provider_id');
  const providerId = rawProviderId && UUID_PATTERN.test(rawProviderId) ? rawProviderId : null;
  const rawVisibility = searchParams.get('comment_visible');
  const visibility = rawVisibility === 'visible' || rawVisibility === 'hidden' ? rawVisibility : 'all';
  const page = readPositiveInteger(searchParams.get('page'), 1, Number.MAX_SAFE_INTEGER);
  const requestedPageSize = readPositiveInteger(searchParams.get('page_size'), 25, 100);
  const pageSize = [10, 25, 100].includes(requestedPageSize) ? requestedPageSize : 25;
  const queryKey = `${providerId ?? ''}|${visibility}|${page}|${pageSize}`;
  const currentQueryKeyRef = useRef(queryKey);
  currentQueryKeyRef.current = queryKey;

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });
    setSearchParams(next);
  }, [searchParams, setSearchParams]);

  const normalizationUpdates: Record<string, string | null> = {};
  if (rawProviderId !== null && providerId === null) normalizationUpdates.provider_id = null;
  if (rawVisibility !== null && rawVisibility !== 'visible' && rawVisibility !== 'hidden') {
    normalizationUpdates.comment_visible = null;
  }
  const rawPage = searchParams.get('page');
  if (rawPage !== null && rawPage !== String(page)) {
    normalizationUpdates.page = String(page);
  }
  const rawPageSize = searchParams.get('page_size');
  if (rawPageSize !== null && rawPageSize !== String(pageSize)) {
    normalizationUpdates.page_size = String(pageSize);
  }
  const needsNormalization = Object.keys(normalizationUpdates).length > 0;
  const normalizationKey = Object.entries(normalizationUpdates)
    .map(([key, value]) => `${key}:${value ?? ''}`)
    .join('|');

  const load = useCallback(async () => {
    const requestedQueryKey = queryKey;
    setLoadState('loading');
    setError(null);
    try {
      const response = await adminApi.listAdminReviews({
        provider_id: providerId ?? undefined,
        comment_visible: visibility === 'all' ? undefined : visibility === 'visible',
        page,
        page_size: pageSize,
      });
      if (page > response.meta.total_pages && response.meta.total > 0) {
        if (currentQueryKeyRef.current === requestedQueryKey) {
          updateParams({ page: '1' });
        }
        return;
      }
      if (currentQueryKeyRef.current !== requestedQueryKey) return;
      setResult(response);
      setLoadState('success');
    } catch (loadError) {
      if (currentQueryKeyRef.current !== requestedQueryKey) return;
      setError(extractErrorMessage(loadError, 'Reviews could not be loaded.'));
      setLoadState('error');
    }
  }, [page, pageSize, providerId, queryKey, updateParams, visibility]);

  useEffect(() => {
    if (needsNormalization) {
      updateParams(normalizationUpdates);
      return;
    }
    void load();
  }, [load, needsNormalization, normalizationKey, updateParams]);

  const toggleVisibility = async (item: AdminProviderReview) => {
    setUpdating(item.id);
    setError(null);
    try {
      const updated = await adminApi.setAdminReviewCommentVisibility(item.id, !item.comment_visible);
      setResult((current) => current && ({
        ...current,
        data: current.data.map((review) => review.id === updated.id ? updated : review),
      }));
    } catch (toggleError) {
      setError(extractErrorMessage(toggleError, 'Comment visibility could not be updated.'));
    } finally {
      setUpdating(null);
    }
  };

  const columns: DataTableColumn<AdminProviderReview>[] = [
    { key: 'provider_name', label: 'Provider', width: '1.1fr', render: (item) => <strong>{item.provider_name}</strong> },
    { key: 'reviewer', label: 'Reviewer', width: '1.1fr', hideOnMobile: true, render: (item) => <span>{item.reviewer_name}<small className={styles.email}>{item.reviewer_email}</small></span> },
    { key: 'rating', label: 'Rating', width: '80px', render: (item) => <span className={styles.rating}>★ {item.rating}</span> },
    { key: 'comment', label: 'Comment', width: '2fr', hideOnMobile: true, render: (item) => <span className={styles.comment}>{item.comment || 'No comment provided'}</span> },
    { key: 'comment_visible', label: 'Visibility', width: '95px', render: (item) => <Badge size="sm" variant={item.comment_visible ? 'success' : 'neutral'}>{item.comment_visible ? 'Visible' : 'Hidden'}</Badge> },
    { key: 'created_at', label: 'Date', width: '105px', hideOnMobile: true, render: (item) => <time dateTime={item.created_at}>{formatTimestamp(item.created_at)}</time> },
    { key: 'actions', label: 'Action', width: '100px', align: 'right', render: (item) => <Button size="sm" variant={item.comment_visible ? 'outline' : 'secondary'} loading={updating === item.id} onClick={() => void toggleVisibility(item)}>{item.comment_visible ? 'Hide' : 'Restore'}</Button> },
  ];
  const scopedProviderName = result?.data[0]?.provider_name;

  return (
    <div className={styles.shell}>
      <PageHeader title="Provider reviews" subtitle="Review member feedback and hide or restore comment text without affecting ratings." breadcrumbs={[{ label: 'Admin' }, { label: 'Reviews' }]} />
      <div className={styles.body}>
        {error && <p className={styles.error} role="alert">{error}</p>}
        {providerId && (
          <div className={styles.scopeBanner} role="status">
            <span>
              Showing reviews for <strong>{scopedProviderName ?? 'selected provider'}</strong>
            </span>
            <Button size="sm" variant="outline" onClick={() => updateParams({ provider_id: null, page: '1' })}>
              View all reviews
            </Button>
          </div>
        )}
        <FilterBar
          groups={[{
            label: 'Comment visibility',
            value: visibility,
            onChange: (value) => updateParams({ comment_visible: value === 'all' ? null : value, page: '1' }),
            options: [{ value: 'all', label: 'All reviews' }, { value: 'visible', label: 'Visible' }, { value: 'hidden', label: 'Hidden' }],
          }]}
        />
        <DataTable
          ariaLabel="Provider reviews"
          columns={columns}
          data={result?.data ?? []}
          page={page}
          pageSize={pageSize}
          rowKey={(item) => item.id}
          loading={loadState === 'loading'}
          error={loadState === 'error' ? { title: 'Failed to load reviews', message: error ?? undefined, onRetry: load } : null}
          empty={{
            icon: '★',
            title: 'No reviews found',
            description: providerId
              ? 'This provider has no reviews matching the selected filters.'
              : visibility === 'all'
                ? 'Member reviews will appear here.'
                : 'Try selecting a different visibility filter.',
          }}
        />
        {loadState === 'success' && result && <Pagination page={page} pageSize={pageSize} total={result.meta.total} onPageChange={(next) => updateParams({ page: String(next) })} onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })} />}
      </div>
    </div>
  );
}