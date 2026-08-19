/**
 * InvitationProviderForm — thin adapter that runs the shared ProviderForm in
 * invitation mode: save-draft and submit go to the token endpoints.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  extractSubmitFieldErrors,
  getInvitationSpecializations,
  saveInvitationDraft,
  submitInvitation,
} from '@/api/invitations';
import { ProviderForm } from '@/components/admin/ProviderForm';
import type { InvitationDraftPayload, InvitationTokenData } from '@/types';
import styles from './InvitationForms.module.css';

interface InvitationProviderFormProps {
  token: string;
  data: InvitationTokenData;
}

export function InvitationProviderForm({ token, data }: InvitationProviderFormProps) {
  const navigate = useNavigate();
  const [draftSaved, setDraftSaved] = useState(false);
  const [externalErrors, setExternalErrors] = useState<Record<string, string>>({});

  async function handleSaveDraft(payload: InvitationDraftPayload) {
    setDraftSaved(false);
    setExternalErrors({});
    await saveInvitationDraft(token, payload);
    setDraftSaved(true);
    window.setTimeout(() => setDraftSaved(false), 5000);
  }

  async function handleSubmit(payload: InvitationDraftPayload) {
    setDraftSaved(false);
    setExternalErrors({});
    try {
      await submitInvitation(token, payload);
    } catch (err) {
      setExternalErrors(extractSubmitFieldErrors(err));
      throw err;
    }
    navigate('/provider/invite/success');
  }

  return (
    <div className={styles.wrapper}>
      {draftSaved && (
        <div className={styles.savedBanner} role="status">
          ✓ Draft saved. You can return to this link later to finish.
        </div>
      )}
      <ProviderForm
        invitation={{
          providerType: data.provider_type,
          initial: data.provider,
          loadSpecializations: () => getInvitationSpecializations(token),
          onSaveDraft: handleSaveDraft,
          onSubmit: handleSubmit,
          externalErrors,
        }}
      />
    </div>
  );
}
