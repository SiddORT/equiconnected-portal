import styles from './BrandLogo.module.css';

interface BrandLogoProps {
  className?: string;
  showTagline?: boolean;
}

export function BrandLogo({ className = '', showTagline = true }: BrandLogoProps) {
  return (
    <div className={`${styles.lockup} ${className}`.trim()}>
      <span className={styles.mark}>
        <img src="/logo.png" alt="" aria-hidden="true" />
      </span>
      <span className={styles.copy}>
        <span className={styles.name}>EquiConnected</span>
        {showTagline && (
          <span className={styles.tagline}>Connecting horses with the right care</span>
        )}
      </span>
    </div>
  );
}