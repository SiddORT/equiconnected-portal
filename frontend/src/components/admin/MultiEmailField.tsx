/**
 * MultiEmailField — dynamic list of email entries with add/remove buttons
 * and an optional "Primary" radio per row.
 */
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from './MultiContactField.module.css';

export interface EmailEntry {
  /** Set for entries persisted on the server (edit mode). */
  id?: string;
  email: string;
  is_primary: boolean;
}

export function emptyEmailEntry(isPrimary = false): EmailEntry {
  return { email: '', is_primary: isPrimary };
}

interface MultiEmailFieldProps {
  entries: EmailEntry[];
  onChange: (entries: EmailEntry[]) => void;
  errors?: Record<number, string>;
  disabled?: boolean;
}

export function MultiEmailField({ entries, onChange, errors, disabled }: MultiEmailFieldProps) {
  function updateEntry(index: number, patch: Partial<EmailEntry>) {
    onChange(entries.map((e, i) => (i === index ? { ...e, ...patch } : e)));
  }

  function setPrimary(index: number) {
    onChange(entries.map((e, i) => ({ ...e, is_primary: i === index })));
  }

  function removeEntry(index: number) {
    const removed = entries[index];
    const next = entries.filter((_, i) => i !== index);
    if (removed.is_primary && next.length > 0) next[0] = { ...next[0], is_primary: true };
    onChange(next);
  }

  return (
    <div className={styles.field}>
      <span className={styles.fieldLabel}>Email addresses</span>
      {entries.length === 0 && <p className={styles.emptyHint}>No email addresses added.</p>}
      {entries.map((entry, i) => (
        <div key={entry.id ?? `new-${i}`} className={styles.row}>
          <Input
            type="email"
            placeholder="contact@example.com"
            value={entry.email}
            onChange={(e) => updateEntry(i, { email: e.target.value })}
            error={errors?.[i]}
            disabled={disabled}
            maxLength={254}
            aria-label={`Email address ${i + 1}`}
            containerClassName={styles.grow}
          />
          <label className={styles.primaryRadio} title="Set as primary email">
            <input
              type="radio"
              name="primary-email"
              checked={entry.is_primary}
              onChange={() => setPrimary(i)}
              disabled={disabled}
            />
            <span>Primary</span>
          </label>
          <button
            type="button"
            className={styles.removeBtn}
            aria-label={`Remove email ${i + 1}`}
            onClick={() => removeEntry(i)}
            disabled={disabled}
          >
            ✕
          </button>
        </div>
      ))}
      <div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => onChange([...entries, emptyEmailEntry(entries.length === 0)])}
        >
          ＋ Add email
        </Button>
      </div>
    </div>
  );
}
