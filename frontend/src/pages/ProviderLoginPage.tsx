import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import styles from './ProviderLoginPage.module.css';

interface LoginLocationState {
  from?: { pathname: string };
  verifiedEmail?: string;
  verifiedNotice?: string;
}

export function ProviderLoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LoginLocationState | null;
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
    <div
      className={styles.page}
      data-testid="provider-login-page"
      data-layout="provider-care-story-left-form"
      data-mobile-layout="single-column-at-820px"
    >
      <section className={styles.story} data-testid="provider-care-panel" aria-labelledby="provider-story-heading">
        <img
          className={styles.storyImage}
          src="/provider-veterinary-care.jpg"
          alt="A hoof-care specialist supporting a horse's raised leg during a routine examination."
        />
        <div className={styles.storyOverlay} aria-hidden="true" />
        <div className={styles.storyContent}>
          <Link className={styles.storyBrand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.storyLogo} />
            <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
          </Link>
          <p className={styles.storyEyebrow}>Provider portal</p>
          <h1 id="provider-story-heading">Care that keeps every horse moving forward.</h1>
          <p className={styles.storyCopy}>
            Your provider workspace brings practice details and account access together, so you can stay focused on the care in front of you.
          </p>
          <a
            className={styles.photoCredit}
            href="https://commons.wikimedia.org/wiki/Category:Farrier_and_Veterinarian_at_Obligation_Farm,_Maryland,_2025"
            target="_blank"
            rel="noreferrer"
          >
            Photo: USDA / public domain
          </a>
        </div>
      </section>

      <main className={styles.main} data-testid="provider-login-form">
        <div className={styles.formCard}>
          <div className={styles.mobileBrand}>
            <Link className={styles.mobileBrandLink} to="/" aria-label="EquiConnected home">
              <img src="/logo.png" alt="" />
              <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
            </Link>
          </div>

          <header className={styles.formHeader}>
            <p className={styles.eyebrow}>Provider portal</p>
            <h1 id="provider-login-heading" className="text-display">Welcome back to your practice.</h1>
            <p>Sign in with the email address associated with your approved provider account.</p>
          </header>

          {notice && <Alert variant="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}
          {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

          <form className={styles.form} onSubmit={submit} noValidate>
            <Input
              label="Email address"
              type="email"
              id="provider-login-email"
              autoComplete="username email"
              placeholder="you@practice.com"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                if (error) setError(null);
              }}
              disabled={submitting}
              required
            />
            <Input
              label="Password"
              type={showPassword ? 'text' : 'password'}
              id="provider-login-password"
              autoComplete="current-password"
              placeholder="Enter your password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                if (error) setError(null);
              }}
              disabled={submitting}
              required
              rightAdornment={
                <button
                  type="button"
                  className={styles.showHide}
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  disabled={submitting}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              }
            />
            <Button type="submit" variant="primary" size="lg" fullWidth loading={submitting}>
              {submitting ? 'Signing in…' : 'Sign in to provider portal'}
            </Button>
          </form>

          <p className={styles.noRegister}>
            New to EquiConnected? <Link to="/provider/signup">Register your provider practice</Link>.
          </p>
          <p className={styles.securityNote}>This sign-in is reserved for approved equine care providers.</p>
        </div>
      </main>
    </div>
  );
}