/**
 * Public EquiConnected homepage — editorial, horse-first storytelling.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { hasMemberRole } from '@/features/member/memberAccess';
import { extractErrorMessage } from '@/api/client';
import { recordPublicVisit, registerSubscriber } from '@/api/public';
import { systemCalendarDate, useTimeSettings } from '@/app/TimeSettingsContext';
import { CareNearYou } from '@/components/public/CareNearYou';
import { HomeFooter } from '@/components/public/home-v2/HomeFooter';
import { HomeHero } from '@/components/public/home-v2/HomeHero';
import categoryVet from '@/components/public/home-v2/media/category-vet.jpg';
import categoryClinic from '@/components/public/home-v2/media/category-clinic.jpg';
import categoryHospital from '@/components/public/home-v2/media/category-hospital.jpg';
import findCarePhoto from '@/components/public/home-v2/media/find-care.jpg';
import whyPhoto from '@/components/public/home-v2/media/why-care.jpg';
import ownerPhoto from '@/components/public/home-v2/media/owner-horse.jpg';
import vetPhoto from '@/components/public/home-v2/media/vet-care.jpg';
import visitingPhoto from '@/components/public/home-v2/media/visiting-specialist.jpg';
import emergencyPhoto from '@/components/public/home-v2/media/emergency-care.jpg';
import finalPhoto from '@/components/public/home-v2/media/final-horses.jpg';
import styles from '@/components/public/home-v2/HomeV2.module.css';
import type { SubscriberRegistrationType } from '@/types';

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
  const [headerScrolled, setHeaderScrolled] = useState(false);
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
    const updateHeader = () => setHeaderScrolled(window.scrollY > 28);
    updateHeader();
    window.addEventListener('scroll', updateHeader, { passive: true });
    return () => window.removeEventListener('scroll', updateHeader);
  }, []);

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
      <header className={`${styles.header} ${headerScrolled ? styles.headerScrolled : ''}`}>
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
            <a href="/#find" onClick={closeMenu}>Find a provider</a>
            <a href="/#owners" onClick={closeMenu}>Owners &amp; riders</a>
            <a href="/#providers" onClick={closeMenu}>For vets</a>
            <a href="/#visiting" onClick={closeMenu}>Visiting specialists</a>
            <a href="/#emergency" onClick={closeMenu}>Emergency</a>
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
        <HomeHero careHref={careHref} member={member} />

        <section className={styles.intro} id="care" aria-labelledby="intro-heading">
          <h2 id="intro-heading">
            Every horse deserves care from someone who knows horses.
            {' '}<span className={styles.inlinePhoto}><img src="/home-v2/statement-detail-1.jpg" alt="" /></span>
            {' '}EquiConnected brings together the vets, clinics and hospitals of the Emirates
            {' '}<span className={styles.inlinePhoto}><img src="/home-v2/statement-detail-2.jpg" alt="" /></span>
            {' '}<em>so the right one is always within reach.</em>
          </h2>
          <div className={styles.introFoot}>
            <p>A starting point for horse owners, riders and stable teams to learn about equine care providers and the information they share.</p>
            <a className={styles.textLink} href="#how-it-works">A clearer first step <Arrow /></a>
          </div>
        </section>

        <section className={styles.steps} id="how-it-works" aria-labelledby="steps-heading">
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionKicker}>How it works</p>
              <h2 id="steps-heading">Four quiet steps.</h2>
            </div>
            <p>Start with what your horse needs. Explore the network at your own pace.</p>
          </div>
          <ol className={styles.stepList}>
            {[
              ['One', 'Tell us what you need', 'Start with the kind of equine care you’re looking for.', 'note'],
              ['Two', 'Choose a place to look', 'Explore care by provider type and shared location.', 'pin'],
              ['Three', 'Discover providers', 'Browse profiles and the information providers share.', 'search'],
              ['Four', 'Make your connection', 'Contact the provider directly to discuss your needs.', 'link'],
            ].map(([number, title, description, icon]) => (
              <li key={number} className={styles.step}>
                <div className={styles.stepTrack}>
                  <span className={styles.stepIcon} aria-hidden="true">
                    {icon === 'note' && <svg viewBox="0 0 24 24"><rect x="6" y="4.5" width="12" height="16" rx="1.5" /><path d="M9 8h6M9 12h6M9 16h4" /></svg>}
                    {icon === 'pin' && <svg viewBox="0 0 24 24"><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2.2" /></svg>}
                    {icon === 'search' && <svg viewBox="0 0 24 24"><circle cx="10.8" cy="10.8" r="6.2" /><path d="m15.4 15.4 4.1 4.1" /></svg>}
                    {icon === 'link' && <svg viewBox="0 0 24 24"><path d="m9.5 14.5 5-5" /><path d="M8 16 6 18a3 3 0 0 1-4-4l4-4a3 3 0 0 1 4 0m4-2 2-2a3 3 0 0 1 4 4l-4 4a3 3 0 0 1-4 0" /></svg>}
                  </span>
                  <span className={styles.stepConnector} aria-hidden="true" />
                </div>
                <span className={styles.stepNo}>{number}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.categories} aria-labelledby="categories-heading">
          <div className={styles.categoryWrap}>
            <div className={styles.categoryHeading}>
              <p className={styles.sectionKicker}>Who you’ll find</p>
              <h2 id="categories-heading">Three kinds of care.<br /><em>One place to look.</em></h2>
              <p>From independent veterinary professionals to clinics and hospitals, browse by practice type. Services vary by provider.</p>
            </div>
            <div className={styles.categoryGrid}>
              {[
                { number: 'i', type: 'Veterinary professional', title: 'Vets', description: 'Independent and ambulatory vets — some visit your stable within their service area.', services: ['Health checks', 'Lameness exams', 'Dentistry'], image: categoryVet, credit: 'Photo by Daniel Bonilla on Unsplash' },
                { number: 'ii', type: 'Clinic', title: 'Clinics', description: 'Equine clinics may provide diagnostics and outpatient treatment when your horse needs to travel.', services: ['X-ray & ultrasound', 'Outpatient', 'Rehabilitation'], image: categoryClinic, credit: 'Photo by Mathias Reding on Unsplash' },
                { number: 'iii', type: 'Hospital', title: 'Hospitals', description: 'Equine hospitals may provide surgery, intensive care and advanced imaging.', services: ['Surgery', 'Intensive care', 'MRI & CT'], image: categoryHospital, credit: 'Photo by D. Gibson on Unsplash' },
              ].map(({ number, type, title, description, services, image, credit }) => (
                <article className={styles.categoryCard} key={number}>
                  <Link to={careHref} className={styles.categoryLink} aria-label={`Explore ${title} in the directory`}>
                    <div className={styles.categoryPhoto}>
                      <img src={image} alt="" loading="lazy" />
                      <span className={styles.categoryCredit}>{credit}</span>
                    </div>
                    <div className={styles.categoryCaption}><span>{number}</span> {type}</div>
                    <h3>{title}</h3>
                    <p>{description}</p>
                    <ul className={styles.categoryServices} aria-label="Example services; offerings vary by provider">
                      {services.map((service) => <li key={service}>{service}</li>)}
                    </ul>
                  </Link>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className={styles.findSection} id="find" aria-labelledby="find-heading">
          <div className={styles.findImage}>
            <img src={findCarePhoto} alt="A horse standing in a sunlit stable yard" loading="lazy" />
            <span className={styles.imageNote}>
              <span>A clear place to begin exploring equine care.</span>
              <a href="https://unsplash.com/@weareambitious" target="_blank" rel="noreferrer">Photo by Ambitious Studio* | Rick Barrett</a>
            </span>
          </div>
          <div className={styles.findCopy}>
            <p className={styles.sectionKicker}>Find equine care</p>
            <h2 id="find-heading">Care that starts with <em>your horse.</em></h2>
            <p>Explore providers by care type and location, then review the profile information they share. Directory details vary by provider, and full profiles are available to members.</p>
            <ul className={styles.findPoints}>
              <li><span aria-hidden="true">↗</span> Independent veterinary professionals</li>
              <li><span aria-hidden="true">↗</span> Clinics and hospitals</li>
              <li><span aria-hidden="true">↗</span> Provider-shared locations</li>
              <li><span aria-hidden="true">↗</span> Details to guide your next step</li>
            </ul>
            <Link to={careHref} className={styles.darkButton}>Explore the directory <Arrow /></Link>
          </div>
        </section>

        <div className={styles.mapShell}>
          <CareNearYou theme="brown" />
        </div>

        <section className={styles.whySection} aria-labelledby="why-heading">
          <img className={styles.whyImage} src={whyPhoto} alt="Close portrait of a horse in soft outdoor light" loading="lazy" />
          <div className={styles.whyShade} />
          <div className={styles.whyCopy}>
            <p className={styles.sectionKicker}>Why EquiConnected</p>
            <h2 id="why-heading">Built around how equine care <em>really works.</em></h2>
            <p>Finding care can involve more than a name in a list. Explore the information providers share, and decide what feels right for your horse.</p>
            <div className={styles.whyItems}>
              <div className={styles.whyItem}><b>01</b><span><strong>Equine, by focus</strong>Made for people looking for horse care.</span></div>
              <div className={styles.whyItem}><b>02</b><span><strong>Useful details</strong>Provider profiles bring shared information together.</span></div>
              <div className={styles.whyItem}><b>03</b><span><strong>Your next step</strong>Connect directly with providers to discuss care.</span></div>
            </div>
          </div>
        </section>

        <section className={styles.ownersSection} id="owners" aria-labelledby="owners-heading">
          <div className={styles.ownersCollage}>
            <img className={styles.ownerMain} src="/home-v2-hero.jpg" alt="White horse moving through a green pasture" loading="lazy" />
            <img className={styles.ownerDetail} src={ownerPhoto} alt="Close detail of a horse" loading="lazy" />
            <span className={styles.ownerIndex}>For the ones who know them best</span>
            <a className={styles.ownerCredit} href="https://unsplash.com/@glencarrie" target="_blank" rel="noreferrer">Horse detail · Glen Carrie / Unsplash</a>
          </div>
          <div className={styles.ownersCopy}>
            <p className={styles.sectionKicker}>For horse owners &amp; riders</p>
            <h2 id="owners-heading">Your horse is at the heart of <em>every decision.</em></h2>
            <p>A member account gives you access to provider profiles and the details they share, so you can find the care that feels right for your horse.</p>
            <ul className={styles.ownerList}>
              <li><span>01</span> Explore an equine-focused provider directory</li>
              <li><span>02</span> See member-only profile information</li>
              <li><span>03</span> Choose who to contact, and when</li>
            </ul>
            <Link to={member ? '/providers' : '/signup'} className={styles.darkButton}>{member ? 'Open provider directory' : 'Create your account'} <Arrow /></Link>
          </div>
        </section>

        <section className={styles.providerSection} id="providers" aria-labelledby="provider-heading">
          <div className={styles.providerVisual}>
            <img src={vetPhoto} alt="Veterinary professional caring for a horse" loading="lazy" />
            <span>For the people behind equine care · Photo by Kirsten LaChance</span>
          </div>
          <div className={styles.providerCopy}>
            <p className={styles.sectionKicker}>For veterinary professionals</p>
            <h2 id="provider-heading">A profile worthy of the work <em>you do.</em></h2>
            <p>Introduce your practice to horse owners, riders and stable teams. Share your qualifications, areas of care and contact information so people can learn more about your services.</p>
            <div className={styles.providerTypes}><span>Veterinary professionals</span><span>Clinics</span><span>Hospitals</span></div>
            <Link to="/provider/signup" className={styles.darkButton}>Register as a provider <Arrow /></Link>
          </div>
        </section>

        <section className={styles.visiting} id="visiting" aria-labelledby="visiting-heading">
          <img src={visitingPhoto} alt="Horse and rider moving across an open landscape" loading="lazy" />
          <div className={styles.visitingCopy}>
            <p className={styles.sectionKicker}>Visiting specialists</p>
            <h2 id="visiting-heading">Expertise that’s here <em>for a season.</em></h2>
            <p>Some veterinary professionals travel to care for horses. Explore the services and locations providers share, then contact them directly to ask about availability.</p>
            <Link to={careHref} className={styles.lightButton}>Explore provider profiles <Arrow /></Link>
          </div>
          <span className={styles.visitingCredit}>Photo by Filip Eliasson on Unsplash</span>
        </section>

        <section className={styles.editorial} aria-labelledby="editorial-heading">
          <div className={styles.editorialIntro}>
            <p className={styles.sectionKicker}>Ratings &amp; reviews</p>
            <h2 id="editorial-heading">In their words.</h2>
            <p>Provider profile reviews are shared by members. They appear when available, alongside the rest of a provider’s profile details.</p>
          </div>
          <div className={styles.editorialQuote}>
            <p className={styles.editorialStatement}>Real experiences can help you start a more informed conversation.</p>
            <p>Reviews and ratings appear only where real member feedback is available.</p>
            <Link to={careHref} className={styles.textLink}>Browse provider profiles <Arrow /></Link>
          </div>
        </section>

        <section className={styles.emergency} id="emergency" aria-labelledby="emergency-heading">
          <div className={styles.emergencyCopy}>
            <p className={styles.sectionKicker}>Emergency care</p>
            <h2 id="emergency-heading">When it can’t wait, know where to start.</h2>
            <p>Some provider profiles include emergency service information. Review the details shared by a provider and contact them directly to confirm availability.</p>
            <Link to={careHref} className={styles.darkButton}>Explore care providers <Arrow /></Link>
            <span className={styles.emergencyNote}>EquiConnected is a directory, not an emergency dispatch service. If a horse needs urgent care, contact a local veterinary provider.</span>
          </div>
          <div className={styles.emergencyVisual}>
            <img src={emergencyPhoto} alt="Calm horse looking out from a stable" loading="lazy" />
            <span className={styles.emergencyLabel}>Provider-shared emergency details</span>
            <a className={styles.emergencyCredit} href="https://unsplash.com/@kellyforrister" target="_blank" rel="noreferrer">Photo by Kelly Forrister</a>
          </div>
        </section>

        <section className={styles.finalCta} id="join" aria-labelledby="final-heading">
          <img src={finalPhoto} alt="" loading="lazy" />
          <a className={styles.finalCredit} href="https://unsplash.com/@itfeelslikefilm" target="_blank" rel="noreferrer">Photo by Janko Ferlič on Unsplash</a>
          <div className={styles.finalInner}>
            <p className={styles.sectionKicker}>For every horse, and everyone who cares for them</p>
            <h2 id="final-heading">Find the right care<br />for <em>your horse.</em></h2>
            <p>Start exploring EquiConnected. Provider profiles are available to members.</p>
            <div className={styles.finalActions}>
              <Link to={careHref} className={styles.goldButton}>Find a provider <Arrow /></Link>
              <Link to={member ? '/providers' : '/signup'} className={styles.ghostButton}>
                {member ? 'Open directory' : 'Join EquiConnected'}
              </Link>
            </div>
          </div>
        </section>

        <section className={styles.comingSoon} aria-label="Get EquiConnected updates">
          <p className={styles.sectionKicker}>A network that grows with you</p>
          <h2>Stay close to what’s<br />happening <em>next.</em></h2>
          <p>Join the list for occasional EquiConnected updates for people who care for horses.</p>
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