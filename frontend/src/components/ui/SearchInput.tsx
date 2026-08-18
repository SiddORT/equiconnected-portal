/**
 * SearchInput — debounced text input reusable across admin pages.
 *
 * The parent owns the *debounced* value; this component owns the raw input
 * text and calls `onChange` after `delay` ms of inactivity.
 */
import { useEffect, useRef, useState } from 'react';
import { Input } from './Input';

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  delay?: number;
  containerClassName?: string;
  'aria-label'?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  delay = 350,
  containerClassName,
  'aria-label': ariaLabel,
}: SearchInputProps) {
  const [text, setText] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  // Keep local text in sync if the parent resets the value externally.
  useEffect(() => {
    setText(value);
  }, [value]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.value;
    setText(next);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onChangeRef.current(next), delay);
  }

  return (
    <Input
      type="search"
      placeholder={placeholder}
      value={text}
      onChange={handleChange}
      leftAdornment={<span aria-hidden="true">🔍</span>}
      containerClassName={containerClassName}
      aria-label={ariaLabel ?? placeholder}
    />
  );
}
