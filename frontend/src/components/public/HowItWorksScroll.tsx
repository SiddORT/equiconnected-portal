import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import styles from './HowItWorksScroll.module.css';

type HowItWorksStep = {
  number: string;
  label: string;
  title: string;
  description: string;
  image: string;
  alt: string;
};

const HOW_IT_WORKS_STEPS: HowItWorksStep[] = [
  {
    number: '01',
    label: 'SEARCH',
    title: 'Tell us what care you’re looking for.',
    description:
      'Start with the concern, specialty, or kind of support your horse needs. A clearer search begins with the right question.',
    image: '/horse-panel.jpg',
    alt: 'Horse standing in a quiet mountain pasture',
  },
  {
    number: '02',
    label: 'DISCOVER',
    title: 'Find care near your location.',
    description:
      'Explore doctors, clinics, and hospitals in the places that work for you, with the context to compare your options.',
    image: '/stable-panel.jpg',
    alt: 'Sunlit stable aisle with open horse stalls',
  },
  {
    number: '03',
    label: 'CONNECT',
    title: 'Choose with confidence.',
    description:
      'Explore profiles, reviews, and practical information, then connect with the provider who feels right for your horse.',
    image: '/provider-veterinary-care.jpg',
    alt: 'Equine care professional working with a horse indoors',
  },
];

if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  gsap.registerPlugin(ScrollTrigger);
}

