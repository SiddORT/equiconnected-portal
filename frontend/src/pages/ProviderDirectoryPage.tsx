import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import * as profileApi from '@/api/profile';
import { historyFilters, recordMemberHistory } from '@/api/memberHistoryRecording';
import {
  hasSensitiveTrafficUrlParameter,
  isNewTrafficNavigation,
  recordMemberTrafficView,
  type TrafficRouteLocation,
} from '@/analytics/trafficTracking';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Pagination } from '@/components/ui/Pagination';
import { SaveProviderButton } from '@/components/member/SaveProviderButton';
import { VisitingProviderInvitation } from '@/components/member/VisitingProviderInvitation';
import type { Horse, MemberProviderListItem, PaginatedResponse, ProviderType, VisitStability } from '@/types';
import styles from './ProviderDirectoryPage.module.css';

type Coordinates = { latitude: number; longitude: number };
type Facets = { specializations: { id: string; name: string }[]; regions: string[] };
type State = { key: string; status: 'ready' | 'error'; data?: PaginatedResponse<MemberProviderListItem>; message?: string };
const validCoordinates = (value?: { latitude?: number | null; longitude?: number | null } | null): value is Coordinates =>
  !!value && typeof value.latitude === 'number' && typeof value.longitude === 'number'
  && Number.isFinite(value.latitude) && Number.isFinite(value.longitude)
  && Math.abs(value.latitude) <= 90 && Math.abs(value.longitude) <= 180;
const filterKeys = ['name', 'visit_stability', 'specialization_id', 'region', 'provider_type', 'minimum_rating', 'emergency_only', 'within_working_radius', 'closest_first', 'horse_id'];
const draftKeys = ['name', 'visit_stability', 'specialization_id', 'region', 'provider_type', 'minimum_rating', 'emergency_only'];
const labelType = (value: ProviderType) => value.charAt(0) + value.slice(1).toLowerCase();

function ProviderImage({ provider }: { provider: MemberProviderListItem }) {
  const [failed, setFailed] = useState(false);
  const url = provider.thumbnail_url?.trim();
  return url && !failed
    ? <img className={styles.cardImage} src={url} alt={provider.thumbnail_alt_text?.trim() || provider.name} loading="lazy" onError={() => setFailed(true)} />
    : <div className={styles.imageFallback} role="img" aria-label={`No photo available for ${provider.name}`}><img src="/logo.png" alt="" /><span>EquiConnected care partner</span></div>;
}

function ProviderCard({ provider, query, coordinates, onSavedChange, distanceContext }: { provider: MemberProviderListItem; query: string; coordinates: Coordinates | null; onSavedChange: (saved: boolean) => void; distanceContext?: string }) {
  const place = [provider.location?.city, provider.location?.state_province].filter(Boolean).join(', ') || 'Location not listed';
  const to = `/providers/${provider.id}${query ? `?${query}` : ''}`;
  return <article className={styles.card}>
    <div className={styles.cardMedia}><ProviderImage key={provider.thumbnail_url} provider={provider} /></div>
    <div className={styles.cardContent}>
      <p className={styles.typePill}>{labelType(provider.provider_type)}</p>
      <h2>{provider.name}</h2>
      <p className={styles.place}>{place}</p>
      <div className={styles.tags}>
        {provider.specializations?.map(name => <span key={name}>{name}</span>)}
        {provider.visit_stability === 'STABLE_VISIT' && <span>Stable visits</span>}
        {provider.emergency_services_available && <span>Emergency services</span>}
      </div>
      <p className={styles.rating}>{provider.average_rating === null ? 'Not yet rated' : `★ ${provider.average_rating.toFixed(1)}`} · {provider.review_count} review{provider.review_count === 1 ? '' : 's'}
        {provider.distance_km != null && <> · {provider.distance_km} km {distanceContext ?? 'from your location'}</>}
      </p>
      <div className={styles.cardBottom}>
        <Link className={styles.detailLink} state={{ directoryCoordinates: coordinates, directoryLocationGranted: !!coordinates }} to={to}>View profile <span aria-hidden="true">↗</span></Link>
        <Link className={styles.contactLink} state={{ directoryCoordinates: coordinates, directoryLocationGranted: !!coordinates }} to={`${to}#contact`}>Contact details</Link>
        <SaveProviderButton id={provider.id} name={provider.name} saved={provider.is_saved} onChange={onSavedChange} />
      </div>
    </div>
  </article>;
}

