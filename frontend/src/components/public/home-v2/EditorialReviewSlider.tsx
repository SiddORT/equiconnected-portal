import { useState } from 'react';
import { Link } from 'react-router-dom';
import styles from './HomeV2.module.css';

const slides = [
  {
    statement: 'A little more context. A conversation that starts in the right place.',
    support: 'When someone has shared a real experience, it can help you know what to ask next.',
    label: 'A note on feedback',
    title: 'Only what’s really there.',
    detail: 'Reviews and ratings appear on provider profiles only when real member feedback is available. Open a profile to find it alongside the information the provider shares.',
  },
  {
    statement: 'Read the experience, then check the details.',
    support: 'A review can add context. Look at the provider’s services, locations and profile information before deciding what to ask.',
    label: 'Review context',
    title: 'Beside the profile.',
    detail: 'When available, member feedback appears on provider profiles alongside the information the provider shares.',
  },
  {
    statement: 'Your next question matters as much as a rating.',
    support: 'Care can vary by horse, location and timing. Ask the provider directly what they can offer now.',
    label: 'Before you book',
    title: 'Confirm what fits.',
    detail: 'Use available reviews as one input, then contact the provider to confirm services and availability.',
  },
] as const;

export function EditorialReviewSlider({ careHref }: { careHref: string }) {
  const [active, setActive] = useState(0);
  const slide = slides[active];
  const show = (index: number) => setActive((index + slides.length) % slides.length);

  return (
    <section className={styles.editorial} aria-labelledby="editorial-heading" aria-roledescription="carousel">
      <div className={styles.editorialIntro}>
        <div>
          <p className={styles.sectionKicker}>Ratings &amp; reviews</p>
          <h2 id="editorial-heading">In their words.</h2>
        </div>
        <div className={styles.editorialControls} aria-label="Review guide controls">
          <button type="button" aria-label="Previous review guide slide" aria-controls="editorial-slide" onClick={() => show(active - 1)}>←</button>
          <button type="button" aria-label="Next review guide slide" aria-controls="editorial-slide" onClick={() => show(active + 1)}>→</button>
        </div>
      </div>
      <div className={styles.editorialBody} id="editorial-slide" aria-live="polite" aria-atomic="true">
        <div className={styles.editorialThought}>
          <span className={styles.editorialRule} aria-hidden="true" />
          <p className={styles.editorialStatement}>{slide.statement}</p>
          <p className={styles.editorialSupport}>{slide.support}</p>
        </div>
        <aside className={styles.editorialCard} aria-label="How reviews appear">
          <p className={styles.editorialCardLabel}>{slide.label}</p>
          <h3>{slide.title}</h3>
          <p>{slide.detail}</p>
          <Link to={careHref} className={styles.textLink}>Browse provider profiles <span className={styles.arrow} aria-hidden="true">↗</span></Link>
        </aside>
      </div>
      <div className={styles.editorialDots} aria-label="Choose a review guide slide">
        {slides.map((_, index) => (
          <button
            key={index}
            type="button"
            aria-label={`Show review guide slide ${index + 1} of ${slides.length}`}
            aria-controls="editorial-slide"
            aria-current={index === active ? 'true' : undefined}
            onClick={() => show(index)}
          />
        ))}
      </div>
    </section>
  );
}