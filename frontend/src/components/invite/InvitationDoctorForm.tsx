/**
 * InvitationDoctorForm — thin adapter that runs the shared DoctorForm in
 * invitation mode and adds the Organization Association section.
 *
 * Selected organizations are associated (as PENDING relationships) when the
 * invitation is submitted.
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
import { OrganizationAssociation } from './OrganizationAssociation';
import type { InvitationDraftPayload, InvitationTokenData, OrgSearchResult } from '@/types';
import styles from './InvitationForms.module.css';

interface InvitationDoctorFormProps {
  token: string;
  data: InvitationTokenData;
}

export function InvitationDoctorForm({ token, data }: InvitationDoctorFormProps) {
  const navigate = useNavigate();
  const [draftSaved, setDraftSaved] = useState(false);
  const [externalErrors, setExternalErrors] = useState<Record<string, string>>({});
  const [selectedOrgs, setSelectedOrgs] = useState<OrgSearchResult[]>([]);

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
      // Organizations are reconciled server-side in the same transaction as
      // the submit, so a failed submit leaves no stray relationships behind.
      await submitInvitation(token, {
        ...payload,
        organization_ids: selectedOrgs.map((org) => org.id),
      });
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
          loadSpecializations: () => getInvitationSpecializations(token),
          onSaveDraft: handleSaveDraft,
          onSubmit: handleSubmit,
          externalErrors,
        }}
      >
        <OrganizationAssociation token={token} selected={selectedOrgs} onChange={setSelectedOrgs} />
      </DoctorForm>
    </div>
  );
}
