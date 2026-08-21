/**
 * Provider locations map — keyless OpenStreetMap tiles via Leaflet.
 * Renders type-distinct circle markers with popups; handles empty state.
 */
import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { LocationMarker, ProviderType } from '@/types';
import { EmptyState } from '@/components/ui/EmptyState';
import styles from './DashboardMap.module.css';

const TYPE_COLORS: Record<LocationMarker['provider_type'], string> = {
  HOSPITAL: '#dc2626',
  CLINIC: '#2563eb',
  DOCTOR: '#059669',
};

const TYPE_LABELS: Record<LocationMarker['provider_type'], string> = {
  HOSPITAL: 'Hospital',
  CLINIC: 'Clinic',
  DOCTOR: 'Doctor',
};

const PROVIDER_TYPES = Object.keys(TYPE_LABELS) as ProviderType[];

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

interface DashboardMapProps {
  markers: LocationMarker[];
}

export function DashboardMap({ markers }: DashboardMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [selectedTypes, setSelectedTypes] = useState<Record<ProviderType, boolean>>({
    HOSPITAL: true,
    CLINIC: true,
    DOCTOR: true,
  });

  const plottable = markers.filter(
    (m) => m.latitude != null && m.longitude != null
  );
  const visiblePlottable = plottable.filter((m) => selectedTypes[m.provider_type]);
  const plottableKey = JSON.stringify(
    plottable.map((m) => [
      m.location_id,
      m.provider_type,
      m.latitude,
      m.longitude,
      m.provider_name,
      m.location_name,
      m.address,
      m.is_primary,
    ])
  );
  const selectedTypesKey = PROVIDER_TYPES.filter((type) => selectedTypes[type]).join(',');

  useEffect(() => {
    if (!containerRef.current || plottable.length === 0) return;

    const map = L.map(containerRef.current, { scrollWheelZoom: false });

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const bounds = L.latLngBounds([]);
    for (const m of visiblePlottable) {
      const latLng: L.LatLngExpression = [m.latitude, m.longitude];
      bounds.extend(latLng);
      const marker = L.circleMarker(latLng, {
        radius: 9,
        color: '#ffffff',
        weight: 2,
        fillColor: TYPE_COLORS[m.provider_type],
        fillOpacity: 0.9,
      }).addTo(map);
      marker.bindPopup(
        `<strong>${escapeHtml(m.provider_name)}</strong><br/>` +
          `${TYPE_LABELS[m.provider_type]}${m.location_name ? ' — ' + escapeHtml(m.location_name) : ''}<br/>` +
          `${escapeHtml(m.address)}${m.is_primary ? '<br/><em>Primary location</em>' : ''}`
      );
    }

    if (visiblePlottable.length === 1) {
      map.setView(bounds.getCenter(), 12);
    } else if (visiblePlottable.length > 1) {
      map.fitBounds(bounds, { padding: [32, 32] });
    } else if (plottable.length === 1) {
      map.setView([plottable[0].latitude, plottable[0].longitude], 12);
    } else {
      const allBounds = L.latLngBounds([]);
      for (const m of plottable) {
        allBounds.extend([m.latitude, m.longitude]);
      }
      map.fitBounds(allBounds, { padding: [32, 32] });
    }

    return () => {
      map.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plottableKey, selectedTypesKey]);

  if (plottable.length === 0) {
    return (
      <EmptyState
        icon="🗺"
        title="No mappable locations"
        description="Provider locations with coordinates will appear on the map here."
      />
    );
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.mapArea}>
        <div
          ref={containerRef}
          className={styles.map}
          role="region"
          aria-label="Map of provider locations"
        />
        {visiblePlottable.length === 0 && (
          <div className={styles.emptyOverlay}>
            <EmptyState
              icon="🗺"
              title="No visible locations"
              description="Select a provider type to show its locations on the map."
            />
          </div>
        )}
      </div>
      <div className={styles.legend} role="group" aria-label="Filter provider locations by type">
        {PROVIDER_TYPES.map((type) => {
          const isSelected = selectedTypes[type];
          return (
            <button
              key={type}
              type="button"
              className={`${styles.legendItem} ${isSelected ? styles.legendItemSelected : ''}`}
              onClick={() => setSelectedTypes((current) => ({
                ...current,
                [type]: !current[type],
              }))}
              aria-pressed={isSelected}
              aria-label={`${isSelected ? 'Hide' : 'Show'} ${TYPE_LABELS[type]} locations`}
            >
              <span
                className={styles.legendDot}
                style={{ backgroundColor: TYPE_COLORS[type] }}
                aria-hidden="true"
              />
              {TYPE_LABELS[type]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
