/**
 * Public landing page for the EquiConnected portal.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { recordPublicVisit, registerSubscriber } from '@/api/public';
import { systemCalendarDate, useTimeSettings } from '@/app/TimeSettingsContext';
import { HeroImageSlider } from '@/components/public/HeroImageSlider';
import { HowItWorksScroll } from '@/components/public/HowItWorksScroll';
import { SpecializationExplorer } from '@/components/public/SpecializationExplorer';
import { CareNearYou } from '@/components/public/CareNearYou';
import { WhyEquiConnected } from '@/components/public/WhyEquiConnected';
import { Footer } from '@/components/layout/Footer';
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

  useEffect(() => {
    let animationFrame = 0;

    function revealHashTarget() {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(() => {
        const targetId = decodeURIComponent(window.location.hash.slice(1));
        if (!targetId) return;

        const target = document.getElementById(targetId);
        if (!target) return;

        target.scrollIntoView({ block: 'start' });
        const heading = target.querySelector<HTMLElement>('h1, h2');
        if (!heading) return;

        const alreadyFocusable = heading.hasAttribute('tabindex');
        if (!alreadyFocusable) heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
        if (!alreadyFocusable) {
          heading.addEventListener('blur', () => heading.removeAttribute('tabindex'), { once: true });
        }
      });
    }

    revealHashTarget();
    window.addEventListener('hashchange', revealHashTarget);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener('hashchange', revealHashTarget);
    };
  }, []);

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
          <nav className={styles.nav} aria-label="Primary navigation">
            <Link to="/signup">Find care</Link>
            <Link to="/provider/signup">For providers</Link>
            <Link to="/admin/login" className={styles.navCta}>Admin portal</Link>
          </nav>
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
          <div className={styles.heroVisual}>
            <HeroImageSlider />
          </div>
        </section>

        <SpecializationExplorer />
        <HowItWorksScroll />
        <CareNearYou />
        <WhyEquiConnected />

        <section id="provider-join" className={styles.providerSection} aria-labelledby="provider-join-heading">
          <div className={styles.providerCopy}>
            <p className={styles.sectionEyebrow}><span aria-hidden="true" />For providers</p>
            <h2 id="provider-join-heading">Grow your presence with EquiConnected.</h2>
            <p>
              Put your practice in front of members looking for thoughtful equine care.
              Share the information that helps people understand where you fit in their
              healthcare journey.
            </p>
            <Link to="/provider/signup" className={styles.providerCta}>
              Join as a provider <span aria-hidden="true">↗</span>
            </Link>
          </div>
          <ul className={styles.providerTypes} aria-label="Provider types">
            {PROVIDER_TYPES.map((type, index) => (
              <li key={type} className={styles.providerType}>
                <span className={styles.providerTypeNumber} aria-hidden="true">0{index + 1}</span>
                {type}
              </li>
            ))}
          </ul>
        </section>

        <section id="trust-and-transparency" className={styles.trustSection} aria-labelledby="trust-heading">
          <div className={styles.trustIntro}>
            <p className={styles.sectionEyebrow}><span aria-hidden="true" />A clearer way to discover care</p>
            <h2 id="trust-heading">Designed around better healthcare discovery.</h2>
            <p>
              The details you need to make a considered next choice, brought together
              in one calm, connected place.
            </p>
          </div>
          <div className={styles.trustGrid}>
            {TRUST_SIGNALS.map((signal) => (
              <article className={styles.trustCard} key={signal.title}>
                <span className={styles.trustIcon} aria-hidden="true">{signal.icon}</span>
                <h3>{signal.title}</h3>
                <p>{signal.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="get-started" className={styles.finalCta} aria-labelledby="final-cta-heading">
          <div className={styles.finalCtaCopy}>
            <p className={styles.sectionEyebrow}><span aria-hidden="true" />Keep moving forward</p>
            <h2 id="final-cta-heading">Your healthcare network starts here.</h2>
            <p>Find the care you need. Discover providers around you.</p>
            <div className={styles.finalCtaActions}>
              <Link to="/signup" className={styles.finalPrimaryCta}>
                Find care <span aria-hidden="true">↗</span>
              </Link>
              <Link to="/provider/signup" className={styles.finalSecondaryCta}>
                Join as a provider
              </Link>
            </div>
          </div>
          <svg className={styles.connectionMotif} viewBox="0 0 260 220" aria-hidden="true">
            <path d="M28 166C61 166 63 54 114 54s52 112 87 112 31-49 40-93" />
            <path d="M31 166h209" />
            <circle cx="28" cy="166" r="7" />
            <circle cx="114" cy="54" r="7" />
            <circle cx="201" cy="166" r="7" />
            <circle cx="241" cy="73" r="7" />
          </svg>
        </section>
      </main>

      <Footer />
    </div>
  );
}

const PROVIDER_TYPES = ['Doctors', 'Clinics', 'Hospitals'];

const TRUST_SIGNALS = [
  {
    icon: '01',
    title: 'Clear provider information',
    description: 'Review the practice details providers choose to share before you reach out.',
  },
  {
    icon: '02',
    title: 'Transparent community reviews',
    description: 'See ratings and reviews from the EquiConnected community alongside each profile.',
  },
  {
    icon: '03',
    title: 'Location-based discovery',
    description: 'Find care options around the places that work for you and your horse.',
  },
  {
    icon: '04',
    title: 'Secure member accounts',
    description: 'Keep your member experience and care-seeking activity in a secure account.',
  },
  {
    icon: '05',
    title: 'Provider profiles',
    description: 'Explore a dedicated view of each doctor, clinic, or hospital in the network.',
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
