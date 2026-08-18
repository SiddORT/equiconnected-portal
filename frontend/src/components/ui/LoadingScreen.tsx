import styles from './LoadingScreen.module.css';
import { HorseLoader } from './HorseLoader';

interface LoadingScreenProps {
  message?: string;
}

export function LoadingScreen({ message = 'Loading…' }: LoadingScreenProps) {
  return (
    <div className={styles.screen} role="status" aria-live="polite">
      <HorseLoader size={96} label={message} />
      <p className={styles.message}>{message}</p>
    </div>
  );
}