export function HowItWorksScroll() {
  const [activeStep, setActiveStep] = useState(0);
  const [isDesktop, setIsDesktop] = useState(() => (
    typeof window !== 'undefined' && window.innerWidth > 799
  ));
  const [reducedMotion, setReducedMotion] = useState(() => (
    typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ));
  const storyRef = useRef<HTMLDivElement>(null);
  const storyTrackRef = useRef<HTMLDivElement>(null);
  const scrollTargetRef = useRef<number | null>(null);
  const scrollTargetTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const desktopQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia('(min-width: 800px)')
      : null;
    const motionQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)')
      : null;

    const updateViewportState = () => {
      setIsDesktop(desktopQuery ? desktopQuery.matches : window.innerWidth > 799);
      setReducedMotion(motionQuery?.matches ?? false);
    };
    const updateDesktopState = () => {
      setIsDesktop(desktopQuery ? desktopQuery.matches : window.innerWidth > 799);
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

  function getScrollGeometry() {
    const story = storyRef.current;
    const storyTrack = storyTrackRef.current;
    if (!story || !storyTrack || storyTrack.offsetHeight === 0) return null;

    const isMobile = window.innerWidth <= 799;
    const stickyOffset = isMobile ? 154 : 124;
    const railHeight = isMobile ? storyTrack.offsetTop : 0;

    return {
      story,
      stickyOffset,
      railHeight,
      stepDistance: storyTrack.offsetHeight / HOW_IT_WORKS_STEPS.length,
    };
  }

  function clearScrollTarget() {
    scrollTargetRef.current = null;
    if (scrollTargetTimerRef.current !== null) {
      window.clearTimeout(scrollTargetTimerRef.current);
      scrollTargetTimerRef.current = null;
    }
  }

  useEffect(() => {
    function updateActiveStep() {
      const geometry = getScrollGeometry();
      if (!geometry) return;

      const { story, stickyOffset, railHeight, stepDistance } = geometry;
      const stageTop = story.getBoundingClientRect().top + railHeight;
      const passedDistance = Math.max(0, stickyOffset - stageTop);
      const nextStep = Math.min(
        HOW_IT_WORKS_STEPS.length - 1,
        Math.floor(passedDistance / stepDistance),
      );

      if (scrollTargetRef.current !== null) {
        if (nextStep !== scrollTargetRef.current) return;
        clearScrollTarget();
      }
      setActiveStep(nextStep);
    }

    updateActiveStep();
    window.addEventListener('scroll', updateActiveStep, { passive: true });
    window.addEventListener('resize', updateActiveStep);
    window.addEventListener('wheel', clearScrollTarget, { passive: true });
    window.addEventListener('touchstart', clearScrollTarget, { passive: true });
    window.addEventListener('keydown', clearScrollTarget);

    return () => {
      window.removeEventListener('scroll', updateActiveStep);
      window.removeEventListener('resize', updateActiveStep);
      window.removeEventListener('wheel', clearScrollTarget);
      window.removeEventListener('touchstart', clearScrollTarget);
      window.removeEventListener('keydown', clearScrollTarget);
      clearScrollTarget();
    };
  }, []);

  useEffect(() => {
    const storyTrack = storyTrackRef.current;
    const panels = storyTrack?.querySelector<HTMLElement>(`.${styles.panels}`);
    const panelViewport = storyTrack?.querySelector<HTMLElement>(`.${styles.panelViewport}`);
    if (
      !storyTrack
      || !panels
      || !panelViewport
      || !isDesktop
      || reducedMotion
      || storyTrack.offsetHeight === 0
      || panelViewport.offsetHeight === 0
    ) return undefined;

    const context = gsap.context(() => {
      gsap.to(panels, {
        xPercent: -((HOW_IT_WORKS_STEPS.length - 1) / HOW_IT_WORKS_STEPS.length) * 100,
        ease: 'none',
        scrollTrigger: {
          trigger: storyTrack,
          start: 'top top+=124',
          end: () => `+=${Math.max(1, storyTrack.offsetHeight - panelViewport.offsetHeight)}`,
          scrub: true,
          invalidateOnRefresh: true,
        },
      });
    }, storyTrack);

    return () => context.revert();
  }, [isDesktop, reducedMotion]);

  function focusStep(index: number) {
    const nextIndex = (index + HOW_IT_WORKS_STEPS.length) % HOW_IT_WORKS_STEPS.length;
    setActiveStep(nextIndex);
    const geometry = getScrollGeometry();
    if (!geometry || typeof window.scrollTo !== 'function') return;

    const { story, stickyOffset, railHeight, stepDistance } = geometry;
    const storyTop = story.getBoundingClientRect().top + window.scrollY;
    const targetTop = storyTop + railHeight - stickyOffset + stepDistance * nextIndex;
    const reduceMotion =
      typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    clearScrollTarget();
    scrollTargetRef.current = nextIndex;
    scrollTargetTimerRef.current = window.setTimeout(clearScrollTarget, 1400);
    window.scrollTo({
      top: Math.max(0, targetTop),
      behavior: reduceMotion ? 'auto' : 'smooth',
    });
  }

  return (
    <section id="how-it-works" className={styles.section} aria-labelledby="how-it-works-heading">
      <div className={styles.sectionIntro}>
        <p className={styles.eyebrow}>
          <span className={styles.eyebrowRule} />
          How EquiConnected works
        </p>
        <h2 id="how-it-works-heading" className={styles.heading}>
          From concern to{' '}
          <span>confident care.</span>
        </h2>
      </div>

      <div
        className={`${styles.story} ${reducedMotion ? styles.reducedMotion : ''}`}
        ref={storyRef}
        data-care-journey-story
      >
        <nav
          className={styles.stepRail}
          aria-label="How EquiConnected works"
          data-care-journey-rail
        >
          <div className={styles.stepRailContent} data-care-journey-rail-controls>
            <p className={styles.railLabel}>Your path to care</p>
            <ol className={styles.steps}>
              {HOW_IT_WORKS_STEPS.map((step, index) => (
                <li key={step.label}>
                  <button
                    type="button"
                    className={`${styles.stepButton} ${index === activeStep ? styles.activeStep : ''}`}
                    aria-current={index === activeStep ? 'step' : undefined}
                    aria-label={`${step.number} — ${step.label}`}
                    onClick={() => focusStep(index)}
                  >
                    <span className={styles.stepNumber}>{step.number}</span>
                    <span className={styles.stepLabel}>{step.label}</span>
                    <span className={styles.stepMarker} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </nav>

        <div className={styles.storyTrack} ref={storyTrackRef} data-care-journey-track>
          <div className={styles.panelViewport} data-care-journey-viewport>
            <div className={styles.panels}>
              {HOW_IT_WORKS_STEPS.map((step, index) => (
                <article
                  key={step.label}
                  className={`${styles.panel} ${index === activeStep ? styles.activePanel : ''}`}
                  data-step-index={index}
                  aria-hidden={index !== activeStep}
                  aria-labelledby={`how-it-works-${step.label.toLowerCase()}`}
                  tabIndex={index === activeStep ? 0 : -1}
                >
                  <div className={styles.panelImageFrame}>
                    <img
                      className={styles.panelImage}
                      src={step.image}
                      alt={step.alt}
                      loading={index === 0 ? 'eager' : 'lazy'}
                    />
                    <span className={styles.panelImageNumber} aria-hidden="true">{step.number}</span>
                  </div>
                  <div className={styles.panelCopy}>
                    <p className={styles.panelKicker}>{step.label}</p>
                    <h3 id={`how-it-works-${step.label.toLowerCase()}`}>{step.title}</h3>
                    <p>{step.description}</p>
                    <span className={styles.panelRule} aria-hidden="true" />
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}