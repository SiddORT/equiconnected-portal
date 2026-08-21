import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import styles from './SignupPage.module.css';

export function ProviderLoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { from?: { pathname: string }; verifiedEmail?: string; verifiedNotice?: string } | null;
  const [email, setEmail] = useState(state?.verifiedEmail ?? '');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(state?.verifiedNotice ?? null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (state?.verifiedEmail || state?.verifiedNotice) {
      navigate('/provider/login', { replace: true, state: null });
    }
  }, [navigate, state?.verifiedEmail, state?.verifiedNotice]);

  if (isLoading) return <LoadingScreen message="Checking session…" />;
  if (isAuthenticated) return <Navigate to={state?.from?.pathname ?? '/provider/account'} replace />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setError('Enter your email address and password.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim().toLowerCase(), password);
      navigate(state?.from?.pathname ?? '/provider/account', { replace: true });
    } catch (requestError) {
      setError(extractErrorMessage(requestError, 'Sign in failed. Please check your credentials.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.card} aria-labelledby="provider-login-heading">
        <header className={styles.header}>
          <Link className={styles.brand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.logo} />
            <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
          </Link>
          <p className={styles.eyebrow}>Provider portal</p>
          <h1 id="provider-login-heading" className="text-display">Sign in to your provider account.</h1>
          <p className={styles.intro}>Approved providers can access their account confirmation here.</p>
        </header>
        <form className={styles.form} onSubmit={submit} noValidate>
          {notice && <Alert variant="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}
          {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}
          <Input label="Email address" type="email" id="provider-login-email" autoComplete="username email" value={email} onChange={(event) => setEmail(event.target.value)} disabled={submitting} required />
          <Input label="Password" type={showPassword ? 'text' : 'password'} id="provider-login-password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} disabled={submitting} required rightAdornment={<button type="button" className={styles.showHide} onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? '🙈' : '👁'}</button>} />
          <Button type="submit" variant="primary" size="lg" fullWidth loading={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</Button>
        </form>
        <p className={styles.intro}><Link className={styles.homeLink} to="/provider/signup">Need a provider account? Register here.</Link></p>
      </section>
    </main>
  );
}