import styles from './LoadingSpinner.module.css';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  label?: string;
}

export function LoadingSpinner({ size = 'md', className = '', label = 'Loading…' }: LoadingSpinnerProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={[styles.spinner, styles[`spinner--${size}`], className].filter(Boolean).join(' ')}
    />
  );
}
