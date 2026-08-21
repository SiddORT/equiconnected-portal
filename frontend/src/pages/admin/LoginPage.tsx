/**
 * Admin login page — /admin/login
 * Redirects to dashboard if already authenticated.
 */
import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { extractErrorMessage } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Alert } from '@/components/ui/Alert';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import styles from './LoginPage.module.css';

interface FormState {
  email: string;
  password: string;
}

interface FormErrors {
  email?: string;
  password?: string;
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

export function LoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const memberLogin = location.pathname === '/login';
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname
    ?? (memberLogin ? '/profile' : '/admin/dashboard');

  const [form, setForm] = useState<FormState>({ email: '', password: '' });
  const [fieldErrors, setFieldErrors] = useState<FormErrors>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Already authenticated — go straight to dashboard
  if (!isLoading && isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  if (isLoading) {
    return <LoadingScreen message="Checking session…" />;
  }

  function handleChange(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (fieldErrors[field]) {
      setFieldErrors((prev) => ({ ...prev, [field]: undefined }));
    }
    if (globalError) setGlobalError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
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
    } catch (err) {
      setGlobalError(extractErrorMessage(err, 'Login failed. Please check your credentials.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.leftPanel} aria-hidden="true">
        <div className={styles.leftContent}>
          <img src="/logo.png" alt="" className={styles.logoMark} aria-hidden="true" />
          <h1 className={`text-display ${styles.leftTitle}`}>EquiConnected</h1>
          <p className={styles.leftSubtitle}>
            Secure healthcare coordination for the modern era.
          </p>
          <ul className={styles.leftFeatures} role="list">
            {[
              'Role-based access control',
              'Full audit trail',
              'End-to-end encryption',
              'Real-time coordination',
            ].map((f) => (
              <li key={f} className={styles.leftFeature}>
                <span className={styles.leftCheck} aria-hidden="true">✓</span>
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <main className={styles.rightPanel}>
        <div className={styles.formCard}>
          <div className={styles.formHeader}>
<div className={styles.formIcon} aria-hidden="true">🔐</div>
            <h2 className={`text-display ${styles.formTitle}`}>{memberLogin ? 'Member sign in' : 'Admin sign in'}</h2>
            <p className={styles.formSubtitle}>
              {memberLogin
                ? 'Enter your approved member credentials to access your profile.'
                : 'Enter your administrator credentials to access the portal.'}
            </p>
          </div>

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
              id="admin-email"
              autoComplete="username email"
              placeholder="you@organisation.com"
              value={form.email}
              onChange={(e) => handleChange('email', e.target.value)}
              error={fieldErrors.email}
              disabled={submitting}
              required
            />

            <Input
              label="Password"
              type={showPassword ? 'text' : 'password'}
              name="password"
              id="admin-password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={form.password}
              onChange={(e) => handleChange('password', e.target.value)}
              error={fieldErrors.password}
              disabled={submitting}
              required
              rightAdornment={
                <button
                  type="button"
                  className={styles.showHide}
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? '🙈' : '👁'}
                </button>
              }
            />

            <Button
              type="submit"
              variant="primary"
              fullWidth
              size="lg"
              loading={submitting}
            >
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <p className={styles.noRegister}>
            {memberLogin ? 'Need an approved member account?' : 'This portal is for authorised administrators only.'}
            <br />
            Joining as a horse owner or stable manager?{' '}
            <Link to="/signup" className={styles.signupLink}>Create a public account</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
