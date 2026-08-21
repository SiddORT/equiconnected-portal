/**
 * Input — text input with label, hint, and error support.
 * Fully accessible: label, aria-describedby, aria-invalid.
 */
import React from 'react';
import styles from './Input.module.css';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  leftAdornment?: React.ReactNode;
  rightAdornment?: React.ReactNode;
  containerClassName?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      hint,
      error,
      leftAdornment,
      rightAdornment,
      containerClassName = '',
      id,
      className = '',
      ...rest
    },
    ref
  ) => {
    const generatedId = React.useId();
    const inputId = id ?? generatedId;
    const hintId = hint ? `${inputId}-hint` : undefined;
    const errorId = error ? `${inputId}-error` : undefined;
    const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;

    return (
      <div className={`${styles.container} ${containerClassName}`}>
        {label && (
          <label htmlFor={inputId} className={styles.label}>
            {label}
          </label>
        )}
        <div className={`${styles.inputWrapper} ${error ? styles['inputWrapper--error'] : ''}`}>
          {leftAdornment && (
            <span className={styles.adornment}>{leftAdornment}</span>
          )}
          <input
            ref={ref}
            id={inputId}
            aria-describedby={describedBy}
            aria-invalid={!!error}
            className={`${styles.input} ${leftAdornment ? styles['input--left'] : ''} ${rightAdornment ? styles['input--right'] : ''} ${className}`}
            {...rest}
          />
          {rightAdornment && (
            <span className={`${styles.adornment} ${styles['adornment--right']}`}>
              {rightAdornment}
            </span>
          )}
        </div>
        {hint && !error && (
          <p id={hintId} className={styles.hint}>
            {hint}
          </p>
        )}
        {error && (
          <p id={errorId} className={styles.error} role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = 'Input';
