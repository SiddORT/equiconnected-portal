import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import styles from './SpecializationExplorer.module.css';

type Specialization = {
  title: string;
  description: string;
  image: string;
  alt: string;
  position?: string;
};

const SPECIALIZATIONS: Specialization[] = [
  {
    title: 'Cardiology',
    description: 'Heart health, circulation, and performance support.',
    image: '/provider-veterinary-care.jpg',
    alt: 'Equine care professional examining a horse',
    position: '58% center',
  },
  {
    title: 'Dermatology',
    description: 'Practical support for skin, coat, and allergy concerns.',
    image: '/horse-panel.jpg',
    alt: 'Dark horse standing in a mountain pasture',
    position: '70% center',
  },
  {
    title: 'Neurology',
    description: 'Thoughtful assessment for balance, movement, and nerves.',
    image: '/horse-panel.jpg',
    alt: 'Dark horse looking across a quiet pasture',
    position: '78% 42%',
  },
  {
    title: 'Pediatrics',
    description: 'A considered start for foals and growing horses.',
    image: '/stable-panel.jpg',
    alt: 'Warm stable aisle with open horse stalls',
    position: '72% center',
  },
  {
    title: 'Orthopedics',
    description: 'Mobility, recovery, and soundness from hoof to hip.',
    image: '/provider-veterinary-care.jpg',
    alt: 'Professional supporting a horse during care',
    position: '38% center',
  },
  {
    title: 'Dentistry',
    description: 'Comfort-focused dental care for every stage of life.',
    image: '/provider-veterinary-care.jpg',
    alt: 'Horse receiving hands-on veterinary care',
    position: '28% center',
  },
  {
    title: 'Ophthalmology',
    description: 'Protecting clear vision and everyday confidence.',
    image: '/horse-panel.jpg',
    alt: 'Horse in soft evening light',
    position: '78% 55%',
  },
  {
    title: 'Reproduction',
    description: 'Planning, fertility, and breeding care with patience.',
    image: '/stable-panel.jpg',
    alt: 'Sunlit stable opening toward a paddock',
    position: '88% center',
  },
];

const DESKTOP_BREAKPOINT = 1100;

