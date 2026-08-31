import { Link } from 'react-router-dom';
import styles from './CommunityPreview.module.css';

type PreviewCard = {
  index: string;
  label: string;
  detail: string;
};

const PREVIEW_CARDS: PreviewCard[] = [
  {
    index: '01',
    label: 'Care context',
    detail: 'See the signals members use to compare a care team.',
  },
  {
    index: '02',
    label: 'Shared experience',
    detail: 'Read community notes after you sign in.',
  },
  {
    index: '03',
    label: 'A confident next step',
    detail: 'Keep useful context close as you make a choice.',
  },
];

const RATING_BARS = [
  { label: '5', width: '84%' },
  { label: '4', width: '62%' },
  { label: '3', width: '28%' },
];

export function CommunityPreview() {
  return (
    <section className={styles.section} aria-labelledby="community-preview-heading">
      <div className={styles.headingBlock}>
        <p className={styles.eyebrow}><span aria-hidden="true" />Reviews / Community</p>
        <h2 id="community-preview-heading">
          Real experiences.<br /> <em>Better decisions.</em>
        </h2>
        <p className={styles.description}>
          Once you&apos;re inside, community insight helps you move from a promising profile to
          care that feels right for your horse.
        </p>
        <Link to="/member" className={styles.cta}>
          Explore providers <span aria-hidden="true">↗</span>
        </Link>
      </div>

      <div className={styles.previewShell} aria-label="Illustrative member reviews interface">
        <div className={styles.previewHeader}>
          <div>
            <p className={styles.previewKicker}>Member view preview</p>
            <h3>Community notes</h3>
          </div>
          <span className={styles.previewStatus}>Illustrative</span>
        </div>

        <div className={styles.summary}>
          <div className={styles.scoreBlock}>
            <strong>4.8</strong>
            <span className={styles.stars} aria-label="Illustrative five-star rating">★★★★★</span>
            <span>126 community reviews</span>
          </div>
          <div className={styles.ratingBars} aria-hidden="true">
            {RATING_BARS.map((bar) => (
              <div className={styles.ratingRow} key={bar.label}>
                <span>{bar.label}</span>
                <span className={styles.ratingTrack}><span style={{ width: bar.width }} /></span>
              </div>
            ))}
          </div>
        </div>

        <p className={styles.previewNote}>
          A preview of the context members can explore after signing in. No live review text is
          shown here.
        </p>

        <div className={styles.cardGrid}>
          {PREVIEW_CARDS.map((card) => (
            <article className={styles.reviewCard} key={card.index}>
              <div className={styles.cardTopline}>
                <span>{card.index}</span>
                <span className={styles.cardDots} aria-hidden="true">•••</span>
              </div>
              <div className={styles.memberRow}>
                <span className={styles.avatar} aria-hidden="true">EC</span>
                <span>
                  <strong>Community member</strong>
                  <small>Verified experience</small>
                </span>
              </div>
              <div className={styles.cardStars} aria-hidden="true">★★★★★</div>
              <h4>{card.label}</h4>
              <p>{card.detail}</p>
              <div className={styles.redactedLines} aria-hidden="true">
                <span /><span />
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}