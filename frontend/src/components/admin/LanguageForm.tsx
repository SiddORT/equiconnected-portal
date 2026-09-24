import { useEffect, useId, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { extractErrorMessage } from '@/api/client';
import { createLanguage, updateLanguage } from '@/api/languages';
import type { Language } from '@/types';
import styles from './LanguageForm.module.css';

interface Props {
  initialValues?: Language;
  onSuccess: (language: Language) => void;
  onCancel: () => void;
}

export function LanguageForm({ initialValues, onSuccess, onCancel }: Props) {
  const edit = Boolean(initialValues);
  const titleId = useId();
  const ref = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(initialValues?.name ?? '');
  const [code, setCode] = useState(initialValues?.code ?? '');
  const [errors, setErrors] = useState<{ name?: string; code?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { ref.current?.focus(); }, []);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onCancel]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!name.trim()) next.name = 'Name is required.';
    if (!code.trim()) next.code = 'Code is required.';
    else if (!/^[A-Za-z]{2,10}(-[A-Za-z]{2,10})?$/.test(code.trim())) next.code = 'Use a valid language code (for example, en or pt-BR).';
    setErrors(next);
    if (Object.keys(next).length) return;
    setSaving(true); setApiError(null);
    try {
      const saved = edit && initialValues
        ? await updateLanguage(initialValues.id, { name: name.trim(), code: code.trim() })
        : await createLanguage({ name: name.trim(), code: code.trim() });
      onSuccess(saved);
    } catch (error) {
      setApiError(extractErrorMessage(error, 'Failed to save language. Please try again.'));
    } finally { setSaving(false); }
  }

  return (
    <div className={styles.backdrop} role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className={styles.panel}>
        <header className={styles.header}><h2 id={titleId}>{edit ? 'Edit Language' : 'Add Language'}</h2><button type="button" className={styles.close} onClick={onCancel} aria-label="Close">✕</button></header>
        <form onSubmit={submit} noValidate>
          <div className={styles.body}>
            {apiError && <div className={styles.error} role="alert">{apiError}</div>}
            <Input ref={ref} label="Language name" value={name} onChange={(e) => setName(e.target.value)} error={errors.name} maxLength={200} required placeholder="e.g. English" />
            <Input label="Language code" value={code} onChange={(e) => setCode(e.target.value)} error={errors.code} maxLength={21} required placeholder="e.g. en or pt-BR" />
          </div>
          <footer className={styles.footer}><Button type="button" variant="ghost" onClick={onCancel} disabled={saving}>Cancel</Button><Button type="submit" variant="primary" loading={saving}>{edit ? 'Save changes' : 'Add language'}</Button></footer>
        </form>
      </div>
    </div>
  );
}