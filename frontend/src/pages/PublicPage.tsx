/**
 * Public landing page for the EquiConnected portal.
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { recordPublicVisit, registerSubscriber } from '@/api/public';
import { systemCalendarDate, useTimeSettings } from '@/app/TimeSettingsContext';
import { HeroImageSlider } from '@/components/public/HeroImageSlider';
import { HowItWorksScroll } from '@/components/public/HowItWorksScroll';
import { SpecializationsScroll } from '@/components/public/SpecializationsScroll';
import { CareNearYou } from '@/components/public/CareNearYou';
import { WhyEquiConnected } from '@/components/public/WhyEquiConnected';
import { Footer } from '@/components/layout/Footer';
import { usePublicPageAnimations } from '@/hooks/usePublicPageAnimations';
import type { SubscriberRegistrationType } from '@/types';
import styles from './PublicPage.module.css';

export function PublicPage() {
  const pageRef = useRef<HTMLDivElement>(null);
  const { settings, isLoading: settingsLoading, error: settingsError } = useTimeSettings();
  const [email, setEmail] = useState('');
  const [registrationType, setRegistrationType] = useState<SubscriberRegistrationType | ''>('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [registrationTypeError, setRegistrationTypeError] = useState('');
  const [formError, setFormError] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);

  usePublicPageAnimations(pageRef);

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

  function closeMenu() {
    setMenuOpen(false);
  }

  return (
    <div className={styles.page} ref={pageRef}>
      {/* ── Background decorative elements ──────────────────────── */}
      <div className={styles.bgGlow} aria-hidden="true" />

      <main className={styles.main} id="main-content">
        {/* ── Logo / Header ────────────────────────────────────── */}
        <header className={styles.header} data-motion-header>
          <Link to="/" className={styles.brand} aria-label="EquiConnected home">
            <img
              src="/equiconnected-logo.png"
              alt=""
              aria-hidden="true"
              className={styles.brandLogo}
            />
          </Link>
          <nav className={`${styles.nav} ${menuOpen ? styles.navOpen : ''}`} aria-label="Primary navigation">
            <button
              type="button"
              className={styles.navToggle}
              aria-expanded={menuOpen}
              aria-controls="primary-navigation-menu"
              onClick={() => setMenuOpen((open) => !open)}
            >
              <span>{menuOpen ? 'Close' : 'Menu'}</span>
              <span className={styles.navToggleIcon} aria-hidden="true">
                <span />
                <span />
              </span>
            </button>
            <div className={styles.navMenu} id="primary-navigation-menu">
              <div className={styles.navLinks}>
                <a href="/#about-us" onClick={closeMenu}>About</a>
                <a href="/#specializations" onClick={closeMenu}>Specializations</a>
                <a href="/#how-it-works" onClick={closeMenu}>Steps</a>
                <a href="/#care-near-you" onClick={closeMenu}>Providers</a>
                <a href="/#why-equiconnected" onClick={closeMenu}>Why us</a>
              </div>
              <div className={styles.navActions}>
                <Link to="/signup" className={styles.navMember} onClick={closeMenu} data-gsap-hover>
                  Register as member
                </Link>
                <Link to="/provider/signup" className={styles.navCta} onClick={closeMenu} data-gsap-hover>
                  Register as provider
                </Link>
              </div>
            </div>
          </nav>
        </header>

        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className={styles.hero} aria-labelledby="hero-heading" data-parallax-trigger>
          <div className={styles.heroContent}>
            <p className={styles.eyebrow} data-hero-item><span className={styles.eyebrowRule} />EquiConnected</p>
            <h1 id="hero-heading" className={styles.heading} data-hero-item>
              Healthcare,{' '}
              <span>Connected Around You.</span>
            </h1>
            <p className={styles.subtitle} data-hero-item>
              Discover doctors, clinics and hospitals based on your specialization, location and care needs.
            </p>
            <div className={styles.ctas} data-hero-item>
              <Link to="/signup" className={styles.primaryCta} data-gsap-hover>
                Find care <span aria-hidden="true">↗</span>
              </Link>
              <Link to="/provider/signup" className={styles.secondaryCta} data-gsap-hover>
                Join as a provider
              </Link>
            </div>
            <p className={styles.trustLine} data-hero-item><span aria-hidden="true" />A clearer path to the right care</p>
            <div className={styles.notifyBlock} data-hero-item>
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
                    <button type="submit" className={styles.notifyBtn} data-gsap-hover disabled={submitting}>
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
          <div className={styles.heroVisual} data-hero-media>
            <HeroImageSlider />
          </div>
        </section>

        <section id="about-us" className={styles.aboutSection} aria-labelledby="about-us-heading" data-about-section>
          <div className={styles.aboutVisual}>
            <img
              className={styles.aboutImage}
              src="/about-equiconnected-transparent.png"
              alt="EquiConnected veterinary team caring for a horse"
              loading="lazy"
              data-about-image
            />
          </div>
          <div className={styles.aboutCopy} data-about-copy>
            <p className={styles.sectionEyebrow}><span aria-hidden="true" />About us</p>
            <h2 id="about-us-heading">
              Care that sees the <em>whole horse.</em>
            </h2>
            <p>
              EquiConnected makes equine healthcare easier to understand and easier to reach.
              We bring trusted doctors, clinics, and hospitals together so horse owners can
              move from concern to confident care.
            </p>
            <p>
              Every connection starts with context: the right specialization, the right location,
              and the right people around your horse.
            </p>
            <div className={styles.aboutFacts}>
              <div>
                <strong>01</strong>
                <span>One connected care network</span>
              </div>
              <div>
                <strong>02</strong>
                <span>Built around the horse</span>
              </div>
            </div>
          </div>
        </section>

        <SpecializationsScroll />
        <HowItWorksScroll />
        <CareNearYou />

        <section id="get-started" className={styles.finalCta} aria-labelledby="final-cta-heading" data-parallax-trigger data-scroll-reveal>
          <div className={styles.finalCtaCopy} data-scroll-reveal>
            <p className={styles.sectionEyebrow}><span aria-hidden="true" />Keep moving forward</p>
            <h2 id="final-cta-heading">Your healthcare network starts here.</h2>
            <p>Find the care you need. Discover providers around you.</p>
            <div className={styles.finalCtaActions}>
              <Link to="/signup" className={styles.finalPrimaryCta} data-gsap-hover>
                Find care <span aria-hidden="true">↗</span>
              </Link>
              <Link to="/provider/signup" className={styles.finalSecondaryCta} data-gsap-hover>
                Join as a provider
              </Link>
            </div>
          </div>
          <div className={styles.finalCtaVisual} aria-hidden="true">
            <img
              className={styles.finalCtaImage}
              src="/hospital1.png"
              alt=""
              data-subtle-parallax
            />
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

        <WhyEquiConnected />

        <section id="provider-join" className={styles.providerSection} aria-labelledby="provider-join-heading" data-scroll-reveal>
          <div className={styles.providerVisual} data-scroll-reveal>
            <img
              className={styles.providerImage}
              src="/provider-cta-equine-care.jpeg"
              alt="Equine veterinarian caring for a chestnut horse in a warm stable"
              loading="lazy"
            />
          </div>
          <div className={styles.providerCopy} data-scroll-reveal>
            <p className={styles.sectionEyebrow}><span aria-hidden="true" />For providers</p>
            <h2 id="provider-join-heading">Grow your presence with EquiConnected.</h2>
            <p>
              Put your practice in front of members looking for thoughtful equine care.
              Share the information that helps people understand where you fit in their
              healthcare journey.
            </p>
            <Link to="/provider/signup" className={styles.providerCta} data-gsap-hover>
              Join as a provider <span aria-hidden="true">↗</span>
            </Link>
            <ul className={styles.providerTypes} aria-label="Provider types" data-scroll-stagger>
              {PROVIDER_TYPES.map((type, index) => (
                <li key={type} className={styles.providerType} data-stagger-item>
                  <span className={styles.providerTypeNumber} aria-hidden="true">0{index + 1}</span>
                  {type}
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}

const PROVIDER_TYPES = ['Doctors', 'Clinics', 'Hospitals'];

const REGISTRATION_TYPES: Array<{ value: SubscriberRegistrationType; label: string }> = [
  { value: 'VET', label: 'Vet' },
  { value: 'HORSE_OWNER', label: 'Horse Owner' },
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'CLINIC', label: 'Clinic' },
  { value: 'STABLE_MANAGER', label: 'Stable Manager' },
  { value: 'OTHER', label: 'Other' },
];
