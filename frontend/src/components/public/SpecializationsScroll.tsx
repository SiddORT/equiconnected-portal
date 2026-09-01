import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import styles from './SpecializationsScroll.module.css';

type Specialization = {
  number: string;
  title: string;
  description: string;
  image: string;
  alt: string;
};

const SPECIALIZATIONS: Specialization[] = [
  {
    number: '01',
    title: 'Sports Medicine',
    description: 'Movement, performance, and recovery support for horses at every level.',
    image: '/horse-panel.jpg',
    alt: 'Horse standing in a quiet mountain pasture',
  },
  {
    number: '02',
    title: 'Internal Medicine',
    description: 'Thoughtful support for the complex systems that keep your horse well.',
    image: '/provider-veterinary-care.jpg',
    alt: 'Equine care professional working with a horse indoors',
  },
  {
    number: '03',
    title: 'Surgery & Orthopedics',
    description: 'Specialist guidance for injuries, procedures, and a confident return to care.',
    image: '/stable-panel.jpg',
    alt: 'Sunlit stable aisle with open horse stalls',
  },
  {
    number: '04',
    title: 'Reproduction',
    description: 'Experienced care for breeding, pregnancy, and the next generation.',
    image: '/hospital1.png',
    alt: 'Equine hospital exterior surrounded by trees',
  },
];

const DESKTOP_QUERY = '(min-width: 1100px)';
const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  gsap.registerPlugin(ScrollTrigger);
}

