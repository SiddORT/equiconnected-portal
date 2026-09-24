import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Pagination } from '@/components/ui/Pagination';
import type { MemberProviderListItem, PaginatedResponse, ProviderType } from '@/types';
import styles from './ProviderDirectoryPage.module.css';

type Coordinates = { latitude: number; longitude: number };
function validCoordinates(value: Coordinates | null | undefined): value is Coordinates {
  return !!value && Number.isFinite(value.latitude) && Number.isFinite(value.longitude)
    && value.latitude >= -90 && value.latitude <= 90
    && value.longitude >= -180 && value.longitude <= 180;
}
const typeOptions = [
  { value: '', label: 'Every provider type' },
  { value: 'HOSPITAL', label: 'Hospitals' },
  { value: 'CLINIC', label: 'Clinics' },
  { value: 'DOCTOR', label: 'Doctors' },
];
const ratingOptions = [
  { value: '', label: 'Any rating' },
  { value: '5', label: '5 stars' },
  { value: '4', label: '4 stars and above' },
  { value: '3', label: '3 stars and above' },
  { value: '2', label: '2 stars and above' },
  { value: '1', label: '1 star and above' },
];

function typeLabel(value: ProviderType) {
  return value.charAt(0) + value.slice(1).toLowerCase();
}

function ProviderImage({ provider }: { provider: MemberProviderListItem }) {
  const [failed, setFailed] = useState(false);
  const url = provider.thumbnail_url?.trim();
  useEffect(() => { setFailed(false); }, [url]);
  return url && !failed ? (
    <img className={styles.cardImage} src={url} alt={provider.thumbnail_alt_text?.trim() || `${provider.name} provider`} loading="lazy" onError={() => setFailed(true)} />
  ) : (
    <div className={styles.imageFallback} role="img" aria-label={`No photo available for ${provider.name}`}>
      <img src="/logo.png" alt="" />
      <span>EquiConnected care partner</span>
    </div>
  );
}

function ProviderCard({ provider, query, coordinates }: { provider: MemberProviderListItem; query: string; coordinates: Coordinates | null }) {
  const place = provider.location
    ? [provider.location.city, provider.location.state_province].filter(Boolean).join(', ')
    : 'Location details unavailable';
  return (
    <article className={styles.card}>
      <div className={styles.cardMedia}>
        <ProviderImage provider={provider} />
        <span className={styles.typePill}>{typeLabel(provider.provider_type)}</span>
      </div>
      <div className={styles.cardContent}>
        <div className={styles.cardMeta}><span>{place}</span><span className={styles.rating}>{provider.average_rating === null ? 'New' : `${provider.average_rating.toFixed(1)} / 5`}</span></div>
        <h2>{provider.name}</h2>
        <p className={styles.description}>{provider.description || 'Explore services, reviews, and visit details from this care provider.'}</p>
        <div className={styles.cardBottom}>
          <span>{provider.review_count} review{provider.review_count === 1 ? '' : 's'}</span>
          <Link className={styles.detailLink} state={{ directoryCoordinates: coordinates }} to={`/providers/${provider.id}${query ? `?${query}` : ''}`}>View profile <span aria-hidden="true">↗</span></Link>
        </div>
      </div>
    </article>
  );
}

