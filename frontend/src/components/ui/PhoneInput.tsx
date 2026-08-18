/**
 * PhoneInput — flag + dial-code combobox combined with a local-number input,
 * styled as a single cohesive field (matches the Input design tokens).
 */
import React from 'react';
import { findByDialCode, findByIsoCode, DEFAULT_COUNTRY } from '@/utils/countryCodes';
import { CountryCombobox } from './CountryCombobox';
import styles from './PhoneInput.module.css';

export interface PhoneInputProps {
  countryCode: string;            // dial code, e.g. "+1"
  /** ISO 3166-1 alpha-2 code (e.g. "CA"). When provided, used for precise flag
   *  resolution so countries sharing a dial code (CA/US/DO all "+1") show the
   *  correct flag. Backward-compatible: omitting it falls back to findByDialCode. */
  isoCode?: string;
  number: string;                 // local number
  /**
   * Preferred callback — called with both the dial code and ISO code in a single
   * event so consumers can apply them as one atomic state update. Use this when
   * tracking iso_code alongside country_code (e.g. MultiPhoneField).
   */
  onCountryChange?: (dialCode: string, isoCode: string) => void;
  /**
   * Backward-compatible callback — called with just the dial code. Safe to use
   * when ISO tracking is not needed. When onCountryChange is also provided,
   * both are called.
   */
  onCountryCodeChange?: (dialCode: string) => void;
  onNumberChange: (number: string) => void;
  error?: string;
  disabled?: boolean;
  ariaLabel?: string;
}

export function PhoneInput({
  countryCode,
  isoCode,
  number,
  onCountryChange,
  onCountryCodeChange,
  onNumberChange,
  error,
  disabled,
  ariaLabel,
}: PhoneInputProps) {
  const inputId = React.useId();
  const errorId = error ? `${inputId}-error` : undefined;

  // Prefer ISO-code lookup (exact match) over dial-code lookup (first-match).
  const selectedCountry =
    (isoCode ? findByIsoCode(isoCode) : undefined) ??
    findByDialCode(countryCode) ??
    DEFAULT_COUNTRY;

  return (
    <div className={styles.container}>
      <div className={`${styles.wrapper} ${error ? styles['wrapper--error'] : ''}`}>
        <CountryCombobox
          value={selectedCountry}
          onChange={(country) => {
            // Fire atomic callback first (both values in one call), then the
            // legacy dial-code-only callback for any backward-compat callers.
            onCountryChange?.(country.dialCode, country.code);
            onCountryCodeChange?.(country.dialCode);
          }}
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