export function SpecializationsScroll() {
  const stageRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const [isDesktop, setIsDesktop] = useState(() => (
    typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(DESKTOP_QUERY).matches
  ));
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const desktopQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia(DESKTOP_QUERY)
      : null;
    const motionQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia(REDUCED_MOTION_QUERY)
      : null;

    const updateViewportState = () => {
      setIsDesktop(desktopQuery?.matches ?? window.innerWidth >= 1100);
      setReducedMotion(motionQuery?.matches ?? false);
    };
    const updateDesktopState = () => {
      setIsDesktop(desktopQuery?.matches ?? window.innerWidth >= 1100);
    };

    updateViewportState();
    window.addEventListener('resize', updateDesktopState);
    desktopQuery?.addEventListener?.('change', updateDesktopState);
    motionQuery?.addEventListener?.('change', updateViewportState);

    return () => {
      window.removeEventListener('resize', updateDesktopState);
      desktopQuery?.removeEventListener?.('change', updateDesktopState);
      motionQuery?.removeEventListener?.('change', updateViewportState);
    };
  }, []);

  useEffect(() => {
    const stage = stageRef.current;
    const viewport = viewportRef.current;
    const track = trackRef.current;
    if (!stage || !viewport || !track || !isDesktop || reducedMotion) return undefined;

    const cards = Array.from(track.querySelectorAll<HTMLElement>('[data-specialization-card]'));
    const images = Array.from(track.querySelectorAll<HTMLElement>('[data-specialization-parallax]'));
    if (cards.length === 0) return undefined;

    const updateCardStates = (progress: number) => {
      const activeIndex = Math.min(
        cards.length - 1,
        Math.max(0, Math.round(progress * (cards.length - 1))),
      );
      cards.forEach((card, index) => {
        card.dataset.cardState = index === activeIndex
          ? 'active'
          : index < activeIndex
            ? 'passed'
            : 'upcoming';
      });
    };
    updateCardStates(0);

    const cleanups: Array<() => void> = [];
    const context = gsap.context(() => {
      const getTravel = () => Math.max(0, track.scrollWidth - viewport.clientWidth);
      const horizontalTween = gsap.to(track, {
        x: () => -getTravel(),
        ease: 'none',
        scrollTrigger: {
          trigger: stage,
          start: 'top top+=124',
          end: () => `+=${Math.max(getTravel(), viewport.clientWidth * 0.8, 1)}`,
          pin: stage,
          scrub: true,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          onUpdate: (self) => updateCardStates(self.progress),
          onRefresh: (self) => updateCardStates(self.progress),
        },
      });

      images.forEach((image) => {
        gsap.fromTo(
          image,
          { xPercent: -3 },
          {
            xPercent: 3,
            ease: 'none',
            scrollTrigger: {
              trigger: image.closest('[data-specialization-card]'),
              containerAnimation: horizontalTween,
              start: 'left right',
              end: 'right left',
              scrub: true,
              invalidateOnRefresh: true,
            },
          },
        );
      });

      track.querySelectorAll<HTMLElement>('[data-specialization-card]').forEach((card) => {
        const image = card.querySelector<HTMLElement>('[data-specialization-image]');
        const content = card.querySelector<HTMLElement>('[data-specialization-reveal]');
        if (!image || !content) return;

        const reveal = () => {
          gsap.to(image, {
            scale: 1.06,
            duration: 0.62,
            ease: 'power2.out',
            overwrite: 'auto',
          });
          gsap.to(content, {
            y: -5,
            duration: 0.52,
            ease: 'power2.out',
            overwrite: 'auto',
          });
        };
        const conceal = () => {
          gsap.to(image, {
            scale: 1,
            duration: 0.62,
            ease: 'power2.out',
            overwrite: 'auto',
          });
          gsap.to(content, {
            y: 0,
            duration: 0.52,
            ease: 'power2.out',
            overwrite: 'auto',
          });
        };
        const focusOut = (event: FocusEvent) => {
          if (event.relatedTarget instanceof Node && card.contains(event.relatedTarget)) return;
          conceal();
        };

        card.addEventListener('pointerenter', reveal);
        card.addEventListener('pointerleave', conceal);
        card.addEventListener('focusin', reveal);
        card.addEventListener('focusout', focusOut);
        cleanups.push(() => {
          card.removeEventListener('pointerenter', reveal);
          card.removeEventListener('pointerleave', conceal);
          card.removeEventListener('focusin', reveal);
          card.removeEventListener('focusout', focusOut);
        });
      });

      const refresh = () => ScrollTrigger.refresh();
      window.addEventListener('resize', refresh);
      cleanups.push(() => window.removeEventListener('resize', refresh));
    }, stage);

    return () => {
      cleanups.forEach((cleanup) => cleanup());
      context.revert();
    };
  }, [isDesktop, reducedMotion]);

  return (
    <section
      id="specializations"
      className={`${styles.section} ${reducedMotion ? styles.reducedMotion : ''}`}
      aria-labelledby="specializations-heading"
      data-scroll-reveal
    >
      <div className={styles.intro}>
        <div>
          <p className={styles.eyebrow}><span aria-hidden="true" />Explore specializations</p>
          <h2 id="specializations-heading">
            The right care has a <em>point of view.</em>
          </h2>
        </div>
        <p className={styles.introCopy}>
          Begin with the kind of support your horse needs, then find the people and places
          connected to that work.
        </p>
      </div>

      <div
        className={styles.stage}
        ref={stageRef}
        data-specialization-stage
        data-specialization-mode={isDesktop && !reducedMotion ? 'pinned' : 'horizontal'}
      >
        <div className={styles.viewport} ref={viewportRef} data-specialization-viewport>
          <div className={styles.track} ref={trackRef} data-specialization-track>
            {SPECIALIZATIONS.map((specialization) => (
              <article
                key={specialization.number}
                className={styles.card}
                data-specialization-card
                data-card-state="upcoming"
              >
                <div className={styles.imageFrame}>
                  <div className={styles.imageParallax} data-specialization-parallax>
                    <img
                      className={styles.image}
                      src={specialization.image}
                      alt={specialization.alt}
                      data-specialization-image
                      loading={specialization.number === '01' ? 'eager' : 'lazy'}
                    />
                  </div>
                  <span className={styles.imageNumber} aria-hidden="true">{specialization.number}</span>
                </div>
                <div className={styles.cardBody}>
                  <div className={styles.cardHeading}>
                    <span className={styles.number}>{specialization.number}</span>
                    <h3>{specialization.title}</h3>
                  </div>
                  <div className={styles.reveal} data-specialization-reveal>
                    <p className={styles.description}>{specialization.description}</p>
                    <Link
                      to="/signup"
                      className={styles.explore}
                      aria-label={`Explore ${specialization.title} care`}
                    >
                      Explore <span aria-hidden="true">→</span>
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
        <p className={styles.scrollHint} aria-hidden="true">
          <span />Scroll to explore
        </p>
      </div>
    </section>
  );
}