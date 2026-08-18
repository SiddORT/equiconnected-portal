/**
 * FormField — generic labelled field wrapper for controls that don't carry
 * their own label (textareas, custom widgets, checkbox groups).
 */
import React from 'react';
import styles from './FormField.module.css';

interface FormFieldProps {
  label: string;
  htmlFor?: string;
  required?: boolean;
  optional?: boolean;
  hint?: string;
  error?: string;
  children: React.ReactNode;
  className?: string;
}

export function FormField({
  label,
  htmlFor,
  required = false,
  optional = false,
  hint,
  error,
  children,
  className = '',
}: FormFieldProps) {
  return (
    <div className={`${styles.field} ${className}`}>
      <label className={styles.label} htmlFor={htmlFor}>
        {label}
        {required && <span className={styles.required} aria-hidden="true"> *</span>}
        {optional && <span className={styles.optional}> — optional</span>}
      </label>
      {children}
      {hint && !error && <p className={styles.hint}>{hint}</p>}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
