import { useEffect, useRef, useState } from 'react';
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

export function HowItWorksScroll() {
  const [activeStep, setActiveStep] = useState(0);
  const panelRefs = useRef<Array<HTMLElement | null>>([]);
  const visibilityRatios = useRef<number[]>(HOW_IT_WORKS_STEPS.map(() => 0));

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const index = Number((entry.target as HTMLElement).dataset.stepIndex);
          if (!Number.isNaN(index)) {
            visibilityRatios.current[index] = entry.isIntersecting ? entry.intersectionRatio : 0;
          }
        });

        const highestRatio = Math.max(...visibilityRatios.current);
        if (highestRatio <= 0) return;
        setActiveStep(visibilityRatios.current.indexOf(highestRatio));
      },
      {
        threshold: Array.from({ length: 21 }, (_, index) => index / 20),
        rootMargin: '-12% 0px -30% 0px',
      },
    );

    panelRefs.current.forEach((panel) => {
      if (panel) observer.observe(panel);
    });

    return () => observer.disconnect();
  }, []);

  function focusStep(index: number) {
    setActiveStep(index);
    const panel = panelRefs.current[index];
    if (!panel) return;

    if (typeof panel.scrollIntoView === 'function') {
      const reduceMotion =
        typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      panel.scrollIntoView({
        behavior: reduceMotion ? 'auto' : 'smooth',
        block: 'center',
      });
    }
  }

  return (
    <section className={styles.section} aria-labelledby="how-it-works-heading">
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

      <div className={styles.story}>
        <nav className={styles.stepRail} aria-label="How EquiConnected works">
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
        </nav>

        <div className={styles.panels}>
          {HOW_IT_WORKS_STEPS.map((step, index) => (
            <article
              key={step.label}
              ref={(panel) => {
                panelRefs.current[index] = panel;
              }}
              className={`${styles.panel} ${index === activeStep ? styles.activePanel : ''}`}
              data-step-index={index}
              aria-labelledby={`how-it-works-${step.label.toLowerCase()}`}
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
    </section>
  );
}