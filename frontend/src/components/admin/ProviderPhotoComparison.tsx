import { useMemo, useState } from 'react';
import type { ProviderPhotoCreate } from '@/types';
import styles from './ProviderPhotoComparison.module.css';

type Photo = Partial<ProviderPhotoCreate> & { id?: string | null };

function normalizePhotos(value: unknown): Photo[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item): Photo[] => {
    if (typeof item === 'string') return [{ storage_reference: item, alt_text: null, caption: null, display_order: 0, is_thumbnail: false }];
    if (!item || typeof item !== 'object') return [];
    const photo = item as Record<string, unknown>;
    if (typeof photo.storage_reference !== 'string') return [];
    return [{
      id: typeof photo.id === 'string' ? photo.id : null,
      storage_reference: photo.storage_reference,
      alt_text: typeof photo.alt_text === 'string' ? photo.alt_text : null,
      caption: typeof photo.caption === 'string' ? photo.caption : null,
      display_order: typeof photo.display_order === 'number' ? photo.display_order : 0,
      is_thumbnail: photo.is_thumbnail === true,
    }];
  }).sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
}

function safeImageSource(reference: string | undefined) {
  if (!reference) return null;
  const value = reference.trim();
  if (!value || /[\u0000-\u001f\\]/.test(value) || value.startsWith('//')) return null;
  if (value.startsWith('/uploads/') && !value.includes('/../')) return value;
  try {
    const parsed = new URL(value);
    if ((parsed.protocol === 'https:' || parsed.protocol === 'http:') && parsed.hostname) return parsed.href;
  } catch {
    return null;
  }
  return null;
}

function metadata(photo: Photo) {
  return `${photo.alt_text ?? ''}\u0000${photo.caption ?? ''}`;
}

function PhotoCard({ photo, status, index }: { photo: Photo; status: string; index: number }) {
  const [failed, setFailed] = useState(false);
  const source = safeImageSource(photo.storage_reference);
  const altText = photo.alt_text?.trim() || `Provider photo ${index + 1}`;
  return <article className={styles.photoCard}>
    <div className={styles.imageFrame}>
      {source && !failed
        ? <img src={source} alt={altText} loading="lazy" onError={() => setFailed(true)} />
        : <div className={styles.imageState} role="img" aria-label={source ? `${altText}: image failed to load` : `${altText}: image unavailable`}>
            <span className={styles.imageMark} aria-hidden="true">Photo</span>
            <span>{source ? 'Image could not be loaded' : 'Image unavailable'}</span>
          </div>}
      {photo.is_thumbnail && <span className={styles.thumbnail}>Profile photo</span>}
    </div>
    <div className={styles.photoDetails}>
      <div className={styles.photoTopline}><span className={styles.order}>Photo {index + 1} · order {photo.display_order ?? 0}</span><span className={styles.status}>{status}</span></div>
      <p className={styles.caption}>{photo.caption?.trim() || 'No caption'}</p>
      <p className={styles.alt}>Alt text: {photo.alt_text?.trim() || 'Not provided'}</p>
    </div>
  </article>;
}

export function ProviderPhotoComparison({ current, proposed }: { current: unknown; proposed: unknown }) {
  const currentPhotos = useMemo(() => normalizePhotos(current), [current]);
  const proposedPhotos = useMemo(() => normalizePhotos(proposed), [proposed]);
  const { currentStatus, proposedStatus } = useMemo(() => {
    const currentCounts = new Map<string, number>();
    const proposedCounts = new Map<string, number>();
    currentPhotos.forEach((photo) => currentCounts.set(photo.storage_reference!, (currentCounts.get(photo.storage_reference!) ?? 0) + 1));
    proposedPhotos.forEach((photo) => proposedCounts.set(photo.storage_reference!, (proposedCounts.get(photo.storage_reference!) ?? 0) + 1));
    const statuses = (photos: Photo[], other: Photo[], otherCounts: Map<string, number>) => {
      const seen = new Map<string, number>();
      return photos.map((photo) => {
        const ref = photo.storage_reference!;
        const position = seen.get(ref) ?? 0;
        seen.set(ref, position + 1);
        if (position >= (otherCounts.get(ref) ?? 0)) return 'Added';
        const counterpart = other.filter((candidate) => candidate.storage_reference === ref)[position];
        const changed: string[] = [];
        if (metadata(photo) !== metadata(counterpart)) changed.push('Metadata changed');
        if (photo.display_order !== counterpart.display_order) changed.push('Order changed');
        if (photo.is_thumbnail !== counterpart.is_thumbnail) changed.push('Profile photo changed');
        return changed.length ? `Changed · ${changed.join(' · ')}` : 'Unchanged';
      });
    };
    return {
      currentStatus: statuses(currentPhotos, proposedPhotos, proposedCounts).map((status) => status === 'Added' ? 'Removed' : status),
      proposedStatus: statuses(proposedPhotos, currentPhotos, currentCounts),
    };
  }, [currentPhotos, proposedPhotos]);

  return <section className={styles.comparison} aria-label="Photo comparison" aria-labelledby="photo-comparison-title">
    <div className={styles.sectionHead}>
      <div><p className={styles.kicker}>Visual review</p><h3 id="photo-comparison-title">Photo comparison</h3></div>
      <p className={styles.legend}>Compared by stored photo identity</p>
    </div>
    <div className={styles.columns}>
      {[{ title: 'Current photos', photos: currentPhotos, statuses: currentStatus }, { title: 'Proposed photos', photos: proposedPhotos, statuses: proposedStatus }].map((column) =>
        <section className={styles.column} key={column.title} aria-label={column.title}>
          <h4>{column.title}<span>{column.photos.length}</span></h4>
          {column.photos.length
            ? <div className={styles.photoGrid}>{column.photos.map((photo, index) => <PhotoCard key={`${photo.storage_reference}-${index}`} photo={photo} status={column.statuses[index]} index={index} />)}</div>
            : <div className={styles.empty}>No photos in this profile.</div>}
        </section>)}
    </div>
  </section>;
}

export default ProviderPhotoComparison;