export function ProviderDirectoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const previousLocation = location.state as { directoryCoordinates?: Coordinates; directoryLocationGranted?: boolean } | null;
  const initialCoordinates = previousLocation?.directoryCoordinates;
  // Only explicitly granted browser coordinates are kept here, never a horse's location.
  const [coordinates, setCoordinates] = useState<Coordinates | null>(
    previousLocation?.directoryLocationGranted && validCoordinates(initialCoordinates) ? initialCoordinates : null,
  );
  const [horses, setHorses] = useState<Horse[]>([]);
  const [horsesLoading, setHorsesLoading] = useState(true);
  const [horsesError, setHorsesError] = useState<string | null>(null);
  const [draft, setDraft] = useState(() => new URLSearchParams(searchParams));
  const [more, setMore] = useState(false);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [facetsError, setFacetsError] = useState(false);
  const [result, setResult] = useState<State | null>(null);
  const [retry, setRetry] = useState(0);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
  const [locationPending, setLocationPending] = useState(false);
  const geoRequestId = useRef(0);
  const filtersRef = useRef<HTMLSelectElement>(null);
  const requestId = useRef(0);
  const lastRecordedSearch = useRef<string | null>(null);
  const trafficLocation = useRef<TrafficRouteLocation | null>(null);
  const horseLoadId = useRef(0);
  useEffect(() => () => { geoRequestId.current++; requestId.current++; }, []);
  const query = searchParams.toString();
  const closestFirst = searchParams.get('closest_first') === 'true';
  const withinRadius = searchParams.get('within_working_radius') === 'true';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pageSize = Math.min(50, Math.max(1, Number(searchParams.get('page_size')) || 10));
  const view = searchParams.get('view') === 'grid' ? 'grid' : 'list';
  const savedOnly = searchParams.get('saved') === 'true';
  const sort = searchParams.get('sort') === 'name' ? 'name' : 'relevance';
  const horseId = searchParams.get('horse_id') || '';
  const selectedHorse = horses.find((horse) => horse.id === horseId);
  const horseLocation = selectedHorse?.effective_location;
  const horseUsable = !!horseLocation?.available && validCoordinates(horseLocation);
  const horseSelectionPending = !!horseId && horsesLoading;
  const horseSelectionInvalid = !!horseId && !horsesLoading && (!!horsesError || !selectedHorse || !horseUsable);
  const needsLocation = !horseId && (closestFirst || withinRadius);
  const key = `${query}|${horseId ? `horse:${horseId}` : needsLocation ? `${coordinates?.latitude},${coordinates?.longitude}` : ''}`;
  const current = result?.key === key ? result : null;
  const ready = !horseSelectionPending && !horseSelectionInvalid && current?.status === 'ready' ? current.data : undefined;

  const updateParams = useCallback((updates: Record<string, string | null>, stateCoordinates = coordinates) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([name, value]) => value ? next.set(name, value) : next.delete(name));
    const browserCoordinates = next.has('horse_id') ? null : stateCoordinates;
    setSearchParams(next, { state: { directoryCoordinates: browserCoordinates, directoryLocationGranted: !!browserCoordinates } });
  }, [coordinates, searchParams, setSearchParams]);
  useEffect(() => { setDraft(new URLSearchParams(searchParams)); }, [query]);
  const loadHorses = useCallback(() => {
    const id = ++horseLoadId.current;
    setHorsesLoading(true);
    setHorsesError(null);
    profileApi.getProfile().then((profile) => {
      if (id !== horseLoadId.current) return;
      setHorses(profile.horses ?? []);
    }).catch((error) => {
      if (id === horseLoadId.current) setHorsesError(extractErrorMessage(error, 'Your horse locations could not be loaded.'));
    }).finally(() => { if (id === horseLoadId.current) setHorsesLoading(false); });
  }, []);
  useEffect(() => {
    loadHorses();
    const refresh = () => loadHorses();
    window.addEventListener('focus', refresh);
    window.addEventListener('popstate', refresh);
    window.addEventListener('member-profile-changed', refresh);
    return () => {
      horseLoadId.current++;
      window.removeEventListener('focus', refresh);
      window.removeEventListener('popstate', refresh);
      window.removeEventListener('member-profile-changed', refresh);
    };
  }, [loadHorses]);
  useEffect(() => {
    let alive = true;
    providersApi.getMemberProviderFilters().then(data => { if (alive) { setFacets(data); setFacetsError(false); } })
      .catch(() => { if (alive) setFacetsError(true); });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (needsLocation && !coordinates) {
      setLocationMessage('Your location is not available after refresh. Choose a location option again to restore distance results.');
      updateParams({ within_working_radius: null, closest_first: null });
    }
  }, [needsLocation, coordinates, updateParams]);
  useEffect(() => {
    if (horseSelectionPending || horseSelectionInvalid || (needsLocation && !coordinates)) return;
    const id = ++requestId.current;
    const requestedKey = key;
    providersApi.listMemberProviders({
      saved_only: savedOnly || undefined,
      name: searchParams.get('name')?.trim() || undefined,
      provider_type: (searchParams.get('provider_type') || undefined) as ProviderType | undefined,
      visit_stability: (searchParams.get('visit_stability') || undefined) as VisitStability | undefined,
      specialization_id: searchParams.get('specialization_id') || undefined,
      region: searchParams.get('region') || undefined,
      emergency_only: searchParams.get('emergency_only') === 'true' || undefined,
      minimum_rating: searchParams.get('minimum_rating') ? Number(searchParams.get('minimum_rating')) : undefined,
      sort: horseId ? undefined : sort,
      closest_first: horseId ? undefined : closestFirst || undefined,
      within_working_radius: horseId ? undefined : withinRadius || undefined,
      latitude: !horseId && needsLocation ? coordinates!.latitude : undefined,
      longitude: !horseId && needsLocation ? coordinates!.longitude : undefined,
      horse_id: horseId || undefined,
      page, page_size: pageSize,
    }).then(data => {
      if (id !== requestId.current) return;
      if (page > data.meta.total_pages && data.meta.total > 0) updateParams({ page: '1' });
      else {
        setResult({ key: requestedKey, status: 'ready', data });
        const historyParams = new URLSearchParams(searchParams);
        historyParams.delete('horse_id');
        const filters = historyFilters(historyParams);
        const signature = JSON.stringify(filters);
        if (Object.keys(filters).length && signature !== lastRecordedSearch.current) {
          void recordMemberHistory({
            event_key: `search:${location.key}`,
            type: 'search', filters,
          });
        }
        lastRecordedSearch.current = signature;
      }
    }).catch(error => {
      if (id === requestId.current) setResult({ key: requestedKey, status: 'error', message: extractErrorMessage(error, 'Providers could not be loaded.') });
    });
    return () => { requestId.current++; };
  }, [key, retry, horseSelectionPending, horseSelectionInvalid]); // exact horse location remains server-side

  useEffect(() => {
    if (!ready) return;
    const currentLocation: TrafficRouteLocation = {
      key: location.key,
      pathname: location.pathname,
      search: location.search,
      hash: location.hash,
      category: 'provider_directory',
    };
    if (
      !hasSensitiveTrafficUrlParameter(location.search, location.hash)
      && isNewTrafficNavigation(trafficLocation.current, currentLocation)
    ) {
      recordMemberTrafficView('provider_directory');
    }
    trafficLocation.current = currentLocation;
  }, [
    ready,
    location.hash,
    location.key,
    location.pathname,
    location.search,
  ]);

  const setDraftValue = (name: string, value: string) => setDraft(previous => {
    const next = new URLSearchParams(previous);
    if (value) next.set(name, value); else next.delete(name);
    return next;
  });
  const apply = (event: React.FormEvent) => {
    event.preventDefault();
    const updates: Record<string, string | null> = { page: '1' };
    draftKeys.forEach(name => { updates[name] = name === 'name' ? draft.get(name)?.trim() || null : draft.get(name); });
    updateParams(updates);
  };
  const clearFilters = () => {
    geoRequestId.current++;
    setLocationPending(false);
    const updates: Record<string, string | null> = { page: '1' };
    filterKeys.forEach(name => { updates[name] = null; });
    setDraft(new URLSearchParams());
    updateParams(updates);
  };
  const requestLocation = (kind: 'closest_first' | 'within_working_radius') => {
    setLocationMessage(null);
    if (!navigator.geolocation) {
      setLocationMessage('Location is not available in this browser. You can still browse the directory.');
      return;
    }
    const id = ++geoRequestId.current;
    setLocationPending(true);
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      if (id !== geoRequestId.current) return;
      setLocationPending(false);
      if (!validCoordinates(coords)) {
        setLocationMessage('Your browser returned an invalid location. Location filtering is off.');
        return;
      }
      const next = { latitude: coords.latitude, longitude: coords.longitude };
      setCoordinates(next);
      updateParams({ horse_id: null, [kind]: 'true', page: '1' }, next);
    }, () => {
      if (id !== geoRequestId.current) return;
      setLocationPending(false);
      setLocationMessage('We could not access your location. Check your browser permission, then try again. Location filtering is off.');
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
  };
  const toggleLocation = (kind: 'closest_first' | 'within_working_radius') => {
    if (!horseId && searchParams.get(kind) === 'true') updateParams({ [kind]: null, page: '1' });
    else if (coordinates) updateParams({ horse_id: null, [kind]: 'true', page: '1' });
    else requestLocation(kind);
  };
  const modify = () => { setMore(true); filtersRef.current?.focus(); };

  return <main className={styles.page}>
    <header className={styles.intro}>
      <p className={styles.kicker}>The EquiConnected directory</p>
      <h1>{savedOnly ? 'Saved providers' : 'Find the Right Care for Your Horse'}</h1>
      <p>{savedOnly ? 'Your personal shortlist of providers currently available in the directory.' : 'Discover published equine professionals, clinics and hospitals. Refine by the care you need.'}</p>
      <div className={styles.savedNavigation}>
        <button type="button" aria-pressed={!savedOnly} onClick={() => updateParams({ saved: null, page: '1' })}>All providers</button>
        <button type="button" aria-pressed={savedOnly} onClick={() => updateParams({ saved: 'true', page: '1' })}>Saved providers</button>
      </div>
    </header>
    <VisitingProviderInvitation query={query} directoryState={{ directoryCoordinates: horseId ? null : coordinates, directoryLocationGranted: !horseId && !!coordinates }} />
    {locationMessage && <Alert variant="info" onDismiss={() => setLocationMessage(null)}>{locationMessage}</Alert>}
    <section className={styles.horseFilter} aria-label="Search by horse location">
      <div className={styles.horseFilterCopy}>
        <span className={styles.horseEyebrow}>Horse location</span>
        <strong>Find care near a horse</strong>
        <span>Only your horses are shown. Their exact locations stay private.</span>
      </div>
      <label className={styles.horseSelectLabel} htmlFor="horse-location-filter">Search around</label>
      <select id="horse-location-filter" className={styles.horseSelect} value={horseId} disabled={horsesLoading || !!horsesError} onChange={(event) => {
        const id = event.target.value || null;
        geoRequestId.current++;
        setLocationPending(false);
        setCoordinates(null);
        setLocationMessage(null);
        updateParams({ horse_id: id, closest_first: null, within_working_radius: null, page: '1' });
      }}>
        <option value="">{horsesLoading ? 'Loading your horses…' : 'Choose a horse'}</option>
        {horses.map((horse) => <option key={horse.id} value={horse.id}>{horse.name}{horse.effective_location?.available && validCoordinates(horse.effective_location) ? ' · Location ready' : ' · Location needed'}</option>)}
      </select>
      {horsesError && <div className={styles.horseSetup}><span role="alert">{horsesError}</span><button type="button" onClick={() => {
        loadHorses();
      }}>Reload horse options</button></div>}
      {horseId && selectedHorse && !horseUsable && <div className={styles.horseSetup} role="status">
        <span>{horseLocation?.reason || 'This horse does not have a usable saved location yet.'}</span>
        <Link to="/profile?section=horses">Edit Horse Info</Link>
        <button type="button" onClick={() => updateParams({ horse_id: null, page: '1' })}>Clear horse filter</button>
      </div>}
      {horseId && !horsesLoading && !selectedHorse && <div className={styles.horseSetup} role="status">
        <span>{horsesError ? 'Your horse list could not be verified. Retry loading it or clear this filter.' : 'This horse is no longer available in your profile. Choose another horse or clear this filter.'}</span>
        <button type="button" onClick={() => updateParams({ horse_id: null, page: '1' })}>Clear horse filter</button>
      </div>}
      {horseId && selectedHorse && horseUsable && <div className={styles.horseActive} role="status">
        Showing stable-visiting care by distance from <strong>{selectedHorse.name}</strong>
        <span>{[horseLocation?.city, horseLocation?.state_province, horseLocation?.country].filter(Boolean).join(', ') || 'Saved horse location'} · {selectedHorse.location_mode === 'stable' ? 'Linked to current stable location' : 'Custom horse location'}</span>
        <button type="button" onClick={() => updateParams({ horse_id: null, page: '1' })}>Clear</button>
      </div>}
    </section>
    <form className={styles.toolbar} aria-label="Provider directory filters" onSubmit={apply}>
      <div className={`${styles.filterSegment} ${styles.nameSegment}`}>
        <label htmlFor="provider-name-filter">Provider name</label>
        <input id="provider-name-filter" type="search" maxLength={200} placeholder="Search by name" value={draft.get('name') || ''} onChange={e => setDraftValue('name', e.target.value)} />
      </div>
      <div className={styles.filterSegment}>
        <label htmlFor="visit-filter">1 · Visit type</label>
        <select id="visit-filter" ref={filtersRef} disabled={!!horseId} value={horseId ? 'STABLE_VISIT' : draft.get('visit_stability') || ''} onChange={e => setDraftValue('visit_stability', e.target.value)}>
          <option value="">All visits</option><option value="STABLE_VISIT">Stable visits</option><option value="NOT_STABLE_VISIT">At provider location</option>
        </select>
      </div>
      <div className={styles.filterSegment}>
        <label htmlFor="specialization-filter">2 · Specialization</label>
        <select id="specialization-filter" value={draft.get('specialization_id') || ''} onChange={e => setDraftValue('specialization_id', e.target.value)}>
          <option value="">Any specialization</option>{facets?.specializations.map(spec => <option key={spec.id} value={spec.id}>{spec.name}</option>)}
        </select>
      </div>
      <div className={styles.filterSegment}>
        <label htmlFor="region-filter">3 · Region / emirate</label>
        <select id="region-filter" value={draft.get('region') || ''} onChange={e => setDraftValue('region', e.target.value)}>
          <option value="">All regions</option>{facets?.regions.map(region => <option key={region} value={region}>{region}</option>)}
        </select>
      </div>
      <button type="button" className={styles.moreButton} aria-expanded={more} aria-controls="more-filters" onClick={() => setMore(!more)}>☷ More filters</button>
      <button className={styles.applyButton} type="submit">Apply filters <span aria-hidden="true">→</span></button>
      {more && <div id="more-filters" className={styles.extraFilters}>
        <label>Provider type <select aria-label="Provider type" value={draft.get('provider_type') || ''} onChange={e => setDraftValue('provider_type', e.target.value)}><option value="">Any type</option><option value="DOCTOR">Doctors</option><option value="CLINIC">Clinics</option><option value="HOSPITAL">Hospitals</option></select></label>
        <label>Minimum rating <select aria-label="Minimum rating" value={draft.get('minimum_rating') || ''} onChange={e => setDraftValue('minimum_rating', e.target.value)}><option value="">Any rating</option>{[5, 4, 3, 2, 1].map(n => <option key={n} value={n}>{n}+ stars</option>)}</select></label>
        <label className={styles.checkbox}><input type="checkbox" checked={draft.get('emergency_only') === 'true'} onChange={e => setDraftValue('emergency_only', e.target.checked ? 'true' : '')} /> Emergency services only</label>
        <button type="button" aria-pressed={!horseId && closestFirst} disabled={locationPending} onClick={() => toggleLocation('closest_first')}>Sort closest first</button>
        <button type="button" aria-pressed={!horseId && withinRadius} disabled={locationPending} onClick={() => toggleLocation('within_working_radius')}>{locationPending ? 'Finding your location…' : 'Within working radius'}</button>
        <p>These options switch to your browser location and clear the horse filter. Working radius uses each provider’s listed location and straight-line distance.</p>
        <button type="button" className={styles.clearButton} onClick={clearFilters}>Clear filters</button>
      </div>}
    </form>
    {facetsError && <p className={styles.facetsError} role="status">Filter choices could not be loaded. You can still browse providers and use the other filters.</p>}
    <div className={styles.resultsHeader}>
      <p aria-live="polite">{ready ? <><strong>{ready.meta.total}</strong> provider{ready.meta.total === 1 ? '' : 's'} found</> : current?.status === 'error' ? 'Results unavailable' : 'Finding providers…'}</p>
      <div className={styles.resultTools}>
        <label>Sort <select aria-label="Sort providers" disabled={!!horseId} value={horseId ? 'horse-distance' : sort} onChange={e => updateParams({ sort: e.target.value === 'name' ? 'name' : null, page: '1' })}>{horseId && <option value="horse-distance">Nearest to horse</option>}<option value="relevance">Relevance</option><option value="name">Name A–Z</option></select></label>
        <div className={styles.viewSwitch} role="group" aria-label="Result view">
          <button type="button" aria-label="Grid view" aria-pressed={view === 'grid'} onClick={() => updateParams({ view: 'grid' })}>▦</button>
          <button type="button" aria-label="List view" aria-pressed={view === 'list'} onClick={() => updateParams({ view: null })}>☰</button>
        </div>
      </div>
    </div>
    <section className={styles.results} aria-label="Provider results" aria-busy={!current} aria-live="polite">
      {horseSelectionPending ? <div className={styles.loading} role="status">Checking your horse’s saved location…</div>
      : horseSelectionInvalid ? <div className={styles.statePanel} role="status">
        <span className={styles.stateIcon} aria-hidden="true">!</span>
        <h2>Horse location unavailable</h2>
        <p>{horsesError ? 'Your horse list could not be verified. Retry loading it or clear this filter.' : selectedHorse ? horseLocation?.reason || 'Add both valid coordinates to the horse’s custom location or saved stable location.' : 'This horse is no longer part of your profile. Choose a current horse or clear the filter.'}</p>
        <div className={styles.stateActions}>{selectedHorse && <Link to="/profile?section=horses">Edit Horse Info</Link>}<button type="button" onClick={() => updateParams({ horse_id: null, page: '1' })}>Clear horse filter</button></div>
      </div>
      : !current ? <div className={view === 'grid' ? styles.grid : styles.list} role="status" aria-label="Loading providers">
        {Array.from({ length: view === 'grid' ? 3 : 4 }, (_, n) => <div key={n} className={styles.skeleton} aria-hidden="true"><div /><span /><span /><span /></div>)}
      </div> : current.status === 'error' ? <div className={styles.statePanel} role="alert">
        <span className={styles.stateIcon} aria-hidden="true">!</span><h2>We couldn't load providers right now.</h2>
        <p>{current.message} Your filters are saved — try again in a moment.</p>
        <button type="button" onClick={() => { setResult(null); setRetry(n => n + 1); }}>Try Again</button>
      </div> : !ready?.data.length ? <div className={styles.statePanel}>
        <span className={styles.stateIcon} aria-hidden="true">⌕</span><h2>{savedOnly ? 'No saved providers match.' : 'No providers match your current filters.'}</h2>
        <p>{savedOnly ? 'Save a provider from the directory to revisit it here, or clear your filters.' : 'Try removing a filter or widening the region.'}</p>
        <div className={styles.stateActions}>{savedOnly && <button type="button" onClick={() => updateParams({ saved: null, page: '1' })}>Browse all providers</button>}<button type="button" onClick={clearFilters}>Clear Filters</button><button type="button" onClick={modify}>Modify Search</button></div>
      </div> : <>
        <div className={view === 'grid' ? styles.grid : styles.list}>{ready.data.map(provider => <ProviderCard key={provider.id} provider={provider} query={query} coordinates={horseId ? null : coordinates} distanceContext={horseId ? `from ${selectedHorse?.name}` : undefined} onSavedChange={saved => {
          if (savedOnly && !saved) { setResult(null); setRetry(n => n + 1); }
          else setResult(previous => previous?.status === 'ready' && previous.data
            ? { ...previous, data: { ...previous.data, data: previous.data.data.map(item => item.id === provider.id ? { ...item, is_saved: saved } : item) } }
            : previous);
        }} />)}</div>
        <Pagination page={page} pageSize={pageSize} total={ready.meta.total} onPageChange={next => updateParams({ page: String(next) })} onPageSizeChange={size => updateParams({ page_size: String(size), page: '1' })} />
      </>}
    </section>
  </main>;
}