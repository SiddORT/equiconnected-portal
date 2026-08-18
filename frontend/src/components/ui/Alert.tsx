import React from 'react';
import styles from './Alert.module.css';

type AlertVariant = 'info' | 'success' | 'warning' | 'error';

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

const icons: Record<AlertVariant, string> = {
  info: '●',
  success: '✓',
  warning: '⚠',
  error: '✕',
};

export function Alert({ variant = 'info', title, children, onDismiss, className = '' }: AlertProps) {
  return (
    <div
      role="alert"
      className={[styles.alert, styles[`alert--${variant}`], className].filter(Boolean).join(' ')}
    >
      <span className={styles.icon} aria-hidden="true">{icons[variant]}</span>
      <div className={styles.content}>
        {title && <p className={styles.title}>{title}</p>}
        <div className={styles.body}>{children}</div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          className={styles.dismiss}
        >
          ✕
        </button>
      )}
    </div>
  );
}
