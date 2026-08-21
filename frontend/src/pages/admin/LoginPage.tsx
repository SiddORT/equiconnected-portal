/**
 * Admin login page — /admin/login
 * Redirects to dashboard if already authenticated.
 */
import { useEffect, useState } from 'react';
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

export function LoginPage() {
  const { isAuthenticated, isLoading, login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const loginState = location.state as LoginLocationState | null;
  const from = loginState?.from?.pathname ?? '/admin/dashboard';

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
      // Keep the success notice in component state while removing the
      // one-time handoff data from browser history.
      navigate('/admin/login', { replace: true, state: null });
    }
  }, [loginState?.verifiedEmail, loginState?.verifiedNotice, navigate]);

  // Keep authenticated members out of the admin-only route. Without this
  // role check, the admin guard and this page can redirect a member between
  // /admin/login and /admin/dashboard indefinitely.
  if (!isLoading && isAuthenticated) {
    return <Navigate to={user?.role === 'admin' ? from : '/providers'} replace />;
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
    <div className={styles.page} data-testid="admin-login-page" data-layout="admin-centered">
      <main className={styles.main} aria-labelledby="admin-login-heading">
        <div className={styles.brand}>
          <img src="/logo.png" alt="" className={styles.logoMark} aria-hidden="true" />
          <div>
            <strong>EquiConnected</strong>
            <span>Administration portal</span>
          </div>
        </div>

        <div className={styles.formCard} data-testid="admin-login-form">
          <div className={styles.formHeader}>
            <p className={styles.formEyebrow}>Secure administrator access</p>
            <h1 id="admin-login-heading" className={`text-display ${styles.formTitle}`}>
              Admin sign in
            </h1>
            <p className={styles.formSubtitle}>
              Enter your administrator credentials to access the portal.
            </p>
          </div>

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
            This portal is for authorised administrators only.
            <br />
            Joining as a horse owner or stable manager?{' '}
            <Link to="/signup" className={styles.signupLink}>Create a public account</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
