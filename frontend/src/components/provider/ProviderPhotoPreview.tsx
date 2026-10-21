import { useState } from 'react';
import styles from './ProviderPhotoPreview.module.css';

/** A failed stored image stays visibly failed; never substitute a local blob. */
export function ProviderPhotoPreview({ source, alt, className, local = false }: {
  source: string;
  alt: string;
  className?: string;
  local?: boolean;
}) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  if (failedSource === source) return <div className={styles.error} role="group" aria-label={`${alt}: image failed to load`}>
    <p role="alert">Image could not be loaded.</p>
    <p>{local ? 'Try selecting the image again.' : 'Retry the stored image. If it still fails, contact support or remove it and upload it again. Saving will not repair an inaccessible image.'}</p>
    <button type="button" onClick={() => { setAttempt((value) => value + 1); setFailedSource(null); }}>Retry image</button>
  </div>;
  return <img key={`${source}-${attempt}`} src={source} alt={alt} className={className} onError={() => setFailedSource(source)} />;
}
