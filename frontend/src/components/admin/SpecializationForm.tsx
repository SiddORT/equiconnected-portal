/**
 * SpecializationForm — shared create / edit form rendered inside a modal.
 *
 * Props:
 *   initialValues  — pre-populate fields when editing (undefined = create mode)
 *   onSuccess(spec) — called with the saved specialization on success
 *   onCancel()      — called when the user dismisses the form
 */
import { useEffect, useId, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { extractErrorMessage } from '@/api/client';
import { createSpecialization, updateSpecialization } from '@/api/specializations';
import type { Specialization } from '@/types';
import styles from './SpecializationForm.module.css';

interface FormValues {
  name: string;
  description: string;
  is_active: boolean;
}

interface SpecializationFormProps {
  initialValues?: Pick<Specialization, 'id' | 'name' | 'description' | 'is_active'>;
  onSuccess: (spec: Specialization) => void;
  onCancel: () => void;
}

export function SpecializationForm({ initialValues, onSuccess, onCancel }: SpecializationFormProps) {
  const isEdit = Boolean(initialValues);
  const titleId = useId();
  const firstInputRef = useRef<HTMLInputElement>(null);

  const [values, setValues] = useState<FormValues>({
    name: initialValues?.name ?? '',
    description: initialValues?.description ?? '',
    is_active: initialValues?.is_active ?? true,
  });
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof FormValues, string>>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Focus the name field when the modal opens
  useEffect(() => {
    firstInputRef.current?.focus();
  }, []);

  // Close on Escape
  useEffect(() => {
    const handle = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, [onCancel]);

  function validate(): boolean {
    const errors: Partial<Record<keyof FormValues, string>> = {};
    if (!values.name.trim()) errors.name = 'Name is required.';
    else if (values.name.trim().length > 200) errors.name = 'Name must be 200 characters or fewer.';
    if (values.description.length > 2000) errors.description = 'Description must be 2000 characters or fewer.';
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setApiError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      let saved: Specialization;
      if (isEdit && initialValues) {
        saved = await updateSpecialization(initialValues.id, {
          name: values.name.trim(),
          description: values.description.trim() || null,
        });
      } else {
        saved = await createSpecialization({
          name: values.name.trim(),
          description: values.description.trim() || null,
          is_active: values.is_active,
        });
      }
      onSuccess(saved);
    } catch (err) {
      setApiError(extractErrorMessage(err, 'Failed to save specialization. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    /* Backdrop */
    <div className={styles.backdrop} role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className={styles.panel}>
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {isEdit ? 'Edit Specialization' : 'Add Specialization'}
          </h2>
          <button
            type="button"
            className={styles.closeBtn}
            aria-label="Close"
            onClick={onCancel}
          >
            ✕
          </button>
        </header>

        <form onSubmit={handleSubmit} noValidate>
          <div className={styles.body}>
            {apiError && (
              <div className={styles.apiError} role="alert">
                {apiError}
              </div>
            )}

            <Input
              ref={firstInputRef}
              label="Name"
              placeholder="e.g. Cardiology"
              value={values.name}
              onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))}
              error={fieldErrors.name}
              required
              maxLength={200}
            />

            <div className={styles.fieldGroup}>
              <label className={styles.label} htmlFor="desc-textarea">
                Description
                <span className={styles.optional}> — optional</span>
              </label>
              <textarea
                id="desc-textarea"
                className={`${styles.textarea} ${fieldErrors.description ? styles['textarea--error'] : ''}`}
                placeholder="Brief description of this specialization…"
                rows={3}
                maxLength={2000}
                value={values.description}
                onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))}
                aria-invalid={!!fieldErrors.description}
              />
              {fieldErrors.description && (
                <p className={styles.fieldError} role="alert">{fieldErrors.description}</p>
              )}
            </div>

            {!isEdit && (
              <label className={styles.checkboxRow}>
                <input
                  type="checkbox"
                  checked={values.is_active}
                  onChange={(e) => setValues((v) => ({ ...v, is_active: e.target.checked }))}
                  className={styles.checkbox}
                />
                <span>Active (available for selection immediately)</span>
              </label>
            )}
          </div>

          <footer className={styles.footer}>
            <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={submitting}>
              {isEdit ? 'Save changes' : 'Add specialization'}
            </Button>
          </footer>
        </form>
      </div>
    </div>
  );
}
