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
import { HomeFooter } from '@/components/public/home-v2/HomeFooter';
import { HomeHero } from '@/components/public/home-v2/HomeHero';
import { FindCareTags } from '@/components/public/home-v2/FindCareTags';
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
import ownerPortrait from '@/components/public/home-v2/media/owner-portrait.jpg';

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
  const horseOwner = member && (user?.roles?.length ? user.roles : [user?.role]).includes('horse_owner');
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
        </section>

        <section className={styles.steps} id="how-it-works" aria-labelledby="steps-heading">
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionKicker}>How it works</p>
              <h2 id="steps-heading">Four quiet steps.</h2>
            </div>
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
              <p>From the ambulatory vet who knows your yard to the hospital with a surgical suite — all verified, all searchable.</p>
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
            <div className={styles.radiusCard}>
              <span className={styles.radiusEyebrow}>A care radius</span>
              <div className={styles.radiusDiagram} role="img" aria-label="Illustrative stable and provider within a care radius, not live results">
                <span className={styles.radiusStable}>Your stable</span>
                <span className={styles.radiusProvider}>Care provider</span>
                <i className={styles.radiusStableDot} />
                <i className={styles.radiusProviderDot} />
              </div>
              <span className={styles.radiusCaption}>Illustrative only · not live results</span>
            </div>
            <a className={styles.imageNote} href="https://unsplash.com/@weareambitious" target="_blank" rel="noreferrer">Photo by Ambitious Studio* | Rick Barrett on Unsplash</a>
          </div>
          <div className={styles.findCopy}>
            <p className={styles.sectionKicker}>Find equine care</p>
            <h2 id="find-heading">Care that actually reaches your stable.</h2>
            <p>Explore veterinary professionals, clinics and hospitals. See the care they share on their profiles, including whether a provider offers stable visits.</p>
            <FindCareTags />
            <p className={styles.findMemberNote}>
              <svg aria-hidden="true" viewBox="0 0 20 20"><rect x="4.5" y="8.5" width="11" height="8" rx="1.5" /><path d="M7 8.5V6a3 3 0 0 1 6 0v2.5" /></svg>
              <span><strong>Members only.</strong> Provider profiles, contact details and reviews are available to members. Street addresses are not shown publicly; ask providers about their location and availability.</span>
            </p>
            <Link to={careHref} className={styles.darkButton}>Check all providers <Arrow /></Link>
          </div>
        </section>

        <section className={styles.whySection} id="why" aria-labelledby="why-heading">
          <div className={styles.whyCopy}>
            <p className={styles.sectionKicker}>Why EquiConnected</p>
            <h2 id="why-heading">Built around how equine care <em>really works.</em></h2>
            <p className={styles.whyLead}>Vets travel. Specialists visit for a season. Emergencies happen at 2am. Explore the details providers share, and decide what works for your horse.</p>
            <ul className={styles.whyItems} aria-label="What you can explore on EquiConnected">
              <li className={styles.whyItem}>
                <span className={styles.whyIcon} aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 21s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Z" /><circle cx="12" cy="9" r="2.3" /></svg></span>
                <span><strong>Shared locations</strong>Browse the locations providers list.</span>
              </li>
              <li className={styles.whyItem}>
                <span className={styles.whyIcon} aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.3 2" /></svg></span>
                <span><strong>Provider details</strong>See information shared on each profile.</span>
              </li>
              <li className={styles.whyItem}>
                <span className={styles.whyIcon} aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4.5 12h3l2-5 4 10 2-5h4" /><circle cx="12" cy="12" r="9" /></svg></span>
                <span><strong>Specialties</strong>Explore the areas of care they list.</span>
              </li>
              <li className={styles.whyItem}>
                <span className={styles.whyIcon} aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3.5 18.5h17M5 18.5V10l7-5 7 5v8.5M9 18.5v-5h6v5" /></svg></span>
                <span><strong>Stable visits</strong>Check whether stable visits are offered.</span>
              </li>
              <li className={styles.whyItem}>
                <span className={styles.whyIcon} aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 3.5v17M5 7h14M7.5 7l-4 7h8l-4-7Zm9 0-4 7h8l-4-7Z" /></svg></span>
                <span><strong>Emergency services</strong>See when providers list them; confirm availability directly.</span>
              </li>
              <li className={styles.whyItem}>
                <span className={styles.whyIcon} aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5.5h10M9 3.5v2m3 0c-.5 4-3.5 7-7 9m1-6c1 2.5 3.5 4.7 6 5.5M15 19l3-8 3 8m-5-2h4" /></svg></span>
                <span><strong>Languages</strong>Ask providers which languages they speak.</span>
              </li>
              <li className={styles.whyItem}>
                <span className={styles.whyIcon} aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3Z" /></svg></span>
                <span><strong>Member reviews</strong>Read reviews when they’re available.</span>
              </li>
              <li className={styles.whyItem}>
                <span className={styles.whyIcon} aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><path d="M3.8 12h16.4M12 3.5c2 2.2 3 5.1 3 8.5s-1 6.3-3 8.5c-2-2.2-3-5.1-3-8.5s1-6.3 3-8.5Z" /></svg></span>
                <span><strong>Visiting care</strong>Ask providers about travel and availability.</span>
              </li>
            </ul>
          </div>
          <figure className={styles.whyVisual}>
            <img className={styles.whyImage} src={whyPhoto} alt="A horse in a bright, close-up black-and-white portrait" loading="lazy" />
            <figcaption className={styles.whyCredit}>Photo by Mahmoud Ayad on Unsplash</figcaption>
          </figure>
        </section>

        <section className={styles.ownersSection} id="owners" aria-labelledby="owners-heading">
          <div className={styles.ownersCollage}>
            <img className={styles.ownerMain} src={ownerPortrait} alt="A horse owner standing close beside a chestnut horse" loading="lazy" />
            <img className={styles.ownerDetail} src={ownerPhoto} alt="Close-up of a horse's eye" loading="lazy" />
            <div className={styles.ownerProfileMotif} aria-label="Illustrative horse profile, not a member record">
              <span className={styles.ownerMotifLabel}>Horse profile · illustration</span>
              <strong>Your horse</strong>
              <span>Breed · registration · microchip</span>
              <span className={styles.ownerMotifTag}>Details you choose to add</span>
            </div>
            <div className={styles.ownerCredits}>
              <a href="https://unsplash.com/@ourselp" target="_blank" rel="noreferrer">Owner &amp; horse · Philippe Oursel / Unsplash</a>
              <a href="https://unsplash.com/@glencarrie" target="_blank" rel="noreferrer">Horse detail · Glen Carrie / Unsplash</a>
            </div>
          </div>
          <div className={styles.ownersCopy}>
            <p className={styles.sectionKicker}>For horse owners &amp; riders</p>
            <h2 id="owners-heading">Your horses, known by heart — and on file.</h2>
            <p>Keep each horse’s essentials together in your member profile. Browse provider information and save the ones you want to revisit.</p>
            <ol className={styles.ownerList}>
              <li><span aria-hidden="true">1</span> Create your member profile</li>
              <li><span aria-hidden="true">2</span> Add your horses</li>
              <li><span aria-hidden="true">3</span> Include optional breed details</li>
              <li><span aria-hidden="true">4</span> Add registration and microchip numbers if you have them</li>
              <li><span aria-hidden="true">5</span> Browse provider-shared information</li>
              <li><span aria-hidden="true">6</span> Save providers to revisit later</li>
            </ol>
            <Link to={horseOwner ? '/profile?section=horses' : member ? '/profile' : '/signup'} className={styles.ownerAction}>
              {horseOwner ? 'Your horses' : member ? 'View your profile' : 'Create your account'} <Arrow />
            </Link>
          </div>
        </section>

        <section className={styles.providerSection} id="providers" aria-labelledby="provider-heading">
          <div className={styles.providerCopy}>
            <p className={styles.sectionKicker}>For veterinary professionals</p>
            <h2 id="provider-heading">A profile worthy of the work <em>you do.</em></h2>
            <p>Introduce your practice to horse owners, riders and stable teams. Share your specializations, and add languages and services where relevant so people can learn more about your work.</p>
            <ul className={styles.providerFeatures} aria-label="Profile details and services">
              <li>Specializations</li>
              <li>Languages</li>
              <li>Stable visits</li>
              <li>Travel radius, if you offer stable visits</li>
              <li>Emergency services</li>
            </ul>
            <Link to="/provider/signup" className={styles.darkButton}>Register as a provider <Arrow /></Link>
          </div>
          <figure className={styles.providerVisual}>
            <img src={vetPhoto} alt="A horse resting its head beside the person caring for it" loading="lazy" />
            <figcaption>For the people behind equine care · Photo by Kirsten LaChance</figcaption>
            <div className={styles.providerPreview} role="group" aria-label="Illustrative profile preview, not an actual provider listing">
              <span className={styles.providerPreviewEyebrow}>Illustrative profile preview</span>
              <span className={styles.providerPreviewMark} aria-hidden="true">EC</span>
              <strong>Provider profile</strong>
              <span>Practice name</span>
              <span>Specializations · Languages</span>
              <span className={styles.previewNote}>Details are shared by each provider</span>
            </div>
          </figure>
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
          </div>
          <div className={styles.editorialBody}>
            <div className={styles.editorialThought}>
              <span className={styles.editorialRule} aria-hidden="true" />
              <p className={styles.editorialStatement}>A little more context. A conversation that starts in the right place.</p>
              <p className={styles.editorialSupport}>When someone has shared a real experience, it can help you know what to ask next.</p>
            </div>
            <aside className={styles.editorialCard} aria-label="How reviews appear">
              <p className={styles.editorialCardLabel}>A note on feedback</p>
              <h3>Only what’s really there.</h3>
              <p>Reviews and ratings appear on provider profiles only when real member feedback is available. Open a profile to find it alongside the information the provider shares.</p>
              <Link to={careHref} className={styles.textLink}>Browse provider profiles <Arrow /></Link>
            </aside>
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
