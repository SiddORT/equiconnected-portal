import { useEffect, useId, useRef, useState } from 'react';
import axios from 'axios';
import { createInvitation } from '@/api/invitations';
import { extractErrorMessage } from '@/api/client';
import { listProviders } from '@/api/providers';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import type { Invitation, ProviderListItem, ProviderType } from '@/types';
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
  const [email, setEmail] = useState('');
  const [providerSearch, setProviderSearch] = useState('');
  const [providers, setProviders] = useState<ProviderListItem[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<ProviderListItem | null>(null);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);

  useEffect(() => { emailRef.current?.focus(); }, []);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => { if (event.key === 'Escape' && !submitting) onCancel(); };
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [onCancel, submitting]);

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      setLoadingProviders(true);
      try {
        const result = await listProviders({
          provider_type: providerType,
          search: providerSearch.trim() || undefined,
          page: 1,
          page_size: 10,
        });
        setProviders(result.data);
      } catch {
        setProviders([]);
      } finally {
        setLoadingProviders(false);
      }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [providerSearch, providerType]);

  function changeProviderType(value: ProviderType) {
    setProviderType(value);
    setSelectedProvider(null);
    setProviderSearch('');
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const normalizedEmail = email.trim();
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
        provider_id: selectedProvider?.id ?? null,
      });
      onSuccess(invitation);
    } catch (err) {
      const code = axios.isAxiosError(err) ? err.response?.data?.detail?.code : undefined;
      if (code === 'email_delivery_failed') {
        setError('The invitation was saved, but the email could not be delivered. Close this dialog and use Resend from the invitation row to try delivery again.');
        onDeliveryFailure?.();
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
              onChange={(event) => changeProviderType(event.target.value as ProviderType)}
              options={PROVIDER_TYPES}
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
            <div className={styles.providerField}>
              <Input
                role="combobox"
                aria-expanded={!selectedProvider && Boolean(providerSearch || providers.length > 0)}
                aria-autocomplete="list"
                aria-controls={`${titleId}-provider-listbox`}
                label="Existing provider"
                hint="Optional — leave unselected to invite as a new provider."
                value={selectedProvider ? selectedProvider.name : providerSearch}
                onChange={(event) => {
                  setSelectedProvider(null);
                  setProviderSearch(event.target.value);
                }}
                placeholder={`Search ${providerType.toLowerCase()}s…`}
              />
              {!selectedProvider && (providerSearch || providers.length > 0) && (
                <div className={styles.providerOptions} id={`${titleId}-provider-listbox`} role="listbox" aria-label="Matching providers">
                  {loadingProviders ? <span className={styles.optionHint}>Searching…</span> : providers.length === 0
                    ? <span className={styles.optionHint}>No matching providers</span>
                    : providers.map((provider) => (
                      <button key={provider.id} type="button" role="option" className={styles.providerOption} onClick={() => {
                        setSelectedProvider(provider);
                        setProviderSearch('');
                      }}>
                        <strong>{provider.name}</strong>
                        {provider.email && <span>{provider.email}</span>}
                      </button>
                    ))}
                </div>
              )}
              {selectedProvider && (
                <button type="button" className={styles.clearProvider} onClick={() => setSelectedProvider(null)}>
                  Invite as new provider instead
                </button>
              )}
            </div>
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