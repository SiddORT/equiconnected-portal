import { Link } from 'react-router-dom';
import styles from './HomeV2.module.css';

function Arrow() {
  return <span className={styles.arrow} aria-hidden="true">↗</span>;
}

export function HomeHero({ member }: { member: boolean }) {
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
        <p className={styles.kicker}><span />Equine healthcare, connected</p>
        <h1 id="hero-heading">Trusted equine<br />{' '}care, <em>connected.</em></h1>
        <p className={styles.heroLead}>
          A clearer place to discover equine care providers and the details they choose to share.
        </p>
        <div className={styles.heroActions}>
          <Link to={member ? '/providers' : '/signup'} className={styles.goldButton}>
            {member ? 'Open directory' : 'Join EquiConnected'} <Arrow />
          </Link>
        </div>
        <p className={styles.memberNote}>Provider directory access is available to members.</p>
      </div>
      <a
        className={styles.photoCredit}
        href="https://unsplash.com/@helenalopesph"
        target="_blank"
        rel="noreferrer"
      >
        Hero photograph · Helena Lopes / Unsplash
      </a>
      <a className={styles.scrollCue} href="#care" aria-label="Scroll to care options"><span />Explore</a>
    </section>
  );
}