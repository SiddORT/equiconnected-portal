import { useEffect, useRef, useState } from 'react';
import styles from './SignupMultiSelect.module.css';

interface Option {
  id: string;
  name: string;
  code?: string;
}

interface Props {
  label: string;
  options: Option[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
  required?: boolean;
  error?: string;
  loading?: boolean;
}

export function SignupMultiSelect({
  label, options, selectedIds, onChange, disabled, required, error, loading,
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    searchInput.current?.focus();
    const onPointerDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  const filtered = options.filter((item) =>
    `${item.name} ${item.code ?? ''}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())
  );
  const selected = selectedIds.map((id) => options.find((item) => item.id === id)).filter((item): item is Option => Boolean(item));
  const id = label.toLowerCase().replace(/\W+/g, '-');

  function toggle(optionId: string) {
    onChange(selectedIds.includes(optionId)
      ? selectedIds.filter((id) => id !== optionId)
      : [...selectedIds, optionId]);
  }

  return (
    <div className={styles.field} ref={root}>
      <span className={styles.label} id={`${id}-label`}>{label}{required ? ' *' : ''}</span>
      <button
        className={styles.trigger}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-labelledby={`${id}-label`}
        aria-controls={`${id}-list`}
        disabled={disabled || loading || options.length === 0}
        onClick={() => { setOpen((value) => !value); setSearch(''); }}
      >
        <span>{loading ? 'Loading…' : selected.length ? `${selected.length} selected` : `Select ${label.toLowerCase()}`}</span>
        <span aria-hidden="true">⌄</span>
      </button>
      {selected.length > 0 && (
        <div className={styles.selected} aria-label={`Selected ${label.toLowerCase()}`}>
          {selected.map((item) => (
            <button
              className={styles.chip}
              key={item.id}
              type="button"
              disabled={disabled}
              onClick={() => toggle(item.id)}
              aria-label={`Remove ${item.name}`}
            >
              {item.name}{item.code ? ` (${item.code})` : ''} <span aria-hidden="true">×</span>
            </button>
          ))}
        </div>
      )}
      {open && (
        <div className={styles.dropdown} id={`${id}-list`}>
          <input
            ref={searchInput}
            className={styles.search}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Escape') setOpen(false); }}
            placeholder={`Search ${label.toLowerCase()}…`}
            aria-label={`Search ${label.toLowerCase()}`}
          />
          <div className={styles.options} role="listbox" aria-label={label} aria-multiselectable="true">
            {filtered.map((item) => (
              <button
                key={item.id}
                className={styles.option}
                type="button"
                role="option"
                aria-selected={selectedIds.includes(item.id)}
                onClick={() => toggle(item.id)}
              >
                <span>{item.name}{item.code ? ` (${item.code})` : ''}</span>
                <span aria-hidden="true">{selectedIds.includes(item.id) ? '✓' : ''}</span>
              </button>
            ))}
            {!filtered.length && <p className={styles.empty}>No matching options</p>}
          </div>
        </div>
      )}
      {error && <p className={styles.error} role="alert">{error}</p>}
    </div>
  );
}