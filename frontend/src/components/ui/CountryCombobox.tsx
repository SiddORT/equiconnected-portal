/**
 * CountryCombobox — a searchable, keyboard-navigable country-code picker.
 * Replaces the native <select> in PhoneInput with a custom combobox popover.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { COUNTRY_CODES, CountryCode } from '@/utils/countryCodes';
import styles from './CountryCombobox.module.css';

const COMMON_CODES = new Set(['US', 'GB', 'CA', 'AU', 'IN', 'PK', 'DE', 'FR', 'ES', 'IT', 'AE', 'SA']);

interface CountryComboboxProps {
  value: CountryCode;
  onChange: (country: CountryCode) => void;
  disabled?: boolean;
}

export function CountryCombobox({ value, onChange, disabled }: CountryComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Track touch start position so we can distinguish a tap from a scroll drag.
  // touchstart fires once per gesture; touchend fires after scrolling too, so
  // we only treat touchend as a selection when the finger barely moved (< 10 px).
  const touchStartPos = useRef<{ x: number; y: number } | null>(null);

  // Derive filtered list
  const filteredCountries = React.useMemo<CountryCode[]>(() => {
    const term = search.trim().toLowerCase();
    if (!term) return COUNTRY_CODES;
    return COUNTRY_CODES.filter(
      (c) => c.name.toLowerCase().includes(term) || c.dialCode.includes(term),
    );
  }, [search]);

  // Whether we show the divider between common and rest (only when not searching)
  const showDivider = search.trim() === '';

  // Reset activeIndex when filtered list changes
  useEffect(() => {
    setActiveIndex(0);
  }, [filteredCountries]);

  // Auto-focus search when opened — skip on touch devices to avoid the
  // on-screen keyboard covering the just-opened panel before it has settled.
  useEffect(() => {
    if (open) {
      const isTouchDevice = window.matchMedia('(pointer: coarse)').matches;
      if (!isTouchDevice) {
        setTimeout(() => searchRef.current?.focus(), 0);
      }
    } else {
      setSearch('');
    }
  }, [open]);

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return;
    const item = listRef.current.children[activeIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  // Click-outside / tap-outside → close
  useEffect(() => {
    if (!open) return;
    function handleOutside(e: MouseEvent | TouchEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleOutside);
    // touchstart fires before mousedown; using capture so it wins
    document.addEventListener('touchstart', handleOutside, { capture: true, passive: true });
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('touchstart', handleOutside, { capture: true });
    };
  }, [open]);

  const handleTriggerClick = useCallback(() => {
    if (!disabled) setOpen((o) => !o);
  }, [disabled]);

  const handleSelect = useCallback(
    (country: CountryCode) => {
      onChange(country);
      setOpen(false);
    },
    [onChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!open) {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
          e.preventDefault();
          setOpen(true);
        }
        return;
      }

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setActiveIndex((i) => Math.min(i + 1, filteredCountries.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setActiveIndex((i) => Math.max(i - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (filteredCountries[activeIndex]) {
            handleSelect(filteredCountries[activeIndex]);
          }
          break;
        case 'Escape':
          e.preventDefault();
          setOpen(false);
          break;
      }
    },
    [open, activeIndex, filteredCountries, handleSelect],
  );

  return (
    <div ref={rootRef} className={styles.root} onKeyDown={handleKeyDown}>
      {/* Trigger */}
      <button
        type="button"
        className={styles.trigger}
        onClick={handleTriggerClick}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Country code: ${value.name} ${value.dialCode}`}
        tabIndex={0}
      >
        <span className={styles.flag}>{value.flag}</span>
        <span className={styles.dialCode}>{value.dialCode}</span>
        <span className={styles.caret} aria-hidden="true">▾</span>
      </button>

      {/* Popover panel */}
      {open && (
        <div className={styles.panel} role="dialog" aria-label="Select country code">
          <div className={styles.searchWrapper}>
            <input
              ref={searchRef}
              type="text"
              className={styles.searchInput}
              placeholder="Search country or code…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search countries"
              autoComplete="off"
            />
          </div>

          <ul
            ref={listRef}
            className={styles.list}
            role="listbox"
            aria-label="Countries"
          >
            {filteredCountries.length === 0 && (
              <li className={styles.noResults}>No countries found</li>
            )}
            {filteredCountries.map((country, idx) => {
              const isCommon = COMMON_CODES.has(country.code);
              const prevIsCommon = idx > 0 ? COMMON_CODES.has(filteredCountries[idx - 1].code) : true;
              const showSeparator = showDivider && idx > 0 && !isCommon && prevIsCommon;

              return (
                <React.Fragment key={country.code}>
                  {showSeparator && <li className={styles.separator} role="separator" aria-hidden="true" />}
                  <li
                    role="option"
                    aria-selected={country.code === value.code}
                    className={`${styles.option} ${idx === activeIndex ? styles.optionActive : ''} ${country.code === value.code ? styles.optionSelected : ''}`}
                    onMouseDown={(e) => {
                      e.preventDefault(); // prevent blur of search input
                      handleSelect(country);
                    }}
                    onTouchStart={(e) => {
                      const t = e.touches[0];
                      touchStartPos.current = { x: t.clientX, y: t.clientY };
                    }}
                    onTouchEnd={(e) => {
                      if (touchStartPos.current) {
                        const t = e.changedTouches[0];
                        const dx = t.clientX - touchStartPos.current.x;
                        const dy = t.clientY - touchStartPos.current.y;
                        const moved = Math.sqrt(dx * dx + dy * dy);
                        touchStartPos.current = null;
                        // Only treat as a tap when finger moved < 10 px
                        if (moved < 10) {
                          e.preventDefault(); // prevent ghost mouse click
                          handleSelect(country);
                        }
                      }
                    }}
                    onMouseEnter={() => setActiveIndex(idx)}
                  >
                    <span className={styles.optionFlag}>{country.flag}</span>
                    <span className={styles.optionName}>{country.name}</span>
                    <span className={styles.optionDial}>{country.dialCode}</span>
                  </li>
                </React.Fragment>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
