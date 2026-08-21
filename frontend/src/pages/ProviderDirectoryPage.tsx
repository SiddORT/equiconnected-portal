import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { useTimeSettings } from '@/app/TimeSettingsContext';
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

function ProviderCard({
  provider,
  closestFirst,
  search,
}: {
  provider: MemberProviderListItem;
  closestFirst: boolean;
  search: string;
}) {
  const [imageUnavailable, setImageUnavailable] = useState(false);
  const thumbnailUrl = provider.thumbnail_url?.trim() || null;
  const locationName = provider.location
    ? [provider.location.city, provider.location.state_province, provider.location.country].filter(Boolean).join(', ')
    : 'Location details unavailable';
  const imageAlt = provider.thumbnail_alt_text?.trim() || `${provider.name} provider`;
  const detailPath = `/providers/${provider.id}${search ? `?${search}` : ''}`;

  useEffect(() => {
    setImageUnavailable(false);
  }, [thumbnailUrl]);

  return (
    <article className={styles.card}>
      <div className={styles.cardMedia}>
        {thumbnailUrl && !imageUnavailable ? (
          <img
            src={thumbnailUrl}
            alt={imageAlt}
            className={styles.cardImage}
            loading="lazy"
            decoding="async"
            onError={() => setImageUnavailable(true)}
          />
        ) : (
          <div className={styles.imageFallback} role="img" aria-label={`No photo available for ${provider.name}`}>
            <span aria-hidden="true">✦</span>
            <p>EquiConnected care partner</p>
          </div>
        )}
        <span className={styles.type}>{providerTypeLabel(provider.provider_type)}</span>
      </div>
      <div className={styles.cardBody}>
        <div className={styles.cardTop}>
          <p className={styles.location}>{locationName}</p>
          <Stars rating={provider.average_rating} />
        </div>
        <h2>{provider.name}</h2>
        {closestFirst && (
          <p className={styles.distance}>
            {provider.distance_km === null ? 'Distance unavailable' : `${provider.distance_km.toFixed(1)} km away`}
          </p>
        )}
        <p className={styles.description}>{provider.description || 'Provider details are available on their profile.'}</p>
        <div className={styles.cardFooter}>
          <p className={styles.reviewCount}>{provider.review_count} review{provider.review_count === 1 ? '' : 's'}</p>
          <Link to={detailPath} className={styles.detailLink} aria-label={`View ${provider.name}`}>
            View provider <span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>
    </article>
  );
}

export function ProviderDirectoryPage() {
  const { user } = useAuth();
  const { formatTimestamp } = useTimeSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [result, setResult] = useState<PaginatedResponse<MemberProviderListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [locationNotice, setLocationNotice] = useState<string | null>(null);
  const sliderRef = useRef<HTMLDivElement>(null);
  const [sliderBounds, setSliderBounds] = useState({ canPrevious: false, canNext: false });

  const providerType = searchParams.get('provider_type') ?? '';
  const minimumRating = searchParams.get('minimum_rating') ?? '';
  const closestFirst = searchParams.get('closest_first') === 'true';
  const latitude = searchParams.get('latitude');
  const longitude = searchParams.get('longitude');
  const page = Math.max(1, Number(searchParams.get('page') ?? 1));
  const pageSize = Math.min(50, Math.max(1, Number(searchParams.get('page_size') ?? 20)));
  const lastSignIn = user?.last_successful_login_at
    ? new Date(user.last_successful_login_at)
    : null;
  const hasLastSignIn = lastSignIn !== null && !Number.isNaN(lastSignIn.getTime());
  const firstName = user?.first_name?.trim() || user?.full_name?.split(' ')[0] || 'there';

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

  const updateSliderBounds = useCallback(() => {
    const slider = sliderRef.current;
    if (!slider) return;
    const maxScroll = slider.scrollWidth - slider.clientWidth;
    setSliderBounds({
      canPrevious: slider.scrollLeft > 1,
      canNext: maxScroll > 1 && slider.scrollLeft < maxScroll - 1,
    });
  }, []);

  useEffect(() => {
    const slider = sliderRef.current;
    if (!slider) return;
    slider.scrollLeft = 0;
    updateSliderBounds();
    slider.addEventListener('scroll', updateSliderBounds, { passive: true });
    window.addEventListener('resize', updateSliderBounds);
    return () => {
      slider.removeEventListener('scroll', updateSliderBounds);
      window.removeEventListener('resize', updateSliderBounds);
    };
  }, [result?.data, updateSliderBounds]);

  const scrollSlider = useCallback((direction: -1 | 1) => {
    const slider = sliderRef.current;
    if (!slider) return;
    const amount = Math.max(slider.clientWidth * 0.85, 280);
    if (typeof slider.scrollBy === 'function') {
      slider.scrollBy({ left: amount * direction });
    } else {
      slider.scrollLeft += amount * direction;
      slider.dispatchEvent(new Event('scroll'));
    }
  }, []);

  const handleSliderKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      scrollSlider(1);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      scrollSlider(-1);
    }
  };

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
      <header className={styles.header} data-testid="member-dashboard-hero" aria-labelledby="dashboard-welcome-heading">
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>Your EquiConnected circle</p>
          <h1 id="dashboard-welcome-heading" className="text-display">Welcome back, {firstName}.</h1>
          <p className={styles.heroMessage}>Find the care team that keeps every ride, recovery, and routine moving forward.</p>
          <div className={styles.heroDetails}>
            <span className={styles.sessionMarker} aria-hidden="true" />
            <p className={styles.signInTime}>
              {hasLastSignIn ? (
                <>
                  Last successful sign-in:{' '}
                  <time dateTime={user!.last_successful_login_at!}>
                    {formatTimestamp(user!.last_successful_login_at!)}
                  </time>
                </>
              ) : (
                'Your member session is ready.'
              )}
            </p>
          </div>
          <Link to="/profile" className={styles.profileLink}>
            <span>View your profile</span>
            <span aria-hidden="true">→</span>
          </Link>
        </div>
        <div className={styles.heroArt} aria-hidden="true">
          <div className={styles.horseImageFrame}>
            <img src="/horse-panel.jpg" alt="" />
            <span className={styles.artLabel}>Care, connected</span>
          </div>
          <div className={styles.stableImageFrame}>
            <img src="/stable-panel.jpg" alt="" />
          </div>
          <span className={styles.artCaption}>For every chapter of the journey</span>
        </div>
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
          <section className={styles.slider} aria-label="Provider results">
            <div className={styles.sliderHeader}>
              <p className={styles.sliderHint}>Swipe through {result.data.length} current result{result.data.length === 1 ? '' : 's'} or use the controls</p>
              <div className={styles.sliderControls} aria-label="Provider result controls">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => scrollSlider(-1)}
                  disabled={!sliderBounds.canPrevious}
                  aria-controls="provider-results-slider"
                  aria-label="Previous providers"
                >
                  ← Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => scrollSlider(1)}
                  disabled={!sliderBounds.canNext}
                  aria-controls="provider-results-slider"
                  aria-label="Next providers"
                >
                  Next →
                </Button>
              </div>
            </div>
            <div
              ref={sliderRef}
              id="provider-results-slider"
              className={styles.sliderViewport}
              tabIndex={0}
              role="region"
              aria-label="Provider results slider"
              aria-keyshortcuts="ArrowLeft ArrowRight"
              onKeyDown={handleSliderKeyDown}
            >
              {result.data.map((provider) => (
                <ProviderCard
                  key={provider.id}
                  provider={provider}
                  closestFirst={closestFirst}
                  search={searchParams.toString()}
                />
              ))}
            </div>
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