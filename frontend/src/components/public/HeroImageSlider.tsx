import { useEffect, useState } from 'react';
import styles from './HeroImageSlider.module.css';

type Slide = {
  src: string;
  alt: string;
  label: string;
  title: string;
};

const SLIDES: Slide[] = [
  {
    src: '/horse-panel.jpg',
    alt: 'Dark horse standing in a quiet mountain pasture at sunset',
    label: 'A considered approach to care',
    title: 'Care that sees the whole horse.',
  },
  {
    src: '/provider-veterinary-care.jpg',
    alt: 'Equine care professional working with a horse indoors',
    label: 'Expertise, connected',
    title: 'The right hands, when they matter.',
  },
  {
    src: '/stable-panel.jpg',
    alt: 'Warm, well-kept stable with open doors to the paddock',
    label: 'A trusted care community',
    title: 'Every detail has a place.',
  },
];

const AUTOPLAY_DELAY = 5600;

export function HeroImageSlider() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const [hasFocus, setHasFocus] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(() => (
    typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ));

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined;

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotionPreference = () => setReducedMotion(mediaQuery.matches);
    updateMotionPreference();
    mediaQuery.addEventListener('change', updateMotionPreference);
    return () => mediaQuery.removeEventListener('change', updateMotionPreference);
  }, []);

  useEffect(() => {
    if (isHovered || hasFocus || reducedMotion) return undefined;

    const timer = window.setInterval(() => {
      setActiveIndex((currentIndex) => (currentIndex + 1) % SLIDES.length);
    }, AUTOPLAY_DELAY);

    return () => window.clearInterval(timer);
  }, [hasFocus, isHovered, reducedMotion]);

  function showSlide(index: number) {
    setActiveIndex((index + SLIDES.length) % SLIDES.length);
  }

  function handleBlur(event: React.FocusEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setHasFocus(false);
    }
  }

  const activeSlide = SLIDES[activeIndex];

  return (
    <div
      className={`${styles.slider} ${reducedMotion ? styles.reducedMotion : ''}`}
      aria-label="Equine care stories"
      role="region"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocus={() => setHasFocus(true)}
      onBlur={handleBlur}
    >
      <div className={styles.viewport}>
        {SLIDES.map((slide, index) => (
          <img
            key={slide.src}
            className={`${styles.slide} ${index === activeIndex ? styles.activeSlide : ''}`}
            src={slide.src}
            alt={index === activeIndex ? slide.alt : ''}
            aria-hidden={index !== activeIndex}
            loading={index === 0 ? 'eager' : 'lazy'}
          />
        ))}
        <div className={styles.imageShade} aria-hidden="true" />
        <div className={styles.slideMeta} aria-live="polite">
          <span>{activeSlide.label}</span>
          <strong>{activeSlide.title}</strong>
        </div>
        <div className={styles.slideCount} aria-hidden="true">
          <span>0{activeIndex + 1}</span>
          <i />
          <span>0{SLIDES.length}</span>
        </div>
        <div className={styles.controls}>
          <button
            type="button"
            className={styles.control}
            aria-label="Previous image"
            onClick={() => showSlide(activeIndex - 1)}
          >
            <span aria-hidden="true">←</span>
          </button>
          <button
            type="button"
            className={styles.control}
            aria-label="Next image"
            onClick={() => showSlide(activeIndex + 1)}
          >
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </div>
      <svg className={styles.crescentCut} viewBox="0 0 100 18" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="crescent-border-gradient" x1="-20%" y1="0%" x2="120%" y2="0%">
            <stop offset="0%" stopColor="#9b7427" />
            <stop offset="50%" stopColor="#f0d98e" />
            <stop offset="100%" stopColor="#b78b33" />
            {!reducedMotion && (
              <>
                <animate attributeName="x1" values="-20%;20%;-20%" dur="8s" repeatCount="indefinite" />
                <animate attributeName="x2" values="80%;120%;80%" dur="8s" repeatCount="indefinite" />
              </>
            )}
          </linearGradient>
        </defs>
        <path className={styles.crescentFill} d="M0 0 Q50 16 100 0 L100 18 L0 18 Z" />
        <path className={styles.archShadow} d="M0 0 Q50 16 100 0" />
        <path className={styles.archLine} d="M0 0 Q50 16 100 0" />
      </svg>
      <div className={styles.indicators} role="group" aria-label="Choose a hero image">
        {SLIDES.map((slide, index) => (
          <button
            key={slide.src}
            type="button"
            aria-label={`Show image ${index + 1}: ${slide.label}`}
            aria-pressed={index === activeIndex}
            className={`${styles.indicator} ${index === activeIndex ? styles.activeIndicator : ''}`}
            onClick={() => showSlide(index)}
          />
        ))}
      </div>
    </div>
  );
}