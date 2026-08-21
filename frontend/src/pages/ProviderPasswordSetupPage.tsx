import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import * as authApi from '@/api/auth';
import { extractErrorMessage, getApiErrorCode } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from './SignupPage.module.css';

export function ProviderPasswordSetupPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState<string | null>(
    token ? null : 'This provider portal link is invalid.'
  );
  const [complete, setComplete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    if (password.length < 8 || !/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) {
      setError('Use at least 8 characters with upper- and lowercase letters and a number.');
      return;
    }
    if (password !== confirmation) {
      setError('Passwords do not match.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await authApi.setupProviderPortalPassword(token, password, confirmation);
      setComplete(true);
    } catch (err) {
      const code = getApiErrorCode(err);
      setError(
        code === 'provider_portal_link_expired'
          ? 'This provider portal link has expired. Ask an administrator for a new link.'
          : code === 'provider_portal_link_used'
            ? 'This provider portal link has already been used or replaced.'
            : extractErrorMessage(err, 'This provider portal link is invalid.')
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.card} aria-labelledby="setup-password-heading">
        <header className={styles.header}>
          <Link className={styles.brand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.logo} />
            <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
          </Link>
          <p className={styles.eyebrow}>Provider portal</p>
          <h1 id="setup-password-heading" className="text-display">Set your password</h1>
          <p className={styles.intro}>Choose a secure password to access and maintain your provider profile.</p>
        </header>
        {complete ? (
          <section className={styles.success} aria-live="polite">
            <div className={styles.successMark} aria-hidden="true">✓</div>
            <h2 className="text-display">Password set</h2>
            <p>Your provider portal account is ready. Sign in to continue.</p>
            <Link className={styles.homeLink} to="/provider/login">Go to provider sign in</Link>
          </section>
        ) : (
          <form className={styles.form} onSubmit={submit} noValidate>
            {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}
            <Input label="Password" id="portal-password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={saving || !token} containerClassName={styles.signupField} hint="At least 8 characters with upper- and lowercase letters and a number." required rightAdornment={<button type="button" className={styles.showHide} onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} disabled={saving || !token}>{showPassword ? '🙈' : '👁'}</button>} />
            <Input label="Confirm password" id="portal-password-confirmation" type={showConfirmation ? 'text' : 'password'} autoComplete="new-password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} disabled={saving || !token} containerClassName={styles.signupField} required rightAdornment={<button type="button" className={styles.showHide} onClick={() => setShowConfirmation((visible) => !visible)} aria-label={showConfirmation ? 'Hide password confirmation' : 'Show password confirmation'} aria-pressed={showConfirmation} disabled={saving || !token}>{showConfirmation ? '🙈' : '👁'}</button>} />
            <Button type="submit" fullWidth loading={saving} disabled={!token}>Set password</Button>
          </form>
        )}
      </section>
    </main>
  );
}