export function ProviderDirectoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const initialCoordinates = (location.state as { directoryCoordinates?: Coordinates } | null)?.directoryCoordinates;
  const [coordinates, setCoordinates] = useState<Coordinates | null>(
    validCoordinates(initialCoordinates) ? initialCoordinates : null,
  );
  const [result, setResult] = useState<PaginatedResponse<MemberProviderListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
  const [locationPending, setLocationPending] = useState(false);
  const apiRequestId = useRef(0);
  const geoRequestId = useRef(0);
  useEffect(() => () => {
    apiRequestId.current += 1;
    geoRequestId.current += 1;
  }, []);

  const providerType = searchParams.get('provider_type') || '';
  const minimumRating = searchParams.get('minimum_rating') || '';
  const closestFirst = searchParams.get('closest_first') === 'true';
  const withinRadius = searchParams.get('within_working_radius') === 'true';
  const page = Math.max(1, Number(searchParams.get('page') || 1));
  const pageSize = Math.min(50, Math.max(1, Number(searchParams.get('page_size') || 10)));
  const activeFilterCount = Number(Boolean(providerType)) + Number(Boolean(minimumRating)) + Number(withinRadius);
  const locationSortReady = Boolean(coordinates);

  const updateParams = useCallback((updates: Record<string, string | null>, stateCoordinates = coordinates) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    setSearchParams(next, { state: { directoryCoordinates: stateCoordinates } });
  }, [coordinates, searchParams, setSearchParams]);

  const load = useCallback(async () => {
    if ((withinRadius || closestFirst) && !coordinates) {
      setLoading(false);
      return;
    }
    const current = ++apiRequestId.current;
    setLoading(true);
    setError(null);
    try {
      const coords = coordinates;
      const response = await providersApi.listMemberProviders({
        provider_type: providerType ? providerType as ProviderType : undefined,
        minimum_rating: minimumRating ? Number(minimumRating) : undefined,
        closest_first: closestFirst && Boolean(coords) || undefined,
        within_working_radius: withinRadius && Boolean(coords) ? true : undefined,
        latitude: (closestFirst || withinRadius) && coords ? coords.latitude : undefined,
        longitude: (closestFirst || withinRadius) && coords ? coords.longitude : undefined,
        page,
        page_size: pageSize,
      });
      if (current !== apiRequestId.current) return;
      if (page > response.meta.total_pages && response.meta.total > 0) {
        updateParams({ page: '1' });
      } else setResult(response);
    } catch (loadError) {
      if (current === apiRequestId.current) setError(extractErrorMessage(loadError, 'Providers could not be loaded.'));
    } finally {
      if (current === apiRequestId.current) setLoading(false);
    }
  }, [closestFirst, coordinates, minimumRating, page, pageSize, providerType, updateParams, withinRadius]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if ((closestFirst || withinRadius) && !locationSortReady) {
      setLocationMessage('Your location is not available after refresh. Choose a location sort again to restore distance results.');
      updateParams({ within_working_radius: null, closest_first: null });
    }
  }, [closestFirst, locationSortReady, updateParams, withinRadius]);

  const requestLocation = ({ enableClosest = false, enableRadius = false } = {}) => {
    setLocationMessage(null);
    if (!navigator.geolocation) {
      setLocationMessage('Location is not available in this browser. You can still browse the full directory.');
      return;
    }
    const request = ++geoRequestId.current;
    setLocationPending(true);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        if (request !== geoRequestId.current) return;
        if (!validCoordinates(coords)) {
          setLocationPending(false);
          setLocationMessage('Your browser returned an invalid location. Radius filtering is off.');
          updateParams({ within_working_radius: null });
          return;
        }
        const nextCoordinates = { latitude: coords.latitude, longitude: coords.longitude };
        setCoordinates(nextCoordinates);
        setLocationPending(false);
        updateParams({
          closest_first: enableClosest ? 'true' : null,
          within_working_radius: enableRadius ? 'true' : null,
          page: '1',
        }, nextCoordinates);
      },
      () => {
        if (request !== geoRequestId.current) return;
        setLocationPending(false);
        updateParams({ within_working_radius: null });
        setLocationMessage('We could not access your location. Check your browser permission, then try again. Radius filtering is off.');
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  };

  const toggleClosest = () => {
    if (closestFirst) updateParams({ closest_first: null, page: '1' });
    else if (coordinates) updateParams({ closest_first: 'true', page: '1' });
    else requestLocation({ enableClosest: true });
  };
  const toggleRadius = () => {
    if (withinRadius) updateParams({ within_working_radius: null, page: '1' });
    else if (coordinates) updateParams({ within_working_radius: 'true', page: '1' });
    else requestLocation({ enableRadius: true });
  };
  const clearFilters = () => { geoRequestId.current += 1; setLocationPending(false); updateParams({ provider_type: null, minimum_rating: null, within_working_radius: null, closest_first: null, page: '1' }); };
  const query = useMemo(() => searchParams.toString(), [searchParams]);

  return (
    <main className={styles.page}>
      <header className={styles.hero}>
        <div className={styles.heroCopy}>
          <p className={styles.kicker}>The EquiConnected directory</p>
          <h1>Care that meets you <em>where you are.</em></h1>
          <p className={styles.heroText}>A considered network of equine hospitals, clinics, and doctors — connected to the people and horses they serve.</p>
        </div>
        <div className={styles.heroImage}><img src="/horse-panel.jpg" alt="" /><span>Find your next care connection</span></div>
      </header>

      {locationMessage && <Alert variant="info" onDismiss={() => setLocationMessage(null)}>{locationMessage}</Alert>}
      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <section className={styles.toolbar} aria-label="Provider directory filters">
        <div className={styles.filterGroup}>
          <p className={styles.filterTitle}>Refine the network <span>{activeFilterCount ? `${activeFilterCount} active` : 'Browse all'}</span></p>
          <div className={styles.selects}>
            <label>Type<select aria-label="Provider type" value={providerType} onChange={(e) => updateParams({ provider_type: e.target.value || null, page: '1' })}>{typeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label>Rating<select aria-label="Minimum rating" value={minimumRating} onChange={(e) => updateParams({ minimum_rating: e.target.value || null, page: '1' })}>{ratingOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          </div>
        </div>
        <div className={styles.locationTools}>
          <Button variant={closestFirst ? 'primary' : 'outline'} onClick={toggleClosest} disabled={locationPending}>{closestFirst ? 'Closest first' : 'Sort closest first'}</Button>
          <Button variant={withinRadius ? 'primary' : 'outline'} onClick={toggleRadius} disabled={locationPending}>{locationPending ? 'Finding your location…' : withinRadius ? 'Within working radius' : 'Within working radius'}</Button>
          {activeFilterCount > 0 && <button className={styles.clearButton} type="button" onClick={clearFilters}>Clear filters</button>}
          <p className={styles.locationHelp}>Use your location to show only providers who can make stable visits to you.</p>
        </div>
      </section>

      {loading ? <div className={styles.loading} role="status"><LoadingSpinner /><span>Finding connected providers…</span></div> : result?.data.length ? (
        <>
          <div className={styles.resultsHeader}><p><strong>{result.meta.total}</strong> provider{result.meta.total === 1 ? '' : 's'} found</p><span>{closestFirst ? 'Ordered by distance' : 'A living network of care'}</span></div>
          <section className={styles.grid} aria-label="Provider results">{result.data.map((provider) => <ProviderCard key={provider.id} provider={provider} query={query} coordinates={coordinates} />)}</section>
          <Pagination page={page} pageSize={pageSize} total={result.meta.total} onPageChange={(next) => updateParams({ page: String(next) })} onPageSizeChange={(size) => updateParams({ page_size: String(size), page: '1' })} />
        </>
      ) : !error && (
        <section className={styles.empty} aria-live="polite"><p className={styles.kicker}>0 providers found</p><h2>No providers match this view.</h2><p>Try widening your filters or browse the full connected network.</p><Button variant="outline" onClick={clearFilters}>Clear filters</Button></section>
      )}
    </main>
  );
}