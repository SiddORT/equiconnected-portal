/**
 * Provider locations map — keyless OpenStreetMap tiles via Leaflet.
 * Renders type-distinct circle markers with popups; handles empty state.
 */
import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { LocationMarker } from '@/types';
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
  const mapRef = useRef<L.Map | null>(null);

  const plottable = markers.filter(
    (m) => m.latitude != null && m.longitude != null
  );

  useEffect(() => {
    if (!containerRef.current || plottable.length === 0) return;

    const map = L.map(containerRef.current, { scrollWheelZoom: false });
    mapRef.current = map;

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const bounds = L.latLngBounds([]);
    for (const m of plottable) {
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

    if (plottable.length === 1) {
      map.setView(bounds.getCenter(), 12);
    } else {
      map.fitBounds(bounds, { padding: [32, 32] });
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(plottable.map((m) => m.location_id))]);

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
      <div
        ref={containerRef}
        className={styles.map}
        role="region"
        aria-label="Map of provider locations"
      />
      <div className={styles.legend} aria-label="Map legend">
        {(Object.keys(TYPE_LABELS) as LocationMarker['provider_type'][]).map((t) => (
          <span key={t} className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: TYPE_COLORS[t] }} />
            {TYPE_LABELS[t]}s
          </span>
        ))}
      </div>
    </div>
  );
}
