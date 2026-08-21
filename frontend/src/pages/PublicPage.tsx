/**
 * Public "Coming Soon" page for the EquiConnected portal.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { recordPublicVisit, registerSubscriber } from '@/api/public';
import { systemCalendarDate, useTimeSettings } from '@/app/TimeSettingsContext';
import type { SubscriberRegistrationType } from '@/types';
import styles from './PublicPage.module.css';

export function PublicPage() {
  const { settings, isLoading: settingsLoading, error: settingsError } = useTimeSettings();
  const [email, setEmail] = useState('');
  const [registrationType, setRegistrationType] = useState<SubscriberRegistrationType | ''>('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [registrationTypeError, setRegistrationTypeError] = useState('');
  const [formError, setFormError] = useState('');

  useEffect(() => {
    // Wait for the shared settings so the client-side once-per-day key agrees
    // with the backend's system-calendar visit bucket.
    if (settingsLoading || settingsError) return;

    const storageKey = 'equiconnected-public-visit-date';
    const today = systemCalendarDate(new Date(), settings.timezone);
    if (window.localStorage.getItem(storageKey) === today) return;

    window.localStorage.setItem(storageKey, today);
    void recordPublicVisit().catch(() => {
      window.localStorage.removeItem(storageKey);
    });
  }, [settings.timezone, settingsError, settingsLoading]);

  async function handleNotify(e: React.FormEvent) {
    e.preventDefault();
    if (!registrationType) {
      setRegistrationTypeError('Please choose how you would like to register.');
      return;
    }
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setEmailError('Please enter a valid email address.');
      return;
    }
    setEmailError('');
    setRegistrationTypeError('');
    setFormError('');
    setSubmitting(true);
    try {
      await registerSubscriber({ email: email.trim(), registration_type: registrationType });
      setSubmitted(true);
    } catch (requestError) {
      setFormError(
        extractErrorMessage(
          requestError,
          'We could not save your registration. Please try again shortly.'
        )
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.page}>
      {/* ── Background decorative elements ──────────────────────── */}
      <div className={styles.bgCircle1} aria-hidden="true" />
      <div className={styles.bgCircle2} aria-hidden="true" />

      <main className={styles.main} id="main-content">
        {/* ── Logo ─────────────────────────────────────────────── */}
        <header className={styles.header}>
          <div className={styles.logoMark} aria-hidden="true">
            <img src="/logo.png" alt="" />
          </div>
          <div className={styles.logoText}>
            <span className={styles.logoName}>equiconnected</span>
            <span className={styles.logoTagline}>CONNECTING HORSES WITH THE RIGHT CARE</span>
          </div>
        </header>

        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className={styles.hero} aria-labelledby="coming-soon-heading">
          <p className={styles.preTitle}>We're getting ready</p>
          <h1 id="coming-soon-heading" className={`text-display ${styles.heading}`}>
            Something beautiful
            <span className={styles.headingAccent}> is on its way.</span>
          </h1>
          <p className={styles.subtitle}>
            The EquiConnected portal is launching soon — bringing hospitals, 
            care teams, and visitors together through secure, elegant technology.
          </p>

          {/* ── Notify form ──────────────────────────────────────── */}
          <div className={styles.notifyBlock}>
            {submitted ? (
              <div className={styles.successMessage} role="status">
                <span className={styles.successIcon} aria-hidden="true">✓</span>
                <p>
                  <strong>You're on the list.</strong><br />
                  The EquiConnected team will be in touch soon.
                </p>
              </div>
            ) : (
              <form onSubmit={handleNotify} className={styles.form} noValidate>
                <label htmlFor="registration-type" className={styles.formLabel}>
                  Register as
                </label>
                <select
                  id="registration-type"
                  value={registrationType}
                  onChange={(e) => {
                    setRegistrationType(e.target.value as SubscriberRegistrationType | '');
                    setRegistrationTypeError('');
                    setFormError('');
                  }}
                  className={`${styles.registrationSelect} ${registrationTypeError ? styles['registrationSelect--error'] : ''}`}
                  aria-describedby={registrationTypeError ? 'registration-type-error' : undefined}
                  aria-invalid={!!registrationTypeError}
                  required
                  disabled={submitting}
                >
                  <option value="">Choose your role</option>
                  {REGISTRATION_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
                <label htmlFor="notify-email" className={styles.formLabel}>
                  Email address
                </label>
                <div className={styles.formRow}>
                  <input
                    id="notify-email"
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      setEmailError('');
                      setFormError('');
                    }}
                    placeholder="your@email.com"
                    className={`${styles.emailInput} ${emailError ? styles['emailInput--error'] : ''}`}
                    aria-describedby={emailError ? 'notify-email-error' : undefined}
                    aria-invalid={!!emailError}
                    autoComplete="email"
                    required
                    disabled={submitting}
                  />
                  <button type="submit" className={styles.notifyBtn} disabled={submitting}>
                    {submitting ? 'Submitting…' : 'Register'}
                  </button>
                </div>
                {registrationTypeError && (
                  <p id="registration-type-error" className={styles.errorMsg} role="alert">
                    {registrationTypeError}
                  </p>
                )}
                {emailError && (
                  <p id="notify-email-error" className={styles.errorMsg} role="alert">
                    {emailError}
                  </p>
                )}
                {formError && <p className={styles.errorMsg} role="alert">{formError}</p>}
              </form>
            )}
          </div>
        </section>

        {/* ── Features teaser ──────────────────────────────────── */}
        <section className={styles.features} aria-label="What's coming">
          {TEASERS.map((t) => (
            <div key={t.title} className={styles.featureItem}>
              <span className={styles.featureIcon} aria-hidden="true">{t.icon}</span>
              <h2 className={styles.featureTitle}>{t.title}</h2>
              <p className={styles.featureDesc}>{t.desc}</p>
            </div>
          ))}
        </section>

        {/* ── Divider ──────────────────────────────────────────── */}
        <div className={styles.dividerLine} aria-hidden="true" />

        {/* ── Admin link ───────────────────────────────────────── */}
        <div className={styles.adminLink}>
          <Link to="/signup" className={styles.signupCta}>
            Register as a member
          </Link>
          <span className={styles.linkSeparator} aria-hidden="true">·</span>
          <Link to="/provider/signup" className={styles.signupCta}>
            Register as a provider
          </Link>
          <span className={styles.linkSeparator} aria-hidden="true">·</span>
          <Link to="/admin/login" className={styles.adminAnchor}>
            Admin Portal →
          </Link>
        </div>
      </main>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className={styles.footer} role="contentinfo">
        <p>© {new Date().getFullYear()} EquiConnected. All rights reserved.</p>
      </footer>
    </div>
  );
}

const TEASERS = [
  {
    icon: '🏥',
    title: 'Hospital Portal',
    desc: 'Streamlined tools for healthcare administrators and clinical teams.',
  },
  {
    icon: '🤝',
    title: 'Visitor Coordination',
    desc: 'Secure, dignified access management for families and visitors.',
  },
  {
    icon: '🔒',
    title: 'Built for Trust',
    desc: 'Enterprise-grade security with full audit trails and role-based access.',
  },
];

const REGISTRATION_TYPES: Array<{ value: SubscriberRegistrationType; label: string }> = [
  { value: 'VET', label: 'Vet' },
  { value: 'HORSE_OWNER', label: 'Horse Owner' },
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'CLINIC', label: 'Clinic' },
  { value: 'STABLE_MANAGER', label: 'Stable Manager' },
  { value: 'OTHER', label: 'Other' },
];
