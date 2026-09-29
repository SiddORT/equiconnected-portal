/**
 * Public EquiConnected homepage — editorial, horse-first storytelling.
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { hasMemberRole } from '@/features/member/memberAccess';
import { extractErrorMessage } from '@/api/client';
import { recordPublicVisit, registerSubscriber } from '@/api/public';
import { systemCalendarDate, useTimeSettings } from '@/app/TimeSettingsContext';
import { CareNearYou } from '@/components/public/CareNearYou';
import { HomeFooter } from '@/components/public/home-v2/HomeFooter';
import { HomeHero } from '@/components/public/home-v2/HomeHero';
import type { SubscriberRegistrationType } from '@/types';
import styles from './PublicPage.module.css';

const REGISTRATION_TYPES: Array<{ value: SubscriberRegistrationType; label: string }> = [
  { value: 'HORSE_OWNER', label: 'Horse owner' },
  { value: 'STABLE_MANAGER', label: 'Stable manager' },
  { value: 'VET', label: 'Veterinary professional' },
  { value: 'CLINIC', label: 'Clinic' },
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'OTHER', label: 'Other' },
];

function Arrow() {
  return <span className={styles.arrow} aria-hidden="true">↗</span>;
}

export function PublicPage() {
  const { isAuthenticated, isLoading: authLoading, user, logout } = useAuth();
  const member = !authLoading && isAuthenticated && hasMemberRole(user);
  const { settings, isLoading: settingsLoading, error: settingsError } = useTimeSettings();
  const [menuOpen, setMenuOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [email, setEmail] = useState('');
  const [registrationType, setRegistrationType] = useState<SubscriberRegistrationType | ''>('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [roleError, setRoleError] = useState('');
  const [formError, setFormError] = useState('');
  const careHref = member ? '/providers' : '/signup';
  const greeting = user?.first_name?.trim() || user?.full_name?.trim() || 'Member';

  useEffect(() => {
    if (settingsLoading || settingsError) return;
    const storageKey = 'equiconnected-public-visit-date';
    try {
      const today = systemCalendarDate(new Date(), settings.timezone);
      if (window.localStorage.getItem(storageKey) === today) return;
      window.localStorage.setItem(storageKey, today);
      void recordPublicVisit().catch(() => window.localStorage.removeItem(storageKey));
    } catch {
      // Visit tracking is best-effort when browser storage is unavailable.
      void recordPublicVisit().catch(() => undefined);
    }
  }, [settings.timezone, settingsError, settingsLoading]);

  useEffect(() => {
    let frame = 0;
    const revealHashTarget = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const id = decodeURIComponent(window.location.hash.slice(1));
        if (!id) return;
        const target = document.getElementById(id);
        if (!target) return;
        target.scrollIntoView({ block: 'start' });
        const heading = target.querySelector<HTMLElement>('h1, h2');
        if (!heading) return;
        const hadTabIndex = heading.hasAttribute('tabindex');
        if (!hadTabIndex) heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
        if (!hadTabIndex) heading.addEventListener('blur', () => heading.removeAttribute('tabindex'), { once: true });
      });
    };
    revealHashTarget();
    window.addEventListener('hashchange', revealHashTarget);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('hashchange', revealHashTarget);
    };
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);

  async function handleNotify(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!registrationType) {
      setRoleError('Please choose how you would like to register.');
      return;
    }
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setEmailError('Please enter a valid email address.');
      return;
    }
    setRoleError('');
    setEmailError('');
    setFormError('');
    setSubmitting(true);
    try {
      await registerSubscriber({ email: email.trim(), registration_type: registrationType });
      setSubmitted(true);
    } catch (error) {
      setFormError(extractErrorMessage(error, 'We could not save your registration. Please try again shortly.'));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
      setMenuOpen(false);
    } finally {
      setLoggingOut(false);
    }
  }

  function closeMenu() {
    setMenuOpen(false);
  }

  return (
    <div className={styles.page}>
      <a className={styles.skipLink} href="#main-content">Skip to content</a>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link to="/" className={styles.brand} aria-label="EquiConnected home">
            <img src="/equiconnected-logo.png" alt="" aria-hidden="true" />
          </Link>
          {member && <span className={styles.greeting}>Hi, {greeting}</span>}
          <button
            className={`${styles.menuToggle} ${menuOpen ? styles.menuToggleOpen : ''}`}
            type="button"
            aria-expanded={menuOpen}
            aria-controls="home-navigation"
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? 'Close' : 'Menu'}
            <span className={styles.menuGlyph} aria-hidden="true"><i /><i /></span>
          </button>
          <nav id="home-navigation" className={`${styles.navigation} ${menuOpen ? styles.navigationOpen : ''}`} aria-label="Primary navigation">
            <a href="/#care" onClick={closeMenu}>Find care</a>
            <a href="/#owners" onClick={closeMenu}>Owners &amp; stable teams</a>
            <a href="/#providers" onClick={closeMenu}>For providers</a>
            {member ? (
              <>
                <Link to="/profile" onClick={closeMenu}>Profile</Link>
                <button type="button" className={styles.signOut} onClick={() => void handleLogout()} disabled={loggingOut}>
                  {loggingOut ? 'Signing out…' : 'Sign out'}
                </button>
              </>
            ) : (
              <Link to="/login" onClick={closeMenu}>Sign in</Link>
            )}
            <Link className={styles.navJoin} to={member ? '/providers' : '/signup'} onClick={closeMenu}>
              {member ? 'Directory' : 'Join EquiConnected'}
            </Link>
          </nav>
        </div>
      </header>

      <main id="main-content">
        <HomeHero careHref={careHref} />

        <section className={styles.intro} id="care" aria-labelledby="intro-heading">
          <div className={styles.introIndex}>01 <span>—</span> A connected care network</div>
          <div className={styles.introBody}>
            <p className={styles.sectionKicker}>For the people who care for horses</p>
            <h2 id="intro-heading">Good care begins with knowing <em>where to look.</em></h2>
            <p>EquiConnected brings equine providers and the people seeking care into one considered place. Explore by care category and location, then decide what feels right for your horse.</p>
            <Link to={careHref} className={styles.textLink}>Explore the provider directory <Arrow /></Link>
          </div>
          <div className={styles.introSeal} aria-hidden="true"><span>EC</span><i /></div>
        </section>

        <section className={styles.steps} aria-labelledby="steps-heading">
          <div className={styles.sectionHead}>
            <div><p className={styles.sectionKicker}>A simpler way forward</p><h2 id="steps-heading">Four quiet steps.</h2></div>
            <p>From the first search to a more informed next step.</p>
          </div>
          <ol className={styles.stepList}>
            {[
              ['01', 'Create your account', 'Join as a horse owner or stable manager to access provider profiles.'],
              ['02', 'Explore care', 'Browse the directory and discover providers by category and location.'],
              ['03', 'Compare the details', 'Review available profile information to understand each provider.'],
              ['04', 'Make your connection', 'Choose who to contact and continue the conversation directly.'],
            ].map(([number, title, description]) => (
              <li key={number} className={styles.step}>
                <span className={styles.stepNo}>{number}</span>
                <h3>{title}</h3>
                <p>{description}</p>
                <span className={styles.stepRule} />
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.careSection} aria-labelledby="care-heading">
          <div className={styles.careHeading}>
            <p className={styles.sectionKicker}>Find your starting point</p>
            <h2 id="care-heading">Different needs.<br /><em>One place to look.</em></h2>
            <p>Discover equine care providers by the kind of practice you’re looking for.</p>
          </div>
          <div className={styles.careCards}>
            {[
              ['I', 'Veterinary professionals', 'Explore independent and practice-based veterinary providers.'],
              ['II', 'Clinics', 'Find equine clinics and the care information they share.'],
              ['III', 'Hospitals', 'Explore equine hospitals and their available profile details.'],
            ].map(([number, title, description]) => (
              <article className={styles.careCard} key={number}>
                <span className={styles.careNumber}>{number}</span>
                <div className={styles.careCardBottom}>
                  <h3>{title}</h3>
                  <p>{description}</p>
                  <Link to={careHref} aria-label={`Explore ${title}`} className={styles.cardLink}>Explore directory <Arrow /></Link>
                </div>
              </article>
            ))}
          </div>
          <p className={styles.careFootnote}>Directory details vary by provider. Membership is required to view provider profiles.</p>
        </section>

        <div className={styles.careMap}>
          <CareNearYou theme="brown" />
        </div>

        <section className={styles.darkStory} id="owners" aria-labelledby="owners-heading">
          <div className={styles.storyPhoto}>
            <img src="/home-v2-hero.jpg" alt="A horse in open pasture, seen in the evening light" loading="lazy" />
            <span className={styles.storyCaption}>Care is personal. Finding it should feel clearer.</span>
          </div>
          <div className={styles.storyCopy}>
            <p className={styles.sectionKicker}>For owners &amp; stable teams</p>
            <h2 id="owners-heading">The whole picture starts with <em>your horse.</em></h2>
            <p>Whether you care for one horse or manage a stable, EquiConnected gives you a place to begin your search and learn about providers in your area.</p>
            <ul>
              <li><span>01</span> Browse a dedicated equine provider directory</li>
              <li><span>02</span> Find information by provider type and location</li>
              <li><span>03</span> Keep your next step in your hands</li>
            </ul>
            <Link to={careHref} className={styles.goldButton}>Explore care <Arrow /></Link>
          </div>
        </section>

        <section className={styles.providerSection} id="providers" aria-labelledby="provider-heading">
          <div className={styles.providerTopline}><span>For equine care providers</span><span>EquiConnected / 02</span></div>
          <div className={styles.providerGrid}>
            <h2 id="provider-heading">A profile that helps the right people <em>find you.</em></h2>
            <div>
              <p>Introduce your practice to horse owners and stable teams looking for equine care. Share the details that help people understand your services and how to reach you.</p>
              <Link to="/provider/signup" className={styles.darkButton}>Create a provider account <Arrow /></Link>
            </div>
          </div>
          <div className={styles.providerTypes}><span>Veterinary professionals</span><span>Clinics</span><span>Hospitals</span></div>
        </section>

        <section className={styles.comingSoon} aria-label="More from EquiConnected">
          <span className={styles.comingMark} aria-hidden="true">EC</span>
          <p className={styles.sectionKicker}>A network that grows with you</p>
          <h2>More thoughtful connections<br />are <em>on the way.</em></h2>
          <p>We’re continuing to build tools for the people who care for horses. Join the list for occasional EquiConnected updates.</p>
          {submitted ? (
            <div className={styles.successMessage} role="status"><strong>You’re on the list.</strong> The EquiConnected team will be in touch soon.</div>
          ) : (
            <form className={styles.subscribeForm} onSubmit={(event) => void handleNotify(event)} noValidate aria-label="Get EquiConnected updates">
              <label>
                <span>Your role</span>
                <select value={registrationType} onChange={(event) => { setRegistrationType(event.target.value as SubscriberRegistrationType | ''); setRoleError(''); setFormError(''); }} aria-invalid={!!roleError} aria-describedby={roleError ? 'role-error' : undefined} required disabled={submitting}>
                  <option value="">Choose a role</option>
                  {REGISTRATION_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </label>
              <label>
                <span>Email address</span>
                <input type="email" value={email} onChange={(event) => { setEmail(event.target.value); setEmailError(''); setFormError(''); }} placeholder="you@example.com" autoComplete="email" aria-invalid={!!emailError} aria-describedby={emailError ? 'email-error' : undefined} required disabled={submitting} />
              </label>
              <button type="submit" disabled={submitting}>{submitting ? 'Submitting…' : 'Keep me posted'} <Arrow /></button>
              {roleError && <p id="role-error" className={styles.formError} role="alert">{roleError}</p>}
              {emailError && <p id="email-error" className={styles.formError} role="alert">{emailError}</p>}
              {formError && <p className={styles.formError} role="alert">{formError}</p>}
            </form>
          )}
        </section>
      </main>

      <HomeFooter member={member} careHref={careHref} />
    </div>
  );
}