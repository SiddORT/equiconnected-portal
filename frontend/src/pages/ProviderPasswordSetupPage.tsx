import { useState } from 'react';
import axios from 'axios';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import * as authApi from '@/api/auth';
import { getApiErrorCode } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from './SignupPage.module.css';

function setupErrorMessage(error: unknown, isReset: boolean): string {
  const operation = isReset ? 'reset' : 'setup';
  // Only explicit token rejections establish that a link is unusable.
  const code = getApiErrorCode(error);
  if (isReset) {
    if (code === 'provider_portal_recovery_link_invalid') return 'This password reset link is invalid. Ask an administrator to send a new password reset email.';
    if (code === 'provider_portal_recovery_link_expired') return 'This password reset link has expired. Ask an administrator to send a new password reset email.';
    if (code === 'provider_portal_recovery_link_used') return 'This password reset link has already been used or replaced. If you already changed your password, sign in; otherwise ask an administrator to send a new password reset email.';
  }
  if (code === 'provider_portal_link_invalid') return 'This provider portal link is invalid. Ask an administrator for a new link.';
  if (code === 'provider_portal_link_expired') return 'This provider portal link has expired. Ask an administrator for a new link.';
  if (code === 'provider_portal_link_used') return 'This provider portal link has already been used or replaced. Try signing in if you already submitted your password, or ask an administrator for a new link.';
  if (axios.isAxiosError(error)) {
    if (!error.response) return 'We could not connect to the provider portal. Check your connection and try again with this link. If you already submitted your password, try signing in first.';
    if (error.response.status === 422) return 'Your password could not be accepted. Use 8–128 characters with upper- and lowercase letters and a number, and make sure both passwords match.';
    if (error.response.status === 429) return `Too many password ${operation} attempts. Please wait a few minutes, then try again with this link.`;
    if (error.response.status >= 500) return `Provider password ${operation} is temporarily unavailable. Please try again with this link in a few minutes. If you already submitted your password, try signing in first.`;
  }
  return `We could not confirm your password ${operation}. Try signing in if you already submitted your password, or try again with this link. If this continues, contact an administrator.`;
}

export function ProviderPasswordSetupPage() {
  const [params] = useSearchParams();
  const { pathname } = useLocation();
  const isReset = pathname === '/provider/reset-password';
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
    if (password.length < 8 || password.length > 128 || !/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) {
      setError('Use 8–128 characters with upper- and lowercase letters and a number.');
      return;
    }
    if (password !== confirmation) {
      setError('Passwords do not match.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (isReset) {
        await authApi.resetProviderPortalPassword(token, password, confirmation);
      } else {
        await authApi.setupProviderPortalPassword(token, password, confirmation);
      }
      setComplete(true);
    } catch (err) {
      setError(setupErrorMessage(err, isReset));
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
          <h1 id="setup-password-heading" className="text-display">
            {isReset ? 'Reset your password' : 'Set your password'}
          </h1>
          <p className={styles.intro}>
            {isReset
              ? 'Choose a new secure password for your provider portal account.'
              : 'Choose a secure password to access and maintain your provider profile.'}
          </p>
        </header>
        {complete ? (
          <section className={styles.success} aria-live="polite">
            <div className={styles.successMark} aria-hidden="true">✓</div>
            <h2 className="text-display">{isReset ? 'Password reset' : 'Password set'}</h2>
            <p>{isReset ? 'Your new password is ready. Sign in to continue.' : 'Your provider portal account is ready. Sign in to continue.'}</p>
            <Link className={styles.homeLink} to="/provider/login">Go to provider sign in</Link>
          </section>
        ) : (
          <form className={styles.form} onSubmit={submit} noValidate>
            {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}
            <Input label="Password" id="portal-password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={saving || !token} containerClassName={styles.signupField} hint="At least 8 characters with upper- and lowercase letters and a number." required rightAdornment={<button type="button" className={styles.showHide} onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} disabled={saving || !token}>{showPassword ? '🙈' : '👁'}</button>} />
            <Input label="Confirm password" id="portal-password-confirmation" type={showConfirmation ? 'text' : 'password'} autoComplete="new-password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} disabled={saving || !token} containerClassName={styles.signupField} required rightAdornment={<button type="button" className={styles.showHide} onClick={() => setShowConfirmation((visible) => !visible)} aria-label={showConfirmation ? 'Hide password confirmation' : 'Show password confirmation'} aria-pressed={showConfirmation} disabled={saving || !token}>{showConfirmation ? '🙈' : '👁'}</button>} />
            <Button type="submit" fullWidth loading={saving} disabled={!token}>
              {isReset ? 'Reset password' : 'Set password'}
            </Button>
          </form>
        )}
      </section>
    </main>
  );
}