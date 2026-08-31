/**
 * Public landing page for the EquiConnected portal.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { recordPublicVisit, registerSubscriber } from '@/api/public';
import { systemCalendarDate, useTimeSettings } from '@/app/TimeSettingsContext';
import { HeroNetwork } from '@/components/public/HeroNetwork';
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

  async function handleNotify(event: React.FormEvent) {
    event.preventDefault();
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
      <div className={styles.bgGlow} aria-hidden="true" />

      <main className={styles.main} id="main-content">
        {/* ── Logo / Header ────────────────────────────────────── */}
        <header className={styles.header}>
          <Link to="/" className={styles.brand} aria-label="EquiConnected home">
            <span className={styles.logoMark} aria-hidden="true">EC</span>
            <span className={styles.logoName}>equiconnected</span>
          </Link>
          <span className={styles.headerNote}>Connected care, made clear</span>
        </header>

        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className={styles.hero} aria-labelledby="hero-heading">
          <div className={styles.heroContent}>
            <p className={styles.eyebrow}><span className={styles.eyebrowRule} />EquiConnected</p>
            <h1 id="hero-heading" className={styles.heading}>
              Healthcare,{' '}
              <span>Connected Around You.</span>
            </h1>
            <p className={styles.subtitle}>
              Discover doctors, clinics and hospitals based on your specialization, location and care needs.
            </p>
            <div className={styles.ctas}>
              <Link to="/signup" className={styles.primaryCta}>
                Find care <span aria-hidden="true">↗</span>
              </Link>
              <Link to="/provider/signup" className={styles.secondaryCta}>
                Join as a provider
              </Link>
            </div>
            <p className={styles.trustLine}><span aria-hidden="true" />A clearer path to the right care</p>
            <div className={styles.notifyBlock}>
              <p className={styles.notifyHeading}>Not ready to sign up yet?</p>
              {submitted ? (
                <div className={styles.successMessage} role="status">
                  <span className={styles.successIcon} aria-hidden="true">✓</span>
                  <p>
                    <strong>You&apos;re on the list.</strong><br />
                    The EquiConnected team will be in touch soon.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleNotify} className={styles.form} noValidate aria-label="Get launch updates">
                  <div className={styles.notifyFields}>
                    <div className={styles.notifyField}>
                      <label htmlFor="registration-type" className={styles.formLabel}>Register as</label>
                      <select
                        id="registration-type"
                        value={registrationType}
                        onChange={(event) => {
                          setRegistrationType(event.target.value as SubscriberRegistrationType | '');
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
                    </div>
                    <div className={styles.notifyField}>
                      <label htmlFor="notify-email" className={styles.formLabel}>Email address</label>
                      <input
                        id="notify-email"
                        type="email"
                        value={email}
                        onChange={(event) => {
                          setEmail(event.target.value);
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
                    </div>
                    <button type="submit" className={styles.notifyBtn} disabled={submitting}>
                      {submitting ? 'Submitting…' : 'Keep me posted'}
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
          </div>
          <HeroNetwork />
          <div className={styles.heroCurve} aria-hidden="true" />
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
