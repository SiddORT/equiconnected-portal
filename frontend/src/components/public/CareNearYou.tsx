/**
 * Public provider discovery with a privacy-respecting, opt-in location lookup.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Link } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { listPublicProviders } from '@/api/public';
import { useAuth } from '@/app/AuthContext';
import { hasMemberRole } from '@/features/member/memberAccess';
import type { ProviderType, PublicProviderDiscovery } from '@/types';
import styles from './CareNearYou.module.css';

const TYPE_CONFIG: Record<'blue' | 'brown', Record<ProviderType, { label: string; color: string; shortLabel: string }>> = {
  blue: {
    DOCTOR: { label: 'Doctors', color: '#13866f', shortLabel: 'Doctor' },
    CLINIC: { label: 'Clinics', color: '#2d68a0', shortLabel: 'Clinic' },
    HOSPITAL: { label: 'Hospitals', color: '#a95545', shortLabel: 'Hospital' },
  },
  brown: {
    DOCTOR: { label: 'Doctors', color: '#8e7254', shortLabel: 'Doctor' },
    CLINIC: { label: 'Clinics', color: '#9c7256', shortLabel: 'Clinic' },
    HOSPITAL: { label: 'Hospitals', color: '#9c5f4c', shortLabel: 'Hospital' },
  },
};

const PROVIDER_TYPES: ProviderType[] = ['DOCTOR', 'CLINIC', 'HOSPITAL'];
const DEFAULT_CENTER: L.LatLngExpression = [28.5, 10];

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDistance(distance: number | null): string {
  if (distance === null) return 'Enable location for distance';
  if (distance < 1) return '<1 km away';
  return `${Math.round(distance)} km away`;
}

function formatRating(rating: number | null): string {
  return rating === null ? 'New listing' : `${rating.toFixed(1)} rating`;
}

export function CareNearYou({ theme = 'blue' }: { theme?: 'blue' | 'brown' }) {
  const typeConfig = TYPE_CONFIG[theme];
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerLayerRef = useRef<L.LayerGroup | null>(null);
  const mountedRef = useRef(true);
  const [providers, setProviders] = useState<PublicProviderDiscovery[]>([]);
  const [selectedType, setSelectedType] = useState<ProviderType | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [coordinates, setCoordinates] = useState<{ latitude: number; longitude: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [locationState, setLocationState] = useState<'idle' | 'loading' | 'enabled' | 'error'>('idle');

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError('');

    listPublicProviders(
      coordinates
        ? { latitude: coordinates.latitude, longitude: coordinates.longitude }
        : undefined,
    )
      .then((items) => {
        if (!mounted) return;
        setProviders(items);
        setSelectedId((current) => current && items.some((item) => item.id === current)
          ? current
          : items[0]?.id ?? null);
      })
      .catch((requestError) => {
        if (!mounted) return;
        setError(extractErrorMessage(requestError, 'Provider locations are unavailable right now.'));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [coordinates]);

  const visibleProviders = useMemo(
    () => selectedType
      ? providers.filter((provider) => provider.provider_type === selectedType)
      : providers,
    [providers, selectedType],
  );
  const selectedProvider = visibleProviders.find((provider) => provider.id === selectedId)
    ?? visibleProviders[0]
    ?? null;
  const canAccessMemberDetails = !authLoading
    && isAuthenticated
    && hasMemberRole(user);

  useEffect(() => {
    if (!selectedProvider || selectedProvider.id === selectedId) return;
    setSelectedId(selectedProvider.id);
  }, [selectedId, selectedProvider]);

  useEffect(() => {
    if (!mapContainerRef.current || providers.length === 0 || mapRef.current) return;

    const map = L.map(mapContainerRef.current, {
      scrollWheelZoom: false,
      attributionControl: true,
    });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    const markerLayer = L.layerGroup().addTo(map);
    mapRef.current = map;
    markerLayerRef.current = markerLayer;
    map.setView(DEFAULT_CENTER, 2);
    const invalidateTimer = window.setTimeout(() => map.invalidateSize(), 0);

    return () => {
      window.clearTimeout(invalidateTimer);
      map.remove();
      mapRef.current = null;
      markerLayerRef.current = null;
    };
  }, [providers.length]);

  useEffect(() => {
    const map = mapRef.current;
    const markerLayer = markerLayerRef.current;
    if (!map || !markerLayer) return;

    markerLayer.clearLayers();
    const bounds = L.latLngBounds([]);

    visibleProviders.forEach((provider) => {
      const isSelected = provider.id === selectedProvider?.id;
      const color = typeConfig[provider.provider_type].color;
      const marker = L.circleMarker(
        [provider.location.latitude, provider.location.longitude],
        {
          radius: isSelected ? 12 : 9,
          color: theme === 'brown' ? '#fff8ed' : '#fffdf4',
          weight: isSelected ? 3 : 2,
          fillColor: color,
          fillOpacity: 0.95,
        },
      );
      marker.bindTooltip(provider.name, { direction: 'top', offset: [0, -8] });
      marker.bindPopup(
        `<strong>${escapeHtml(provider.name)}</strong><br/>` +
        `${typeConfig[provider.provider_type].shortLabel} · ${escapeHtml(provider.location.city)}`,
      );
      marker.on('click', () => setSelectedId(provider.id));
      marker.addTo(markerLayer);
      bounds.extend([provider.location.latitude, provider.location.longitude]);
    });

    if (visibleProviders.length === 1) {
      map.setView(
        [visibleProviders[0].location.latitude, visibleProviders[0].location.longitude],
        12,
      );
    } else if (visibleProviders.length > 1) {
      map.fitBounds(bounds, { padding: [36, 36], maxZoom: 12 });
    }
  }, [selectedProvider?.id, theme, typeConfig, visibleProviders]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedProvider) return;
    map.setView(
      [selectedProvider.location.latitude, selectedProvider.location.longitude],
      Math.max(map.getZoom(), 10),
      { animate: true },
    );
  }, [selectedProvider]);

  function requestLocation() {
    if (!navigator.geolocation) {
      setLocationState('error');
      return;
    }

    setLocationState('loading');
    navigator.geolocation.getCurrentPosition(
      ({ coords: position }) => {
        if (!mountedRef.current) return;
        setCoordinates({ latitude: position.latitude, longitude: position.longitude });
        setLocationState('enabled');
      },
      () => {
        if (mountedRef.current) setLocationState('error');
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
    );
  }

  return (
    <section id="care-near-you" className={styles.section} aria-labelledby="care-near-you-heading">
      <div className={styles.intro} data-scroll-reveal>
        <div>
          <p className={styles.eyebrow}><span aria-hidden="true" />Care near you</p>
          <h2 id="care-near-you-heading">Healthcare is closer than you think.</h2>
          <p className={styles.description}>
            Find equine care teams in your area, from independent doctors to full-service clinics
            and hospitals. Start with the providers already connected to EquiConnected.
          </p>
        </div>
        <div className={styles.introActions}>
          <button
            type="button"
            className={styles.locationButton}
            data-gsap-hover
            onClick={requestLocation}
            disabled={locationState === 'loading'}
          >
            <span aria-hidden="true">⌖</span>
            {locationState === 'loading' ? 'Finding you…' : 'Use my location'}
          </button>
          <Link to={canAccessMemberDetails ? '/providers' : '/login'} className={styles.primaryCta} data-gsap-hover>FIND CARE NEAR ME <span aria-hidden="true">↗</span></Link>
        </div>
      </div>

      <div className={styles.explorer} data-scroll-reveal>
        <div className={styles.mapColumn} data-scroll-reveal>
          <div className={styles.mapHeader}>
            <div>
              <p className={styles.panelKicker}>The care map</p>
              <h3>Trusted care, within reach.</h3>
            </div>
            <div className={styles.typeFilters} role="group" aria-label="Filter providers by type">
               <button
                type="button"
                className={`${styles.typeButton} ${selectedType === null ? styles.typeButtonActive : ''}`}
                 data-gsap-hover
                onClick={() => setSelectedType(null)}
                aria-pressed={selectedType === null}
              >
                All
              </button>
              {PROVIDER_TYPES.map((type) => (
                 <button
                  key={type}
                  type="button"
                  className={`${styles.typeButton} ${selectedType === type ? styles.typeButtonActive : ''}`}
                   data-gsap-hover
                  onClick={() => setSelectedType((current) => current === type ? null : type)}
                  aria-pressed={selectedType === type}
                >
                  <span className={styles.typeDot} style={{ backgroundColor: typeConfig[type].color }} aria-hidden="true" />
                  {typeConfig[type].label}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.mapFrame}>
            {providers.length > 0 && <div ref={mapContainerRef} className={styles.map} role="region" aria-label="Map of nearby equine care providers" />}
            {loading && (
              <div className={styles.mapMessage} role="status">
                <span className={styles.loadingDot} aria-hidden="true" />
                Loading connected providers…
              </div>
            )}
            {!loading && error && (
              <div className={styles.mapMessage} role="alert">
                <strong>We couldn&apos;t load the care map.</strong>
                <span>{error}</span>
              </div>
            )}
            {!loading && !error && providers.length === 0 && (
              <div className={styles.mapMessage} role="status">
                <span className={styles.emptyIcon} aria-hidden="true">⌁</span>
                <strong>Care locations are on the way.</strong>
                <span>Join EquiConnected to be notified as the network grows.</span>
              </div>
            )}
            {!loading && !error && providers.length > 0 && visibleProviders.length === 0 && (
              <div className={styles.mapMessage} role="status">
                <strong>No {selectedType ? typeConfig[selectedType].label.toLowerCase() : 'providers'} shown.</strong>
                <span>Try another provider type.</span>
              </div>
            )}
          </div>
          <p className={styles.mapNote}>
            {locationState === 'enabled'
              ? 'Showing distances from your selected location.'
              : locationState === 'error'
                ? 'Location access was unavailable. You can still browse the map.'
                : 'Allow location access to see how far each provider is from you.'}
          </p>
        </div>

        <aside className={styles.providerPanel} aria-labelledby="nearby-providers-heading" data-scroll-reveal>
          <div className={styles.panelHeading}>
            <div>
              <p className={styles.panelKicker}>A few places to start</p>
              <h3 id="nearby-providers-heading">Nearby providers</h3>
            </div>
            {canAccessMemberDetails && providers.length > 0 && (
              <span className={styles.resultCount}>{visibleProviders.length} shown</span>
            )}
          </div>
          <div className={styles.cards}>
            {authLoading && (
              <div className={styles.memberGate} role="status">
                <strong>Checking member access…</strong>
                <span>Provider details will appear after your session is restored.</span>
              </div>
            )}
            {!authLoading && !canAccessMemberDetails && (
              <div className={styles.memberGate}>
                <strong>Please log in or register as a member to see more details.</strong>
                <div className={styles.memberGateActions}>
                  <Link
                    to="/login"
                    state={{ from: { pathname: '/' } }}
                    className={styles.memberGateLink}
                    aria-label="Log in as a member"
                  >
                    Log in as a member
                  </Link>
                  <Link
                    to="/signup"
                    className={styles.memberGateLink}
                    aria-label="Register as a member"
                  >
                    Register as a member
                  </Link>
                </div>
              </div>
            )}
            {canAccessMemberDetails && visibleProviders.map((provider) => {
              const type = typeConfig[provider.provider_type];
              const selected = provider.id === selectedProvider?.id;
              return (
                <div
                  key={provider.id}
                  className={`${styles.providerCard} ${selected ? styles.providerCardSelected : ''}`}
                >
                  <button type="button" className={styles.cardSelect} onClick={() => setSelectedId(provider.id)} aria-pressed={selected}>
                  <span className={styles.cardTopline}>
                    <span className={styles.providerType} style={{ color: type.color }}>
                      <span className={styles.typeDot} style={{ backgroundColor: type.color }} aria-hidden="true" />
                      {type.shortLabel}
                    </span>
                    <span className={styles.cardArrow} aria-hidden="true">↗</span>
                  </span>
                  <strong className={styles.providerName}>{provider.name}</strong>
                  <span className={styles.specializations}>
                    {provider.specializations.length > 0
                      ? provider.specializations.slice(0, 2).join(' · ')
                      : `${type.shortLabel} care`}
                  </span>
                  <span className={styles.cardMeta}>
                    <span>{provider.average_rating === null ? '☆' : '★'} {formatRating(provider.average_rating)}</span>
                    <span>{provider.review_count} {provider.review_count === 1 ? 'review' : 'reviews'}</span>
                  </span>
                  <span className={styles.distance}>{formatDistance(provider.distance_km)}</span>
                  </button>
                  <Link
                    to={`/providers/${provider.id}`}
                    state={{ fromCareNearYou: true }}
                    className={styles.cardDetailLink}
                    onFocus={() => setSelectedId(provider.id)}
                  >
                    View full details <span aria-hidden="true">→</span>
                  </Link>
                </div>
              );
            })}
            {canAccessMemberDetails && !loading && !error && providers.length > 0 && visibleProviders.length === 0 && (
              <p className={styles.panelEmpty}>Choose another filter to see connected providers.</p>
            )}
            {canAccessMemberDetails && loading && <p className={styles.panelEmpty}>Finding connected care near you…</p>}
            {canAccessMemberDetails && error && <p className={styles.panelEmpty}>Please try again later, or continue to member search.</p>}
            {canAccessMemberDetails && !loading && !error && providers.length === 0 && (
              <p className={styles.panelEmpty}>The network is growing. Check back soon for nearby listings.</p>
            )}
          </div>
          <Link
            to={canAccessMemberDetails ? '/providers' : '/login'}
            state={!canAccessMemberDetails ? { from: { pathname: '/providers' } } : undefined}
            className={styles.panelLink}
          >
            Explore the full provider directory <span aria-hidden="true">→</span>
          </Link>
        </aside>
      </div>
    </section>
  );
}