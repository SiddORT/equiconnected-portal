/**
 * MultiPhoneField — dynamic list of phone entries with country-code picker,
 * add/remove buttons, and an optional "Primary" radio per row.
 */
import { Button } from '@/components/ui/Button';
import { PhoneInput } from '@/components/ui/PhoneInput';
import { DEFAULT_COUNTRY } from '@/utils/countryCodes';
import styles from './MultiContactField.module.css';

export interface PhoneEntry {
  /** Set for entries persisted on the server (edit mode). */
  id?: string;
  country_code: string;
  number: string;
  is_primary: boolean;
}

export function emptyPhoneEntry(isPrimary = false): PhoneEntry {
  return { country_code: DEFAULT_COUNTRY.dialCode, number: '', is_primary: isPrimary };
}

interface MultiPhoneFieldProps {
  entries: PhoneEntry[];
  onChange: (entries: PhoneEntry[]) => void;
  errors?: Record<number, string>;
  disabled?: boolean;
}

export function MultiPhoneField({ entries, onChange, errors, disabled }: MultiPhoneFieldProps) {
  function updateEntry(index: number, patch: Partial<PhoneEntry>) {
    onChange(entries.map((e, i) => (i === index ? { ...e, ...patch } : e)));
  }

  function setPrimary(index: number) {
    onChange(entries.map((e, i) => ({ ...e, is_primary: i === index })));
  }

  function removeEntry(index: number) {
    const removed = entries[index];
    const next = entries.filter((_, i) => i !== index);
    // If the removed row was primary, promote the first remaining row.
    if (removed.is_primary && next.length > 0) next[0] = { ...next[0], is_primary: true };
    onChange(next);
  }

  return (
    <div className={styles.field}>
      <span className={styles.fieldLabel}>Phone numbers</span>
      {entries.length === 0 && <p className={styles.emptyHint}>No phone numbers added.</p>}
      {entries.map((entry, i) => (
        <div key={entry.id ?? `new-${i}`} className={styles.row}>
          <PhoneInput
            countryCode={entry.country_code}
            number={entry.number}
            onCountryCodeChange={(code) => updateEntry(i, { country_code: code })}
            onNumberChange={(num) => updateEntry(i, { number: num })}
            error={errors?.[i]}
            disabled={disabled}
            ariaLabel={`Phone number ${i + 1}`}
          />
          <label className={styles.primaryRadio} title="Set as primary phone">
            <input
              type="radio"
              name="primary-phone"
              checked={entry.is_primary}
              onChange={() => setPrimary(i)}
              disabled={disabled}
            />
            <span>Primary</span>
          </label>
          <button
            type="button"
            className={styles.removeBtn}
            aria-label={`Remove phone ${i + 1}`}
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
          onClick={() => onChange([...entries, emptyPhoneEntry(entries.length === 0)])}
        >
          ＋ Add phone
        </Button>
      </div>
    </div>
  );
}
