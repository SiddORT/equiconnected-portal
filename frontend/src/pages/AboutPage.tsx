import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { hasMemberRole } from '@/features/member/memberAccess';
import { AudienceDropdown } from '@/components/public/home-v2/AudienceDropdown';
import { HomeFooter } from '@/components/public/home-v2/HomeFooter';
import heroPhoto from '@/components/public/home-v2/media/final-horses.jpg';
import ownerPhoto from '@/components/public/home-v2/media/owner-portrait.jpg';
import horseDetail from '@/components/public/home-v2/media/owner-horse.jpg';
import storyPhoto from '@/components/public/home-v2/media/why-care.jpg';
import reviewPhoto from '@/components/public/home-v2/media/vet-care.jpg';
import stablePhoto from '@/components/public/home-v2/media/visiting-specialist.jpg';
import vetPhoto from '@/components/public/home-v2/media/category-vet.jpg';
import hospitalPhoto from '@/components/public/home-v2/media/category-hospital.jpg';
import closePhoto from '@/components/public/home-v2/media/emergency-care.jpg';
import homeStyles from '@/components/public/home-v2/HomeV2.module.css';
import styles from './AboutPage.module.css';

const promises = [
  ['01', 'Horse-first care', 'Equine care has its own rhythms, people and practical realities. We keep the horse at the heart of the connection.'],
  ['02', 'Clear information', 'Explore the details providers choose to share, then ask them directly about services, travel and availability.'],
  ['03', 'Privacy by choice', 'Member information stays within the member experience. Public pages introduce the service without exposing private profiles.'],
  ['04', 'Direct connection', 'EquiConnected helps people find one another. Care decisions and arrangements remain between owners and providers.'],
];

const communities = [
  { title: 'Riders & owners', note: 'Keep your horse’s care close, and explore providers who may fit the way you look after them.', image: ownerPhoto, alt: 'A horse owner beside a horse' },
  { title: 'Stable managers', note: 'A clearer starting point when coordinating care across a yard and its horses.', image: stablePhoto, alt: 'A person standing beside a horse' },
  { title: 'Vets', note: 'Share a profile of your equine work, services and the places you travel to.', image: vetPhoto, alt: 'A horse in an outdoor equestrian setting' },
  { title: 'Hospitals & clinics', note: 'Help horse people understand the care and facilities your practice describes.', image: hospitalPhoto, alt: 'A horse and rider in an equestrian arena' },
];

