/** Public email-verification landing page — /verify-email?token=... */
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import * as authApi from '@/api/auth';
import styles from './SignupPage.module.css';

type VerificationState = 'verifying' | 'verified' | 'error';
const REDIRECT_DELAY_MS = 1800;

export function VerifyEmailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const tokenRef = useRef(new URLSearchParams(location.search).get('token'));
  const verificationStarted = useRef(false);
  const isMounted = useRef(true);
  const redirectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [state, setState] = useState<VerificationState>('verifying');
  const [message, setMessage] = useState('We are securely verifying your email address.');
  const [redirectPath, setRedirectPath] = useState<'/login' | '/provider/login'>('/login');

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      if (redirectTimer.current) clearTimeout(redirectTimer.current);
    };
  }, []);

  useEffect(() => {
    // React Strict Mode runs effects twice in development. Verification is
    // deliberately single-use, so never issue a second redemption request.
    if (verificationStarted.current) return;
    verificationStarted.current = true;

    const token = tokenRef.current;
    window.history.replaceState({}, document.title, '/verify-email');
    if (!token) {
      setState('error');
      setMessage('This verification link is invalid. Please use the link from your email.');
      return;
    }
    authApi.verifyEmail(token)
      .then((response) => {
        if (!isMounted.current) return;
        setState('verified');
        setMessage(response.message);
        setRedirectPath(response.redirect_to ?? '/login');
        redirectTimer.current = setTimeout(() => {
          if (!isMounted.current) return;
          const redirectTo = response.redirect_to ?? '/login';
          navigate(redirectTo, {
            replace: true,
            state: {
              verifiedEmail: response.email,
              verifiedNotice: response.message,
            },
          });
        }, REDIRECT_DELAY_MS);
      })
      .catch((error) => {
        if (!isMounted.current) return;
        setState('error');
        setMessage(extractErrorMessage(error, 'We could not verify this email link.'));
      });
  }, [navigate]);

  return (
    <main className={styles.page}>
      <section className={`${styles.card} ${styles.verifyCard}`} aria-live="polite">
        <header className={styles.header}>
          <Link className={styles.brand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.logo} />
            <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
          </Link>
        </header>
        <section className={styles.success}>
          <div
            className={`${styles.successMark} ${state === 'error' ? styles.errorMark : ''} ${state === 'verified' ? styles.verifiedMark : ''}`}
            aria-hidden="true"
          >
            {state === 'verifying' ? '…' : state === 'verified' ? '✓' : '!'}
          </div>
          <h1 className="text-display">
            {state === 'verifying'
              ? 'Verifying your email'
              : state === 'verified'
                ? 'Email verified successfully'
                : 'Unable to verify email'}
          </h1>
          <p>{message}</p>
          {state === 'verified' && (
            <>
              <p className={styles.redirectMessage} role="status">
                Redirecting you to {redirectPath === '/provider/login' ? 'provider' : 'member'} sign in…
              </p>
              <div className={styles.redirectTrack} aria-hidden="true">
                <span />
              </div>
            </>
          )}
          {state === 'error' && <p className={styles.muted}>For your security, verification links can only be used once and expire after 24 hours.</p>}
          {state === 'error' && <Link className={styles.homeLink} to="/">Return to EquiConnected</Link>}
        </section>
      </section>
    </main>
  );
}