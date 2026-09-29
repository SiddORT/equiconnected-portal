import { Link } from 'react-router-dom';
import styles from '@/pages/PublicPage.module.css';

function Arrow() {
  return <span className={styles.arrow} aria-hidden="true">↗</span>;
}

export function HomeHero({ careHref }: { careHref: string }) {
  return (
    <section className={styles.hero} aria-labelledby="hero-heading">
      <img
        className={styles.heroImage}
        src="/home-v2-hero.jpg"
        alt="A white horse moving through a dark green pasture"
        fetchPriority="high"
      />
      <div className={styles.heroShade} />
      <div className={styles.heroInner}>
        <p className={styles.kicker}><span />Equine care, connected</p>
        <h1 id="hero-heading">Trusted equine care,<br /><em>connected.</em></h1>
        <p className={styles.heroLead}>
          A clearer way for horse owners and stable teams to find equine care providers that fit their needs.
        </p>
        <div className={styles.heroActions}>
          <Link to={careHref} className={styles.goldButton}>Find care <Arrow /></Link>
          <Link to="/provider/signup" className={styles.ghostButton}>Join as a provider</Link>
        </div>
        <p className={styles.memberNote}>Provider directory access is available to members.</p>
      </div>
      <a
        className={styles.photoCredit}
        href="https://unsplash.com/@helenalopesph"
        target="_blank"
        rel="noreferrer"
      >
        Photo by Helena Lopes on Unsplash
      </a>
      <a className={styles.scrollCue} href="#care" aria-label="Scroll to care options"><span />Explore</a>
    </section>
  );
}