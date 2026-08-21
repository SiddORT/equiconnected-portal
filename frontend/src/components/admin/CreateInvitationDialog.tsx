import { useEffect, useId, useRef, useState } from 'react';
import axios from 'axios';
import { createInvitation } from '@/api/invitations';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import type { Invitation, ProviderType } from '@/types';
import styles from './CreateInvitationDialog.module.css';

interface Props {
  onSuccess: (invitation: Invitation) => void;
  onCancel: () => void;
  /** Called when the invitation was saved but the email failed to deliver, so the parent can refresh its list. */
  onDeliveryFailure?: () => void;
}

const PROVIDER_TYPES: { value: ProviderType; label: string }[] = [
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'CLINIC', label: 'Clinic' },
  { value: 'DOCTOR', label: 'Doctor' },
];

export function CreateInvitationDialog({ onSuccess, onCancel, onDeliveryFailure }: Props) {
  const titleId = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const [providerType, setProviderType] = useState<ProviderType>('HOSPITAL');
  const [providerName, setProviderName] = useState('');
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerNameError, setProviderNameError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);

  useEffect(() => { emailRef.current?.focus(); }, []);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => { if (event.key === 'Escape' && !submitting) onCancel(); };
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [onCancel, submitting]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const normalizedProviderName = providerName.trim();
    const normalizedEmail = email.trim();
    if (!normalizedProviderName) {
      setProviderNameError('Enter a provider name.');
      return;
    }
    setProviderNameError(null);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      setEmailError('Enter a valid recipient email address.');
      return;
    }
    setEmailError(null);
    setSubmitting(true);
    try {
      const invitation = await createInvitation({
        recipient_email: normalizedEmail,
        provider_type: providerType,
        provider_name: normalizedProviderName,
      });
      onSuccess(invitation);
    } catch (err) {
      const code = axios.isAxiosError(err) ? err.response?.data?.detail?.code : undefined;
      if (code === 'email_delivery_failed') {
        setError('The invitation was saved, but the email could not be delivered. Close this dialog and use Resend from the invitation row to try delivery again.');
        onDeliveryFailure?.();
      } else if (code === 'recipient_email_in_use') {
        setEmailError(extractErrorMessage(err, 'This email address is already in use.'));
        emailRef.current?.focus();
      } else {
        setError(extractErrorMessage(err, 'The invitation could not be sent. Please try again.'));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.backdrop} role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className={styles.panel}>
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>New invitation</h2>
          <button type="button" className={styles.closeBtn} onClick={onCancel} disabled={submitting} aria-label="Close">✕</button>
        </header>
        <form onSubmit={submit} noValidate>
          <div className={styles.body}>
            {error && <Alert variant="error">{error}</Alert>}
            <Select
              label="Provider type"
              value={providerType}
              onChange={(event) => setProviderType(event.target.value as ProviderType)}
              options={PROVIDER_TYPES}
              required
            />
            <Input
              label="Provider name"
              value={providerName}
              onChange={(event) => { setProviderName(event.target.value); setProviderNameError(null); }}
              error={providerNameError ?? undefined}
              placeholder="Enter provider name"
              required
            />
            <Input
              ref={emailRef}
              type="email"
              label="Recipient email"
              value={email}
              onChange={(event) => { setEmail(event.target.value); setEmailError(null); }}
              error={emailError ?? undefined}
              placeholder="name@example.com"
              required
            />
          </div>
          <footer className={styles.footer}>
            <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>Cancel</Button>
            <Button type="submit" variant="primary" loading={submitting}>Send invitation</Button>
          </footer>
        </form>
      </div>
    </div>
  );
}