export function SpecializationExplorer() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isDesktop, setIsDesktop] = useState(() => (
    typeof window !== 'undefined' && window.innerWidth >= DESKTOP_BREAKPOINT
  ));
  const [reducedMotion, setReducedMotion] = useState(() => (
    typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ));
  const trackRef = useRef<HTMLDivElement>(null);
  const premiumStageRef = useRef<HTMLDivElement>(null);
  const premiumTrackRef = useRef<HTMLDivElement>(null);

  function chooseSpecialization(index: number) {
    const nextIndex = (index + SPECIALIZATIONS.length) % SPECIALIZATIONS.length;
    setActiveIndex(nextIndex);
    const card = trackRef.current?.querySelector<HTMLElement>(
      `[data-specialization-index="${nextIndex}"]`,
    );
    if (card && typeof card.scrollIntoView === 'function') {
      const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      card.scrollIntoView({
        behavior: reduceMotion ? 'auto' : 'smooth',
        block: 'nearest',
        inline: 'center',
      });
    }
  }

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const desktopQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia(`(min-width: ${DESKTOP_BREAKPOINT}px)`)
      : null;
    const motionQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)')
      : null;

    function updateViewportState() {
      setIsDesktop(desktopQuery ? desktopQuery.matches : window.innerWidth >= DESKTOP_BREAKPOINT);
      setReducedMotion(motionQuery?.matches ?? false);
    }

    function updateDesktopState() {
      setIsDesktop(desktopQuery ? desktopQuery.matches : window.innerWidth >= DESKTOP_BREAKPOINT);
    }

    updateViewportState();
    window.addEventListener('resize', updateDesktopState);

    if (desktopQuery && typeof desktopQuery.addEventListener === 'function') {
      desktopQuery.addEventListener('change', updateDesktopState);
    } else if (desktopQuery && typeof desktopQuery.addListener === 'function') {
      desktopQuery.addListener(updateDesktopState);
    }

    if (motionQuery && typeof motionQuery.addEventListener === 'function') {
      motionQuery.addEventListener('change', updateViewportState);
    } else if (motionQuery && typeof motionQuery.addListener === 'function') {
      motionQuery.addListener(updateViewportState);
    }

    return () => {
      window.removeEventListener('resize', updateDesktopState);
      if (desktopQuery && typeof desktopQuery.removeEventListener === 'function') {
        desktopQuery.removeEventListener('change', updateDesktopState);
      } else if (desktopQuery && typeof desktopQuery.removeListener === 'function') {
        desktopQuery.removeListener(updateDesktopState);
      }
      if (motionQuery && typeof motionQuery.removeEventListener === 'function') {
        motionQuery.removeEventListener('change', updateViewportState);
      } else if (motionQuery && typeof motionQuery.removeListener === 'function') {
        motionQuery.removeListener(updateViewportState);
      }
    };
  }, []);

  useEffect(() => {
    const stage = premiumStageRef.current;
    const premiumTrack = premiumTrackRef.current;
    if (!stage || !premiumTrack || !isDesktop || reducedMotion) return undefined;

    const viewport = stage.querySelector<HTMLElement>(`.${styles.premiumViewport}`);
    const cards = Array.from(
      premiumTrack.querySelectorAll<HTMLElement>(`.${styles.premiumCard}`),
    );
    const images = cards.map((card) => card.querySelector<HTMLElement>(`.${styles.premiumImage}`));
    const copies = cards.map((card) => card.querySelector<HTMLElement>(`.${styles.premiumCardCopy}`));
    const links = cards.map((card) => card.querySelector<HTMLAnchorElement>(`.${styles.premiumExplore}`));
    if (!viewport || cards.length === 0) return undefined;

    gsap.registerPlugin(ScrollTrigger);

    const removeFocusListeners: Array<() => void> = [];
    const context = gsap.context(() => {
      const setCardProgress = (progress: number) => {
        const cardPosition = progress * (cards.length - 1);
        const currentIndex = Math.min(
          cards.length - 1,
          Math.max(0, Math.round(cardPosition)),
        );

        cards.forEach((card, index) => {
          const state = index < currentIndex
            ? 'passed'
            : index === currentIndex
              ? 'active'
              : 'upcoming';
          card.dataset.premiumState = state;
          const distanceFromCurrent = index - cardPosition;
          const image = images[index];
          const copy = copies[index];
          if (image) {
            gsap.set(image, {
              xPercent: Math.max(-3, Math.min(3, distanceFromCurrent * 3)),
              scale: index === currentIndex ? 1.04 : 1,
            });
          }
          if (copy) {
            gsap.set(copy, { y: index === currentIndex ? -6 : 0 });
          }
        });
      };

      setCardProgress(0);
      const tween = gsap.to(premiumTrack, {
        x: () => -Math.max(0, premiumTrack.scrollWidth - viewport.clientWidth),
        ease: 'none',
        scrollTrigger: {
          trigger: stage,
          pin: true,
          start: 'top top+=112',
          end: () => `+=${Math.max(1, premiumTrack.scrollWidth - viewport.clientWidth)}`,
          scrub: 0.8,
          invalidateOnRefresh: true,
          anticipatePin: 1,
          onUpdate: (self) => setCardProgress(self.progress),
        },
      });

      links.forEach((link, index) => {
        if (!link) return;
        const revealFocusedCard = () => {
          const trigger = tween.scrollTrigger;
          if (!trigger || typeof window.scrollTo !== 'function') return;
          const progress = cards.length === 1 ? 0 : index / (cards.length - 1);
          window.scrollTo({
            top: trigger.start + ((trigger.end - trigger.start) * progress),
            behavior: 'auto',
          });
        };
        link.addEventListener('focus', revealFocusedCard);
        removeFocusListeners.push(() => link.removeEventListener('focus', revealFocusedCard));
      });
    }, stage);

    return () => {
      removeFocusListeners.forEach((removeListener) => removeListener());
      context.revert();
      cards.forEach((card, index) => {
        card.dataset.premiumState = index === 0 ? 'active' : 'upcoming';
      });
    };
  }, [isDesktop, reducedMotion]);

  return (
    <section
      id="specializations"
      className={styles.section}
      data-layout="full-bleed"
      aria-labelledby="specializations-heading"
    >
      <div className={styles.intro}>
        <p className={styles.eyebrow}>
          <span className={styles.eyebrowRule} />
          Care, considered
          <span className={styles.eyebrowRule} />
        </p>
        <h2 id="specializations-heading" className={styles.heading}>
          A closer look at{' '}
          <span>whole-horse care.</span>
        </h2>

        <div className={styles.story}>
          <div className={styles.storyImageFrame}>
            <img
              className={styles.storyImage}
              src="/horse-panel.jpg"
              alt="Dark horse standing in a quiet mountain pasture"
            />
            <span className={styles.storyStamp} aria-hidden="true">EC / 02</span>
          </div>
          <div className={styles.storyCopy}>
            <p className={styles.storyLead}>
              The right care starts with seeing the full picture.
            </p>
            <p>
              EquiConnected brings trusted equine healthcare together, so every concern
              can be met with context, clarity, and a team that understands the horse
              behind the appointment.
            </p>
            <p>
              Explore the areas of care that matter most to you, then find the people
              ready to help you move forward.
            </p>
            <span className={styles.storyRule} aria-hidden="true" />
          </div>
        </div>
      </div>

      <div className={styles.carouselHeader}>
        <div className={styles.carouselControls}>
          <button
            type="button"
            className={styles.carouselButton}
            aria-label="Previous specialization"
            onClick={() => chooseSpecialization(activeIndex - 1)}
          >
            <span aria-hidden="true">←</span>
          </button>
          <button
            type="button"
            className={styles.carouselButton}
            aria-label="Next specialization"
            onClick={() => chooseSpecialization(activeIndex + 1)}
          >
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </div>

      <div
        className={styles.track}
        ref={trackRef}
        role="group"
        aria-label="Equine healthcare specializations"
      >
        {SPECIALIZATIONS.map((specialization, index) => (
          <button
            type="button"
            key={specialization.title}
            data-specialization-card
            data-specialization-index={index}
            className={`${styles.card} ${index === activeIndex ? styles.activeCard : ''}`}
            aria-pressed={index === activeIndex}
            onClick={() => chooseSpecialization(index)}
          >
            <span className={styles.cardImageFrame}>
              <img
                className={styles.cardImage}
                src={specialization.image}
                alt={specialization.alt}
                style={{ objectPosition: specialization.position }}
                loading="lazy"
              />
            </span>
            <span className={styles.cardBody}>
              <span className={styles.cardNumber}>0{index + 1}</span>
              <span className={styles.cardTitle}>{specialization.title}</span>
              <span className={styles.cardDescription}>{specialization.description}</span>
            </span>
          </button>
        ))}
      </div>

      <p className={styles.carouselStatus} aria-live="polite">
        Selected {SPECIALIZATIONS[activeIndex].title}
      </p>

      <section
        className={`${styles.premiumExperience} ${reducedMotion ? styles.premiumReducedMotion : ''}`}
        aria-labelledby="premium-specializations-heading"
        data-premium-specializations
        data-premium-motion={reducedMotion ? 'reduced' : 'scroll'}
      >
        <div className={styles.premiumHeader}>
          <div>
            <p className={styles.premiumKicker}>A deeper view</p>
            <h3 id="premium-specializations-heading">Care, in focus.</h3>
          </div>
          <p className={styles.premiumIntro}>
            A considered approach for every chapter of the horse&apos;s life.
          </p>
        </div>

        <div
          className={styles.premiumStage}
          ref={premiumStageRef}
          data-premium-stage
          data-premium-pinning={isDesktop && !reducedMotion ? 'enabled' : 'disabled'}
        >
          <div className={styles.premiumViewport} data-premium-viewport>
            <div className={styles.premiumTrack} ref={premiumTrackRef} data-premium-track>
              {SPECIALIZATIONS.map((specialization, index) => (
                <article
                  className={styles.premiumCard}
                  data-premium-card
                  data-premium-state={index === 0 ? 'active' : 'upcoming'}
                  key={`premium-${specialization.title}`}
                >
                  <div className={styles.premiumImageFrame}>
                    <img
                      className={styles.premiumImage}
                      src={specialization.image}
                      alt={specialization.alt}
                      style={{ objectPosition: specialization.position }}
                      loading={index === 0 ? 'eager' : 'lazy'}
                    />
                  </div>
                  <div className={styles.premiumCardCopy}>
                    <span className={styles.premiumNumber}>0{index + 1}</span>
                    <h4>{specialization.title}</h4>
                    <p>{specialization.description}</p>
                    <a
                      className={styles.premiumExplore}
                      href="/signup"
                      aria-label={`Explore ${specialization.title} care options`}
                    >
                      EXPLORE <span aria-hidden="true">→</span>
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
    </section>
  );
}