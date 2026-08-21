import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import type { MemberProviderListItem, PaginatedResponse, ProviderType } from '@/types';
import styles from './ProviderDirectoryPage.module.css';

const providerTypeOptions = [
  { value: '', label: 'All provider types' },
  { value: 'HOSPITAL', label: 'Hospitals' },
  { value: 'CLINIC', label: 'Clinics' },
  { value: 'DOCTOR', label: 'Doctors' },
];

const ratingOptions = [
  { value: '', label: 'Any rating' },
  { value: '5', label: '5 stars' },
  { value: '4', label: '4 stars & up' },
  { value: '3', label: '3 stars & up' },
  { value: '2', label: '2 stars & up' },
  { value: '1', label: '1 star & up' },
];

function providerTypeLabel(value: ProviderType): string {
  return value.charAt(0) + value.slice(1).toLowerCase();
}

function Stars({ rating }: { rating: number | null }) {
  if (rating === null) return <span className={styles.noRating}>No ratings yet</span>;
  return <span aria-label={`${rating.toFixed(1)} out of 5 stars`} className={styles.stars}>★ {rating.toFixed(1)}</span>;
}

export function ProviderDirectoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [result, setResult] = useState<PaginatedResponse<MemberProviderListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [locationNotice, setLocationNotice] = useState<string | null>(null);

  const providerType = searchParams.get('provider_type') ?? '';
  const minimumRating = searchParams.get('minimum_rating') ?? '';
  const closestFirst = searchParams.get('closest_first') === 'true';
  const latitude = searchParams.get('latitude');
  const longitude = searchParams.get('longitude');
  const page = Math.max(1, Number(searchParams.get('page') ?? 1));
  const pageSize = Math.min(50, Math.max(1, Number(searchParams.get('page_size') ?? 20)));

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value !== null && value !== '') next.set(key, value);
      else next.delete(key);
    });
    setSearchParams(next);
  }, [searchParams, setSearchParams]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await providersApi.listMemberProviders({
        provider_type: providerType ? providerType as ProviderType : undefined,
        minimum_rating: minimumRating ? Number(minimumRating) : undefined,
        closest_first: closestFirst || undefined,
        latitude: closestFirst && latitude ? Number(latitude) : undefined,
        longitude: closestFirst && longitude ? Number(longitude) : undefined,
        page,
        page_size: pageSize,
      });
      if (page > response.meta.total_pages && response.meta.total > 0) {
        updateParams({ page: '1' });
        return;
      }
      setResult(response);
    } catch (loadError) {
      setError(extractErrorMessage(loadError, 'Providers could not be loaded.'));
    } finally {
      setLoading(false);
    }
  }, [closestFirst, latitude, longitude, minimumRating, page, pageSize, providerType, updateParams]);

  useEffect(() => { void load(); }, [load]);

  const setClosestFirst = () => {
    setLocationNotice(null);
    if (closestFirst) {
      updateParams({ closest_first: null, latitude: null, longitude: null, page: '1' });
      return;
    }
    if (!navigator.geolocation) {
      setLocationNotice('Your browser does not support location access. Providers remain sorted by rating.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        updateParams({
          closest_first: 'true',
          latitude: String(position.coords.latitude),
          longitude: String(position.coords.longitude),
          page: '1',
        });
      },
      () => {
        setLocationNotice('Location access was not available. Providers remain sorted by rating.');
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  };

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Verified member area</p>
          <h1 className="text-display">Find horse care providers</h1>
          <p>Browse active providers, compare feedback, and share your experience.</p>
        </div>
        <Link to="/profile" className={styles.profileLink}>Your profile</Link>
      </header>

      {locationNotice && <Alert variant="info" onDismiss={() => setLocationNotice(null)}>{locationNotice}</Alert>}
      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <section className={styles.filters} aria-label="Provider filters">
        <Select
          label="Provider type"
          options={providerTypeOptions}
          value={providerType}
          onChange={(event) => updateParams({ provider_type: event.target.value || null, page: '1' })}
        />
        <Select
          label="Minimum rating"
          options={ratingOptions}
          value={minimumRating}
          onChange={(event) => updateParams({ minimum_rating: event.target.value || null, page: '1' })}
        />
        <div className={styles.closest}>
          <span className={styles.filterLabel}>Order</span>
          <Button variant={closestFirst ? 'primary' : 'outline'} onClick={setClosestFirst}>
            {closestFirst ? 'Closest first enabled' : 'Sort closest first'}
          </Button>
        </div>
      </section>

      {loading ? (
        <div className={styles.loading} role="status"><LoadingSpinner /> <span>Loading providers…</span></div>
      ) : result?.data.length ? (
        <>
          <p className={styles.resultCount}>{result.meta.total} provider{result.meta.total === 1 ? '' : 's'} found</p>
          <section className={styles.grid} aria-label="Providers">
            {result.data.map((provider) => (
              <article className={styles.card} key={provider.id}>
                <div className={styles.cardTop}>
                  <span className={styles.type}>{providerTypeLabel(provider.provider_type)}</span>
                  <Stars rating={provider.average_rating} />
                </div>
                <h2>{provider.name}</h2>
                <p className={styles.location}>
                  {provider.location
                    ? [provider.location.city, provider.location.state_province, provider.location.country].filter(Boolean).join(', ')
                    : 'Location details unavailable'}
                </p>
                {closestFirst && (
                  <p className={styles.distance}>
                    {provider.distance_km === null ? 'Distance unavailable' : `${provider.distance_km.toFixed(1)} km away`}
                  </p>
                )}
                <p className={styles.description}>{provider.description || 'Provider details are available on their profile.'}</p>
                <p className={styles.reviewCount}>{provider.review_count} review{provider.review_count === 1 ? '' : 's'}</p>
                <Link to={`/providers/${provider.id}${searchParams.toString() ? `?${searchParams}` : ''}`} className={styles.detailLink}>
                  View provider
                </Link>
              </article>
            ))}
          </section>
          <Pagination
            page={page}
            pageSize={pageSize}
            total={result.meta.total}
            onPageChange={(next) => updateParams({ page: String(next) })}
            onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })}
          />
        </>
      ) : (
        <section className={styles.empty} aria-live="polite">
          <h2>No providers match these filters</h2>
          <p>Try removing a filter or check back when more providers are published.</p>
        </section>
      )}
    </main>
  );
}