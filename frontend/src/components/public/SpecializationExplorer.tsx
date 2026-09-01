import { useRef, useState } from 'react';
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

export function SpecializationExplorer() {
  const [activeIndex, setActiveIndex] = useState(0);
  const trackRef = useRef<HTMLDivElement>(null);

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
        <div>
          <p className={styles.carouselKicker}>Find the right perspective</p>
          <h3>Explore specializations</h3>
        </div>
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
    </section>
  );
}