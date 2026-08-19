/**
 * InvitationPage — public landing page for provider invitation links.
 * Route: /provider/invite/:token (no authentication required).
 */
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { getInvitationByToken, getPublicErrorCode, getPublicErrorStatus } from '@/api/invitations';
import { InvitationDoctorForm } from '@/components/invite/InvitationDoctorForm';
import { InvitationProviderForm } from '@/components/invite/InvitationProviderForm';
import { EmptyState } from '@/components/ui/EmptyState';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import type { InvitationTokenData } from '@/types';
import styles from './InvitationPage.module.css';

type PageState =
  | { kind: 'loading' }
  | { kind: 'invalid' }
  | { kind: 'expired' }
  | { kind: 'completed' }
  | { kind: 'cancelled' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; data: InvitationTokenData };

export function InvitationPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<PageState>({ kind: 'loading' });

  useEffect(() => {
    if (!token) {
      setState({ kind: 'invalid' });
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await getInvitationByToken(token);
        if (!cancelled) setState({ kind: 'ready', data });
      } catch (err) {
        if (cancelled) return;
        const status = getPublicErrorStatus(err);
        const code = getPublicErrorCode(err);
        if (status === 404) setState({ kind: 'invalid' });
        else if (status === 410) setState({ kind: 'expired' });
        else if (status === 409 && code === 'invitation_completed') setState({ kind: 'completed' });
        else if (status === 409) setState({ kind: 'cancelled' });
        else setState({ kind: 'error', message: extractErrorMessage(err, 'Something went wrong. Please try again later.') });
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  if (state.kind === 'loading') {
    return <LoadingScreen message="Validating your invitation…" />;
  }

  const heading =
    state.kind === 'ready'
      ? state.data.provider_type === 'DOCTOR'
        ? 'Complete your doctor profile'
        : state.data.provider_type === 'HOSPITAL'
          ? 'Complete your hospital profile'
          : 'Complete your clinic profile'
      : 'Provider invitation';

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.brand}>EquiConnected</span>
        <h1 className={styles.title}>{heading}</h1>
        {state.kind === 'ready' && (
          <p className={styles.subtitle}>
            Fill in the details below. You can save a draft at any time and return to this
            link later, or submit when you're ready for our team to review your profile.
          </p>
        )}
      </header>

      <main className={styles.main}>
        {state.kind === 'invalid' && (
          <EmptyState
            icon={<span aria-hidden="true">🔗</span>}
            title="Invalid invitation"
            description="This invitation link is not valid. Please check that you used the full link from your email."
          />
        )}
        {state.kind === 'expired' && (
          <EmptyState
            icon={<span aria-hidden="true">⏳</span>}
            title="This invitation has expired"
            description="This invitation link is no longer active. Please contact our support team to request a new invitation."
          />
        )}
        {state.kind === 'completed' && (
          <EmptyState
            icon={<span aria-hidden="true">✅</span>}
            title="This invitation has already been completed"
            description="Your submission was already received. Our team will be in touch after review."
          />
        )}
        {state.kind === 'cancelled' && (
          <EmptyState
            icon={<span aria-hidden="true">🚫</span>}
            title="This invitation has been cancelled"
            description="This invitation is no longer available. Please contact our support team if you believe this is a mistake."
          />
        )}
        {state.kind === 'error' && (
          <EmptyState
            icon={<span aria-hidden="true">⚠️</span>}
            title="Something went wrong"
            description={state.message}
          />
        )}
        {state.kind === 'ready' && token && (
          state.data.provider_type === 'DOCTOR' ? (
            <InvitationDoctorForm token={token} data={state.data} />
          ) : (
            <InvitationProviderForm token={token} data={state.data} />
          )
        )}
      </main>
    </div>
  );
}
