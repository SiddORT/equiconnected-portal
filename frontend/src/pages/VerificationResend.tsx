import { useState } from 'react';
import { resendVerification, resendVerificationToken } from '@/api/auth';
import { extractErrorMessage } from '@/api/client';
import { Button } from '@/components/ui/Button';

type RecoveryTarget = { email: string; token?: never } | { token: string | null; email?: never };

export function VerificationResend(target: RecoveryTarget) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const available = 'email' in target ? Boolean(target.email) : Boolean(target.token);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!available || busy) return;
    setBusy(true);
    setMessage('');
    try {
      const response = target.email
        ? await resendVerification(target.email)
        : await resendVerificationToken(target.token!);
      setMessage(response.message);
    } catch (error) {
      setMessage(extractErrorMessage(error, 'Could not request a link. Please try again later.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <Button type="submit" disabled={busy || !available} loading={busy}>Request a new verification link</Button>
      {!available && <p role="status">Without a verification link, we cannot request a new one here. Please use the link from your email or contact support.</p>}
      {message && <p role="status">{message}</p>}
    </form>
  );
}