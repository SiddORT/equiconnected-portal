/**
 * ConfirmDialog — in-app confirmation modal rendered into a portal.
 * Matches the equestrian design system.
 */
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Button } from './Button';
import styles from './ConfirmDialog.module.css';

interface Props {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = false,
  onConfirm,
  onCancel,
}: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) setTimeout(() => cancelRef.current?.focus(), 10);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  return createPortal(
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className={styles.dialog}>
        <div className={styles.icon}>{danger ? '🗑' : '⚠️'}</div>
        <h2 className={styles.title} id="confirm-title">{title}</h2>
        {message && <p className={styles.message}>{message}</p>}
        <div className={styles.divider} />
        <div className={styles.actions}>
          <Button ref={cancelRef} type="button" variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button type="button" variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
