import { useState } from 'react';
import { resendVerification } from '@/api/auth';
import { extractErrorMessage } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

export function VerificationResend({ initialEmail = '' }: { initialEmail?: string }) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const response = await resendVerification(email.trim());
      setMessage(response.message);
    } catch (error) {
      setMessage(extractErrorMessage(error, 'Could not request a link. Please try again later.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <Input label="Email address" type="email" value={email}
        onChange={(event) => setEmail(event.target.value)} required disabled={busy} />
      <Button type="submit" disabled={busy}>Request a new verification link</Button>
      {message && <p role="status">{message}</p>}
    </form>
  );
}