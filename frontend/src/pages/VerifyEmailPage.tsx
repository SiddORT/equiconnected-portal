/** Public email-verification landing page — /verify-email?token=... */
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import * as authApi from '@/api/auth';
import styles from './SignupPage.module.css';

type VerificationState = 'verifying' | 'verified' | 'error';

export function VerifyEmailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const tokenRef = useRef(new URLSearchParams(location.search).get('token'));
  const verificationStarted = useRef(false);
  const [state, setState] = useState<VerificationState>('verifying');
  const [message, setMessage] = useState('We are securely verifying your email address.');

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
        setState('verified');
        setMessage(response.message);
        navigate('/login', {
          replace: true,
          state: {
            verifiedEmail: response.email,
            verifiedNotice: response.message,
          },
        });
      })
      .catch((error) => {
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
          <div className={`${styles.successMark} ${state === 'error' ? styles.errorMark : ''}`} aria-hidden="true">
            {state === 'verifying' ? '…' : state === 'verified' ? '✓' : '!'}
          </div>
          <h1 className="text-display">
            {state === 'verifying' ? 'Verifying your email' : state === 'verified' ? 'Email verified' : 'Unable to verify email'}
          </h1>
          <p>{message}</p>
          {state === 'error' && <p className={styles.muted}>For your security, verification links can only be used once and expire after 24 hours.</p>}
          {state === 'error' && <Link className={styles.homeLink} to="/">Return to EquiConnected</Link>}
        </section>
      </section>
    </main>
  );
}