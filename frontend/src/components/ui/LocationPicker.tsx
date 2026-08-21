import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, MouseEvent } from 'react';
import {
  getCityOptions,
  getCountryOptions,
  getStateOptions,
  type GeographicOption,
} from '@/utils/geography';
import styles from './LocationPicker.module.css';

export interface GeographicLocationValue {
  country: string;
  state_province: string;
  city: string;
}

type LocationField = keyof GeographicLocationValue;

interface SearchableComboboxProps {
  id: string;
  label: string;
  value: string;
  options: GeographicOption[];
  placeholder: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  loading?: boolean;
  required?: boolean;
  error?: string;
  emptyMessage: string;
}

function SearchableCombobox({
  id,
  label,
  value,
  options,
  placeholder,
  onChange,
  disabled = false,
  loading = false,
  required = false,
  error,
  emptyMessage,
}: SearchableComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listId = useId();

  const filteredOptions = useMemo(() => {
    const search = query.trim().toLocaleLowerCase();
    if (!search) return options;
    return options.filter((option) => option.label.toLocaleLowerCase().includes(search));
  }, [options, query]);

  const selected = options.find((option) => option.value === value);
  const selectedLabel = selected?.label ?? value;

  useEffect(() => {
    setActiveIndex(0);
  }, [query, options]);

  useEffect(() => {
    if (!open) return;
    const activeOption = listRef.current?.children[activeIndex] as HTMLElement | undefined;
    activeOption?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex, open]);

  useEffect(() => {
    if (!open) {
      setQuery('');
      return;
    }
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  function closeAndRestoreFocus() {
    setOpen(false);
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  }

  function select(option: GeographicOption) {
    onChange(option.value);
    closeAndRestoreFocus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!open) {
      if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (!disabled) setOpen(true);
      }
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, Math.max(filteredOptions.length - 1, 0)));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter' && filteredOptions[activeIndex]) {
      event.preventDefault();
      select(filteredOptions[activeIndex]);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closeAndRestoreFocus();
    } else if (event.key === 'Tab') {
      setOpen(false);
    }
  }

  return (
    <div className={styles.field} ref={rootRef} onKeyDown={onKeyDown}>
      <label id={`${id}-label`} className={styles.label} htmlFor={id}>
        {label}{required && <span aria-hidden="true"> *</span>}
      </label>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        className={`${styles.trigger} ${error ? styles.triggerError : ''}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-labelledby={`${id}-label`}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        disabled={disabled || loading}
        onClick={() => setOpen((isOpen) => !isOpen)}
      >
        <span className={value ? styles.value : styles.placeholder}>
          {loading ? 'Loading locations…' : selectedLabel || placeholder}
        </span>
        <span className={styles.caret} aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div className={styles.panel}>
          <input
            ref={inputRef}
            role="combobox"
            className={styles.search}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${label.toLocaleLowerCase()}…`}
            aria-label={`Search ${label.toLocaleLowerCase()}`}
            aria-autocomplete="list"
            aria-controls={listId}
            aria-expanded
            aria-activedescendant={
              filteredOptions[activeIndex] ? `${listId}-option-${activeIndex}` : undefined
            }
            autoComplete="off"
          />
          <ul id={listId} className={styles.options} role="listbox" aria-label={label}>
            {filteredOptions.length === 0 ? (
              <li className={styles.empty}>{query ? `No ${label.toLocaleLowerCase()} matches found.` : emptyMessage}</li>
            ) : (
              filteredOptions.map((option, index) => (
                <li
                  key={option.value}
                  id={`${listId}-option-${index}`}
                  role="option"
                  aria-selected={option.value === value}
                  className={`${styles.option} ${index === activeIndex ? styles.active : ''} ${option.value === value ? styles.selected : ''}`}
                  onMouseDown={(event: MouseEvent<HTMLLIElement>) => {
                    event.preventDefault();
                    select(option);
                  }}
                  onMouseEnter={() => setActiveIndex(index)}
                >
                  {option.label}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
      {error && <p id={`${id}-error`} className={styles.error} role="alert">{error}</p>}
    </div>
  );
}

export interface LocationPickerProps {
  value: GeographicLocationValue;
  onChange: (nextValue: GeographicLocationValue) => void;
  errors?: Partial<Record<LocationField, string>>;
  disabled?: boolean;
  theme?: 'light' | 'dark';
  required?: boolean;
  idPrefix?: string;
  className?: string;
}

export function LocationPicker({
  value,
  onChange,
  errors = {},
  disabled = false,
  theme = 'light',
  required = false,
  idPrefix = 'location',
  className = '',
}: LocationPickerProps) {
  const countries = useMemo(getCountryOptions, []);
  const states = useMemo(() => getStateOptions(value.country), [value.country]);
  const cities = useMemo(
    () => getCityOptions(value.country, value.state_province),
    [value.country, value.state_province]
  );
  const stateRequired = required && states.length > 0;
  const cityDisabled = disabled || !value.country || (states.length > 0 && !value.state_province);

  return (
    <div className={`${styles.root} ${theme === 'dark' ? styles.dark : ''} ${className}`}>
      <SearchableCombobox
        id={`${idPrefix}-country`}
        label="Country"
        value={value.country}
        options={countries}
        placeholder="Select country"
        onChange={(country) => onChange({ country, state_province: '', city: '' })}
        disabled={disabled}
        required={required}
        error={errors.country}
        emptyMessage="No countries are available."
      />
      <SearchableCombobox
        id={`${idPrefix}-state`}
        label="State / Province"
        value={value.state_province}
        options={states}
        placeholder={!value.country ? 'Select country first' : states.length ? 'Select state / province' : 'Not applicable'}
        onChange={(state_province) => onChange({ ...value, state_province, city: '' })}
        disabled={disabled || !value.country || states.length === 0}
        required={stateRequired}
        error={errors.state_province}
        emptyMessage="No state or province choices are available."
      />
      <SearchableCombobox
        id={`${idPrefix}-city`}
        label="City"
        value={value.city}
        options={cities}
        placeholder={cityDisabled ? 'Select location above first' : 'Select city'}
        onChange={(city) => onChange({ ...value, city })}
        disabled={cityDisabled}
        required={required}
        error={errors.city}
        emptyMessage="No city choices are available."
      />
    </div>
  );
}
