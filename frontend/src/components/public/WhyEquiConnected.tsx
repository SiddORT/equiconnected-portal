import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
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

const DESKTOP_QUERY = '(min-width: 1100px)';
const TABLET_QUERY = '(min-width: 701px)';
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
  const [isDesktop, setIsDesktop] = useState(() => (
    typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(DESKTOP_QUERY).matches
  ));
  const [isTabletOrLarger, setIsTabletOrLarger] = useState(() => (
    typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(TABLET_QUERY).matches
  ));
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);
  const stageRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLSpanElement>(null);
  const activeIndexRef = useRef(0);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const desktopQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia(DESKTOP_QUERY)
      : null;
    const tabletQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia(TABLET_QUERY)
      : null;
    const motionQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia(REDUCED_MOTION_QUERY)
      : null;
    const updateViewportState = () => {
      setIsDesktop(desktopQuery?.matches ?? false);
      setIsTabletOrLarger(tabletQuery?.matches ?? false);
      setReducedMotion(motionQuery?.matches ?? false);
    };
    const updateResponsiveState = () => {
      setIsDesktop(desktopQuery?.matches ?? false);
      setIsTabletOrLarger(tabletQuery?.matches ?? false);
    };

    updateViewportState();
    window.addEventListener('resize', updateResponsiveState);
    desktopQuery?.addEventListener?.('change', updateResponsiveState);
    tabletQuery?.addEventListener?.('change', updateResponsiveState);
    motionQuery?.addEventListener?.('change', updateViewportState);

    return () => {
      window.removeEventListener('resize', updateResponsiveState);
      desktopQuery?.removeEventListener?.('change', updateResponsiveState);
      tabletQuery?.removeEventListener?.('change', updateResponsiveState);
      motionQuery?.removeEventListener?.('change', updateViewportState);
    };
  }, []);

  useLayoutEffect(() => {
    const stage = stageRef.current;
    const progress = progressRef.current;
    if (!stage || !progress) return undefined;

    const cards = Array.from(stage.querySelectorAll<HTMLElement>('[data-why-card]'));
    const setCardStates = (index: number) => {
      cards.forEach((card, cardIndex) => {
        card.dataset.cardState = cardIndex === index
          ? 'active'
          : cardIndex < index
            ? 'passed'
            : 'upcoming';
      });
    };
    setCardStates(activeIndexRef.current);

    if (!isTabletOrLarger || reducedMotion) {
      progress.style.removeProperty('transform');
      return undefined;
    }

    gsap.registerPlugin(ScrollTrigger);
    const refresh = () => ScrollTrigger.refresh();
    const context = gsap.context(() => {
      const updateProgress = (value: number) => {
        const safeProgress = Math.min(1, Math.max(0, value));
        const nextIndex = Math.min(
          ADVANTAGES.length - 1,
          Math.floor(safeProgress * ADVANTAGES.length),
        );
        setCardStates(nextIndex);
        if (nextIndex !== activeIndexRef.current) {
          activeIndexRef.current = nextIndex;
          setActiveIndex(nextIndex);
        }
      };

      gsap.fromTo(
        progress,
        { scaleX: 0 },
        {
          scaleX: 1,
          transformOrigin: 'left center',
          ease: 'none',
          scrollTrigger: {
            trigger: stage,
            start: isDesktop ? 'top top+=112' : 'top 78%',
            end: isDesktop
              ? () => `+=${Math.max(stage.offsetHeight * 1.8, window.innerHeight * 2.4)}`
              : 'bottom 32%',
            pin: isDesktop ? stage : false,
            pinSpacing: isDesktop,
            scrub: true,
            anticipatePin: 1,
            invalidateOnRefresh: true,
            onUpdate: (self) => updateProgress(self.progress),
            onRefresh: (self) => updateProgress(self.progress),
            onEnter: () => updateProgress(0),
            onEnterBack: (self) => updateProgress(self.progress),
            onLeave: () => updateProgress(1),
            onLeaveBack: () => updateProgress(0),
          },
        },
      );

      const refreshFrame = window.requestAnimationFrame(refresh);
      window.addEventListener('resize', refresh);
      const imageRefreshCleanups: Array<() => void> = [];
      stage.querySelectorAll<HTMLImageElement>('img').forEach((image) => {
        if (image.complete) return;
        image.addEventListener('load', refresh, { once: true });
        imageRefreshCleanups.push(() => image.removeEventListener('load', refresh));
      });

      return () => {
        window.cancelAnimationFrame(refreshFrame);
        imageRefreshCleanups.forEach((cleanup) => cleanup());
      };
    }, stage);

    return () => {
      window.removeEventListener('resize', refresh);
      context.revert();
      progress.style.removeProperty('transform');
      setCardStates(activeIndexRef.current);
    };
  }, [isDesktop, isTabletOrLarger, reducedMotion]);

  function activateCard(index: number) {
    activeIndexRef.current = index;
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
        ref={stageRef}
        data-why-stage
        data-why-mode={
          reducedMotion || !isTabletOrLarger
            ? 'natural'
            : isDesktop
              ? 'pinned'
              : 'scroll'
        }
      >
        <div className={styles.journeyHeader}>
          <span>How the picture comes together</span>
          <span aria-hidden="true">01 — 04</span>
        </div>
        <div className={styles.journeyLine} aria-hidden="true">
          <span className={styles.journeyLineBase} />
          <span className={styles.journeyProgress} ref={progressRef} />
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