export function AboutPage() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const member = !isLoading && isAuthenticated && hasMemberRole(user);
  const verifiedMember = member && Boolean(user?.is_active && user?.email_verified_at);
  const careHref = verifiedMember ? '/providers' : '/signup';

  useEffect(() => {
    const previousTitle = document.title;
    document.title = 'About EquiConnected | EquiConnected';
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    return () => { document.title = previousTitle; };
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 32);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (document.querySelector('[data-audience-dropdown] [aria-expanded="true"]')) return;
      setMenuOpen(false);
      document.getElementById('about-menu-toggle')?.focus();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);

  const closeMenu = () => setMenuOpen(false);

  return (
    <div className={`${homeStyles.page} ${styles.page}`}>
      <a className={styles.skip} href="#about-main">Skip to content</a>
      <header className={`${styles.header} ${scrolled ? styles.headerScrolled : ''}`}>
        <div className={styles.headerInner}>
          <Link to="/" className={styles.brand} aria-label="EquiConnected home">
            <img src="/equiconnected-logo.png" alt="" aria-hidden="true" />
          </Link>
          <button id="about-menu-toggle" className={styles.menuToggle} type="button" aria-expanded={menuOpen} aria-controls="about-navigation" onClick={() => setMenuOpen((open) => !open)}>
            {menuOpen ? 'Close' : 'Menu'} <span aria-hidden="true" className={styles.menuIcon}><i /><i /></span>
          </button>
          <nav id="about-navigation" className={`${styles.navigation} ${menuOpen ? styles.navigationOpen : ''}`} aria-label="Primary navigation">
            <Link to="/" onClick={closeMenu}>Home</Link>
            <a href="/#find" onClick={closeMenu}>Find care</a>
            <a href="/#owners" onClick={closeMenu}>For horse people</a>
            <a href="/#providers" onClick={closeMenu}>For providers</a>
             {!verifiedMember && <AudienceDropdown action="signin" placement="navigation" onSelect={closeMenu} resetOn={menuOpen} />}
            {verifiedMember
              ? <Link className={styles.navAction} to="/providers" onClick={closeMenu}>Directory</Link>
               : <AudienceDropdown action="join" placement="navigation" onSelect={closeMenu} resetOn={menuOpen} />}
          </nav>
        </div>
      </header>

      <main id="about-main">
        <section className={styles.hero} id="about-hero" aria-labelledby="hero-title">
          <img className={styles.heroImage} src={heroPhoto} alt="" fetchPriority="high" />
          <div className={styles.heroShade} />
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}><span /> A little about us</p>
             <h1 id="hero-title">Made by<br />{' '}horse people,<br />{' '}<em>for horse<br />{' '}people.</em></h1>
            <p className={styles.heroLead}>A place to bring the people around a horse’s care a little closer together.</p>
          </div>
          <span className={styles.heroIndex}>EquiConnected · 01</span>
           <a className={styles.scrollCue} href="#about-mission">Scroll to discover <span /></a>
        </section>

        <section className={styles.mission} id="about-mission" aria-labelledby="mission-title">
          <p className={styles.eyebrowDark}>A more connected way to care</p>
           <h2 id="mission-title">Finding the right care can mean phone calls, questions <span className={styles.inlinePhoto}><img src={horseDetail} alt="" loading="lazy" /></span> and word of mouth. EquiConnected brings horse people and equine providers into one place <span className={styles.inlinePhoto}><img src={ownerPhoto} alt="" loading="lazy" /></span> so you can <em>start a more informed conversation.</em></h2>
          <span className={styles.missionRule} />
        </section>

        <section className={styles.story} id="about-story" aria-labelledby="story-title">
          <div className={styles.storyVisual} aria-label="Equine care, in the details">
             <img className={styles.storyArch} src={storyPhoto} alt="A close-up black-and-white portrait of a horse" loading="lazy" />
             <img className={styles.storyRound} src={horseDetail} alt="Close-up of a horse’s eye" loading="lazy" />
          </div>
          <div className={styles.storyCopy}>
            <p className={styles.eyebrowDark}>Why EquiConnected exists</p>
            <h2 id="story-title">From word of mouth<br />to one trusted place.</h2>
            <p>EquiConnected is a connection point for horse owners, riders and stable teams seeking equine care, and the veterinary professionals, clinics and hospitals who provide it.</p>
            <p>Care is personal, and no directory can make the decision for you. We make it easier to explore the information providers share and start a direct conversation about what your horse needs.</p>
            <Link className={styles.textLink} to={careHref}>{verifiedMember ? 'Explore the directory' : 'Find your starting point'} <span aria-hidden="true">↗</span></Link>
          </div>
        </section>

        <section className={styles.promises} id="about-promises" aria-labelledby="promises-title">
          <div className={styles.promisesHeading}>
            <div><p className={styles.eyebrowDark}>What we hold close</p><h2 id="promises-title">Four promises<br />we build around.</h2></div>
            <p>Not a substitute for a conversation or a clinical relationship. A thoughtful place to begin one.</p>
          </div>
          <div className={styles.promiseGrid}>
            {promises.map(([number, title, copy]) => (
              <article className={styles.promise} key={number}>
                <span className={styles.promiseMark}>{number}</span>
                <h3>{title}</h3><p>{copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.review} id="about-review" aria-labelledby="review-title">
          <div className={styles.reviewCopy}>
            <p className={styles.eyebrow}>A considered directory</p>
             <h2 id="review-title">A thoughtful review.<br />A clearer place to begin.</h2>
            <p className={styles.reviewLead}>Provider applications are reviewed before a profile is published. That review helps keep the directory considered; it is not a promise of clinical quality, suitability or availability.</p>
            <ol className={styles.reviewSteps}>
              <li><span>01</span><div><strong>Application received</strong><p>Providers submit information about their practice and professional role.</p></div></li>
              <li><span>02</span><div><strong>Details considered</strong><p>Submitted information is reviewed as part of the application process.</p></div></li>
              <li><span>03</span><div><strong>Profile published</strong><p>Approved profiles share details for members to explore.</p></div></li>
              <li><span>04</span><div><strong>Questions stay direct</strong><p>Contact providers to confirm services, suitability and current availability.</p></div></li>
            </ol>
          </div>
          <figure className={styles.reviewVisual}>
             <img src={reviewPhoto} alt="A horse resting its head beside the person caring for it" loading="lazy" />
            <figcaption>Care decisions belong with horse people and their veterinary professionals.</figcaption>
          </figure>
        </section>

        <section className={styles.community} id="about-community" aria-labelledby="community-title">
          <div className={styles.communityHead}>
            <p className={styles.eyebrowDark}>A community around care</p>
            <h2 id="community-title">One community,<br /><em>four ways in.</em></h2>
            <p>Whether you’re making decisions for a horse or providing the care they need, EquiConnected is designed to bring the right people into the same conversation.</p>
          </div>
          <div className={styles.communityGrid}>
            {communities.map(({ title, note, image, alt }, index) => (
              <article className={styles.communityCard} key={title}>
                <div className={styles.communityPhoto}><img src={image} alt={alt} loading="lazy" /></div>
                <span className={styles.cardIndex}>0{index + 1} / 04</span>
                <h3>{title}</h3><p>{note}</p>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.closing} id="about-join" aria-labelledby="closing-title">
          <img src={closePhoto} alt="" loading="lazy" />
          <div className={styles.closingShade} />
          <div className={styles.closingCopy}>
            <p className={styles.eyebrow}>For the horse, and everyone around them</p>
            <h2 id="closing-title">Care for your horse.<br /><em>Connected.</em></h2>
            <p>Explore equine providers and the details they choose to share. Then reach out and see what might work for you.</p>
            <div className={styles.actions}>
              <Link to={careHref} className={styles.goldButton}>{verifiedMember ? 'Explore providers' : 'Find equine care'} <span aria-hidden="true">↗</span></Link>
              <Link to="/provider/signup" className={styles.outlineButton}>I provide care</Link>
            </div>
          </div>
        </section>
      </main>
       <HomeFooter member={verifiedMember} careHref={careHref} />
    </div>
  );
}

export default AboutPage;