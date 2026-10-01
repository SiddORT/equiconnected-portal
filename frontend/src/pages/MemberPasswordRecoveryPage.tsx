import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { hasMemberRole } from '@/features/member/memberAccess';
import { requestMemberPasswordRecovery, resetMemberPassword } from '@/api/auth';
import { getApiErrorCode } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import styles from './SignupPage.module.css';

function resetError(error: unknown): { message: string; unusable: boolean } {
  const code = getApiErrorCode(error);
  if (code === 'member_recovery_link_expired') return {
    message: 'This reset link has expired. Request a new email to continue.', unusable: true,
  };
  if (code === 'member_recovery_link_used') return {
    message: 'This reset link has already been used or replaced. If you already changed your password, sign in; otherwise request a new email.', unusable: true,
  };
  if (code === 'member_recovery_link_invalid') return {
    message: 'This reset link is invalid. Request a new email to continue.', unusable: true,
  };
  if (axios.isAxiosError(error) && error.response?.status === 422) return {
    message: 'Use 8–128 characters with upper- and lowercase letters and a number, and make sure both passwords match.', unusable: false,
  };
  if (axios.isAxiosError(error) && error.response?.status === 429) return {
    message: 'Too many attempts. Wait a few minutes, then try again with this link.', unusable: false,
  };
  return {
    message: 'We could not confirm your password reset. Check your connection and try again with this link. If you already submitted your password, try signing in first.',
    unusable: false,
  };
}

export function MemberPasswordRecoveryPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const isReset = location.pathname === '/reset-password';
  const member = !isLoading && isAuthenticated && hasMemberRole(user);
  // Memory only: never persist the recovery credential in storage or navigation state.
  // The state initializer survives Strict Mode effect replay; only explicit submission redeems it.
  const [token] = useState(() => new URLSearchParams(location.hash.slice(1)).get('token')
    || new URLSearchParams(location.search).get('token') || '');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [error, setError] = useState<string | null>(isReset && !token
    ? 'This reset link is invalid. Request a new email to continue.' : null);
  const [unusable, setUnusable] = useState(isReset && !token);
  const [saving, setSaving] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);

  useEffect(() => {
    if (isReset && (location.search || location.hash)) {
      navigate('/reset-password', { replace: true, state: null });
    }
  }, [isReset, location.search, location.hash, navigate]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (saving || unusable || isLoading) return;
    setError(null);
    if (isReset) {
      if (password.length < 8 || password.length > 128 || !/[a-z]/.test(password)
        || !/[A-Z]/.test(password) || !/\d/.test(password)) {
        setError('Use 8–128 characters with upper- and lowercase letters and a number.');
        return;
      }
      if (password !== confirmation) {
        setError('Passwords do not match.');
        return;
      }
    } else if (!member && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Enter a valid email address.');
      return;
    }
    setSaving(true);
    try {
      if (isReset) {
        await resetMemberPassword(token, password, confirmation);
        // Do not auto-sign in; discard any local session after a successful reset.
        if (member) {
          try { await logout(); } catch { /* AuthContext clears local state even on logout failure. */ }
        }
        navigate('/login', { replace: true, state: {
          verifiedNotice: 'Your password has been reset. Sign in with your new password.',
        } });
      } else {
        await requestMemberPasswordRecovery(member ? undefined : email.trim().toLowerCase());
        setAcknowledged(true);
      }
    } catch (err) {
      if (isReset) {
        const result = resetError(err);
        setError(result.message);
        setUnusable(result.unusable);
      } else if (axios.isAxiosError(err) && err.response?.status === 429) {
        setError('Too many requests. Wait a few minutes, then try again.');
      } else if (member && axios.isAxiosError(err) && err.response?.status === 401) {
        setError('Your session has expired. Sign in again or sign out and request recovery using your email.');
      } else {
        setError('We could not submit your request. Check your connection and try again shortly.');
      }
    } finally { setSaving(false); }
  }

  return <main className={styles.page}>
    <section className={styles.card} aria-labelledby="member-recovery-heading">
      <header className={styles.header}>
        <Link className={styles.brand} to="/" aria-label="EquiConnected home">
          <img src="/logo.png" alt="" className={styles.logo} />
          <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
        </Link>
        <p className={styles.eyebrow}>Member account</p>
        <h1 id="member-recovery-heading" className="text-display">
          {isReset ? 'Choose a new password' : 'Reset your password'}
        </h1>
        <p className={styles.intro}>{isReset
          ? 'Set a new password for your member account. You will then sign in again.'
          : member ? 'Send a recovery link to the email address on your current member account.'
            : 'Enter your member email address and we’ll send a recovery link if your account is eligible.'}</p>
      </header>
      {acknowledged ? <section className={styles.success} role="status">
        <h2>Check your email</h2>
        <p>If the account is eligible, a password reset email will arrive shortly. Check your spam folder too. If it does not arrive, wait a few minutes and request another email.</p>
        <Button type="button" onClick={() => setAcknowledged(false)}>Request another email</Button>
      </section> : <form className={styles.form} onSubmit={submit} noValidate>
        {error && <Alert variant="error">{error}</Alert>}
        {isReset ? <>
          <Input label="New password" id="member-new-password" type={showPassword ? 'text' : 'password'}
            containerClassName={styles.signupField}
            autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)}
            disabled={saving || unusable} required hint="8–128 characters with upper- and lowercase letters and a number."
            rightAdornment={<button className={styles.showHide} type="button" disabled={saving || unusable}
              aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}
              onClick={() => setShowPassword((shown) => !shown)}>{showPassword ? 'Hide' : 'Show'}</button>} />
          <Input label="Confirm new password" id="member-confirm-password" type={showConfirmation ? 'text' : 'password'}
            containerClassName={styles.signupField}
            autoComplete="new-password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)}
            disabled={saving || unusable} required
            rightAdornment={<button className={styles.showHide} type="button" disabled={saving || unusable}
              aria-label={showConfirmation ? 'Hide password confirmation' : 'Show password confirmation'}
              aria-pressed={showConfirmation} onClick={() => setShowConfirmation((shown) => !shown)}>
              {showConfirmation ? 'Hide' : 'Show'}</button>} />
        </> : member ? <p>Recovery email: <strong>{user?.email}</strong></p>
          : <Input label="Email address" id="member-recovery-email" type="email" autoComplete="email"
            containerClassName={styles.signupField}
            value={email} onChange={(e) => setEmail(e.target.value)} disabled={saving || isLoading} required />}
        <Button type="submit" fullWidth loading={saving} disabled={unusable || isLoading}>
          {isReset ? 'Reset password' : 'Send recovery email'}
        </Button>
        {isReset && <Link className={styles.homeLink} to="/forgot-password">Request a new recovery email</Link>}
      </form>}
      <p><Link className={styles.homeLink} to="/login">Return to member sign in</Link></p>
    </section>
  </main>;
}