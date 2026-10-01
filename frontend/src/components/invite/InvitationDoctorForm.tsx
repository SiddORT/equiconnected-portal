/**
 * InvitationDoctorForm — thin adapter that runs the shared DoctorForm in
 * invitation mode and delegates draft / submit to token endpoints.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  extractSubmitFieldErrors,
  getInvitationSpecializations,
  saveInvitationDraft,
  submitInvitation,
} from '@/api/invitations';
import { DoctorForm } from '@/components/admin/DoctorForm';
import type { InvitationDraftPayload, InvitationTokenData } from '@/types';
import styles from './InvitationForms.module.css';

interface InvitationDoctorFormProps {
  token: string;
  data: InvitationTokenData;
}

export function InvitationDoctorForm({ token, data }: InvitationDoctorFormProps) {
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

  async function handleSubmit(payload: import('@/types').InvitationSubmitPayload) {
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
      <DoctorForm
        invitation={{
          initial: data.provider,
          recipientEmail: data.recipient_email,
          emailsEdited: data.emails_edited,
          loadSpecializations: () => getInvitationSpecializations(token),
          onSaveDraft: handleSaveDraft,
          onSubmit: handleSubmit,
          externalErrors,
        }}
      />
    </div>
  );
}
