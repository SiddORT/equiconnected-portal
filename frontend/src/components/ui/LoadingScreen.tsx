import styles from './LoadingScreen.module.css';
import { LoadingSpinner } from './LoadingSpinner';

interface LoadingScreenProps {
  message?: string;
}

export function LoadingScreen({ message = 'Loading…' }: LoadingScreenProps) {
  return (
    <div className={styles.screen} role="status" aria-live="polite">
      <LoadingSpinner size="lg" />
      <p className={styles.message}>{message}</p>
    </div>
  );
}
