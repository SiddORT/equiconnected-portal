import { useEffect, useState, type ReactNode } from 'react';
import styles from './WhyEquiConnected.module.css';

type Advantage = {
  number: string;
  title: string;
  description: string;
  icon: 'location' | 'specialization' | 'community' | 'connected';
  image: string;
  imageAlt: string;
};

const ADVANTAGES: Advantage[] = [
  {
    number: '01',
    title: 'Location-first discovery',
    description: 'Find relevant care around you.',
    icon: 'location',
    image: '/stable-panel.jpg',
    imageAlt: 'Warm stable aisle opening onto a paddock',
  },
  {
    number: '02',
    title: 'Specialization-based search',
    description: 'Start with the type of care you need.',
    icon: 'specialization',
    image: '/hospital1.png',
    imageAlt: 'Chestnut horse moving through shallow water',
  },
  {
    number: '03',
    title: 'Real community insight',
    description: 'Explore ratings, reviews and comments.',
    icon: 'community',
    image: '/provider-veterinary-care.jpg',
    imageAlt: 'Equine care provider working with a horse',
  },
  {
    number: '04',
    title: 'One connected platform',
    description: 'Doctors, clinics and hospitals in one ecosystem.',
    icon: 'connected',
    image: '/about-equiconnected-transparent.png',
    imageAlt: 'Equine healthcare team caring for a horse',
  },
];

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

function AdvantageIcon({ type }: { type: Advantage['icon'] }) {
  const iconPaths = {
    location: <><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
    specialization: <><path d="M12 3v18M3 12h18" /><path d="m6 6 12 12M18 6 6 18" /></>,
    community: <><path d="M5 18V9M12 18V5M19 18v-7" /><path d="M3 21h18" /></>,
    connected: <><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="6" r="2.5" /><circle cx="18" cy="18" r="2.5" /><path d="m8.2 11 7.5-4M8.2 13l7.5 4" /></>,
  } satisfies Record<Advantage['icon'], ReactNode>;

  return (
    <svg className={styles.icon} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {iconPaths[type]}
    </svg>
  );
}

export function WhyEquiConnected() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const motionQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia(REDUCED_MOTION_QUERY)
      : null;
    const updateMotionState = () => setReducedMotion(motionQuery?.matches ?? false);
    updateMotionState();
    motionQuery?.addEventListener?.('change', updateMotionState);

    return () => {
      motionQuery?.removeEventListener?.('change', updateMotionState);
    };
  }, []);

  function activateCard(index: number) {
    setActiveIndex(index);
  }

  return (
    <section
      id="why-equiconnected"
      className={`${styles.section} ${reducedMotion ? styles.reducedMotion : ''}`}
      aria-labelledby="why-equiconnected-heading"
      data-why-section
    >
      <div className={styles.intro}>
        <div className={styles.introCopy}>
          <p className={styles.eyebrow}><span aria-hidden="true" />Why EquiConnected?</p>
          <h2 id="why-equiconnected-heading">
            The right care starts with a <em>clearer picture.</em>
          </h2>
        </div>
        <p className={styles.description}>
          EquiConnected brings the context around equine healthcare into one considered place, so
          finding support feels less like sorting through a list and more like making a confident
          next choice.
        </p>
      </div>

      <div
        className={styles.stage}
        data-why-stage
        data-why-mode="natural"
      >
        <div className={styles.journeyHeader}>
          <span>How the picture comes together</span>
          <span aria-hidden="true">01 — 04</span>
        </div>
        <div className={styles.journeyLine} aria-hidden="true">
          <span className={styles.journeyLineBase} />
          <span className={styles.journeyDots}>
            {ADVANTAGES.map((advantage) => <span key={advantage.number} />)}
          </span>
        </div>
        <div className={styles.advantageGrid} aria-label="EquiConnected advantages">
          {ADVANTAGES.map((advantage, index) => {
            const titleId = `why-equiconnected-${advantage.number}-title`;
            return (
              <article
                className={styles.advantageCard}
                key={advantage.number}
                data-why-card
                data-card-state={index === activeIndex ? 'active' : index < activeIndex ? 'passed' : 'upcoming'}
                aria-labelledby={titleId}
              >
                <div className={styles.imageFrame}>
                  <img
                    className={styles.cardImage}
                    src={advantage.image}
                    alt={advantage.imageAlt}
                    loading="lazy"
                    decoding="async"
                  />
                  <span className={styles.imageShade} aria-hidden="true" />
                </div>
                <button
                  type="button"
                  className={styles.cardTrigger}
                  aria-label={`Activate ${advantage.number}: ${advantage.title}`}
                  aria-pressed={index === activeIndex}
                  onClick={() => activateCard(index)}
                  onFocus={() => activateCard(index)}
                >
                  <span className={styles.cardTopline}>
                    <span className={styles.number}>{advantage.number}</span>
                    <span className={styles.symbol}><AdvantageIcon type={advantage.icon} /></span>
                  </span>
                  <span className={styles.cardTitle} id={titleId}>{advantage.title}</span>
                </button>
                <p className={styles.cardDescription}>{advantage.description}</p>
                <span className={styles.cardExplore} aria-hidden="true">Explore <span>→</span></span>
                <span className={styles.cardRule} aria-hidden="true" />
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
