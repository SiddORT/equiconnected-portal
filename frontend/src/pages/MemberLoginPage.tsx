/**
 * Member login page — /login.
 *
 * This intentionally lives apart from the administrative sign-in page. The
 * authentication flow is the same, but the member journey is about finding
 * trusted equine care rather than operating the portal.
 */
import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import styles from './MemberLoginPage.module.css';

interface FormState {
  email: string;
  password: string;
}

interface FormErrors {
  email?: string;
  password?: string;
}

interface LoginLocationState {
  from?: { pathname: string };
  verifiedEmail?: string;
  verifiedNotice?: string;
}

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {};
  if (!form.email.trim()) {
    errors.email = 'Email is required';
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = 'Enter a valid email address';
  }
  if (!form.password) {
    errors.password = 'Password is required';
  } else if (form.password.length < 8) {
    errors.password = 'Password must be at least 8 characters';
  }
  return errors;
}

export function MemberLoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const loginState = location.state as LoginLocationState | null;
  const from = loginState?.from?.pathname ?? '/providers';

  const [form, setForm] = useState<FormState>(() => ({
    email: loginState?.verifiedEmail ?? '',
    password: '',
  }));
  const [fieldErrors, setFieldErrors] = useState<FormErrors>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(
    () => loginState?.verifiedNotice ?? null
  );
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (loginState?.verifiedEmail || loginState?.verifiedNotice) {
      navigate('/login', { replace: true, state: null });
    }
  }, [loginState?.verifiedEmail, loginState?.verifiedNotice, navigate]);

  if (!isLoading && isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  if (isLoading) {
    return <LoadingScreen message="Checking session…" />;
  }

  function handleChange(field: keyof FormState, value: string) {
    setForm((previous) => ({ ...previous, [field]: value }));
    if (fieldErrors[field]) {
      setFieldErrors((previous) => ({ ...previous, [field]: undefined }));
    }
    if (globalError) setGlobalError(null);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setGlobalError(null);

    const errors = validate(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setSubmitting(true);
    try {
      await login(form.email.trim().toLowerCase(), form.password);
      navigate(from, { replace: true });
    } catch (error) {
      setGlobalError(extractErrorMessage(error, 'Login failed. Please check your credentials.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.page}>
      <section className={styles.story} aria-labelledby="member-story-heading">
        <div className={styles.storyOverlay} aria-hidden="true" />
        <div className={styles.storyContent}>
          <Link className={styles.storyBrand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.storyLogo} />
            <span>
              <strong>EquiConnected</strong>
              <small>Exceptional equine care</small>
            </span>
          </Link>
          <p className={styles.storyEyebrow}>For horse owners &amp; stable managers</p>
          <h1 id="member-story-heading">The right care for every chapter.</h1>
          <p className={styles.storyCopy}>
            Discover trusted hospitals, clinics, and doctors for the horses who rely on you.
          </p>
          <div className={styles.storyQuote}>
            <span aria-hidden="true">“</span>
            <p>Better care starts with feeling connected.</p>
          </div>
        </div>
      </section>

      <main className={styles.main}>
        <div className={styles.formCard}>
          <div className={styles.mobileBrand}>
            <Link className={styles.mobileBrandLink} to="/" aria-label="EquiConnected home">
              <img src="/logo.png" alt="" />
              <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
            </Link>
          </div>

          <header className={styles.formHeader}>
            <p className={styles.eyebrow}>Welcome back</p>
            <h2 className="text-display">Sign in to your care community</h2>
            <p>
              Your trusted provider directory is ready when you are.
            </p>
          </header>

          {successNotice && (
            <Alert variant="success" onDismiss={() => setSuccessNotice(null)}>
              {successNotice}
            </Alert>
          )}

          {globalError && (
            <Alert variant="error" onDismiss={() => setGlobalError(null)}>
              {globalError}
            </Alert>
          )}

          <form onSubmit={handleSubmit} noValidate className={styles.form}>
            <Input
              label="Email address"
              type="email"
              name="email"
              id="member-email"
              autoComplete="username email"
              placeholder="you@example.com"
              value={form.email}
              onChange={(event) => handleChange('email', event.target.value)}
              error={fieldErrors.email}
              disabled={submitting}
              required
            />

            <Input
              label="Password"
              type={showPassword ? 'text' : 'password'}
              name="password"
              id="member-password"
              autoComplete="current-password"
              placeholder="Enter your password"
              value={form.password}
              onChange={(event) => handleChange('password', event.target.value)}
              error={fieldErrors.password}
              disabled={submitting}
              required
              rightAdornment={
                <button
                  type="button"
                  className={styles.showHide}
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                >
                  {showPassword ? '🙈' : '👁'}
                </button>
              }
            />

            <Button type="submit" variant="primary" fullWidth size="lg" loading={submitting}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <p className={styles.noRegister}>
            New to EquiConnected?{' '}
            <Link to="/signup" className={styles.signupLink}>Create your public account</Link>
          </p>
          <p className={styles.securityNote}>
            Your account is for verified horse owners and stable managers.
          </p>
        </div>
      </main>
    </div>
  );
}