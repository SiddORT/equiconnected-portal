/**
 * PhoneInput — flag + dial-code select combined with a local-number input,
 * styled as a single cohesive field (matches the Input design tokens).
 */
import React from 'react';
import { COUNTRY_CODES } from '@/utils/countryCodes';
import styles from './PhoneInput.module.css';

export interface PhoneInputProps {
  countryCode: string;            // dial code, e.g. "+1"
  number: string;                 // local number
  onCountryCodeChange: (dialCode: string) => void;
  onNumberChange: (number: string) => void;
  error?: string;
  disabled?: boolean;
  ariaLabel?: string;
}

export function PhoneInput({
  countryCode,
  number,
  onCountryCodeChange,
  onNumberChange,
  error,
  disabled,
  ariaLabel,
}: PhoneInputProps) {
  const inputId = React.useId();
  const errorId = error ? `${inputId}-error` : undefined;

  return (
    <div className={styles.container}>
      <div className={`${styles.wrapper} ${error ? styles['wrapper--error'] : ''}`}>
        <select
          className={styles.codeSelect}
          value={countryCode}
          onChange={(e) => onCountryCodeChange(e.target.value)}
          disabled={disabled}
          aria-label="Country code"
        >
          {COUNTRY_CODES.map((c) => (
            <option key={c.code} value={c.dialCode}>
              {c.flag} {c.dialCode} — {c.name}
            </option>
          ))}
        </select>
        <span className={styles.divider} aria-hidden="true" />
        <input
          id={inputId}
          type="tel"
          className={styles.numberInput}
          placeholder="555 000 0000"
          value={number}
          onChange={(e) => onNumberChange(e.target.value)}
          disabled={disabled}
          maxLength={50}
          aria-label={ariaLabel ?? 'Phone number'}
          aria-invalid={!!error}
          aria-describedby={errorId}
        />
      </div>
      {error && (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
