/**
 * PhoneInput — flag + dial-code combobox combined with a local-number input,
 * styled as a single cohesive field (matches the Input design tokens).
 */
import React from 'react';
import { findByDialCode, DEFAULT_COUNTRY } from '@/utils/countryCodes';
import { CountryCombobox } from './CountryCombobox';
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

  // Resolve the full CountryCode object from the stored dial code string.
  const selectedCountry = findByDialCode(countryCode) ?? DEFAULT_COUNTRY;

  return (
    <div className={styles.container}>
      <div className={`${styles.wrapper} ${error ? styles['wrapper--error'] : ''}`}>
        <CountryCombobox
          value={selectedCountry}
          onChange={(country) => onCountryCodeChange(country.dialCode)}
          disabled={disabled}
        />
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
