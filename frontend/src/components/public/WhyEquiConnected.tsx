import styles from './WhyEquiConnected.module.css';

type Advantage = {
  number: string;
  title: string;
  description: string;
  symbol: string;
};

const ADVANTAGES: Advantage[] = [
  {
    number: '01',
    title: 'Location-first discovery',
    description: 'Find relevant care around you.',
    symbol: '⌖',
  },
  {
    number: '02',
    title: 'Specialization-based search',
    description: 'Start with the type of care you need.',
    symbol: '⊹',
  },
  {
    number: '03',
    title: 'Real community insight',
    description: 'Explore ratings, reviews and comments.',
    symbol: '✦',
  },
  {
    number: '04',
    title: 'One connected platform',
    description: 'Doctors, clinics and hospitals in one ecosystem.',
    symbol: '↗',
  },
];

export function WhyEquiConnected() {
  return (
    <section id="why-equiconnected" className={styles.section} aria-labelledby="why-equiconnected-heading">
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

      <div className={styles.advantageGrid}>
        {ADVANTAGES.map((advantage) => (
          <article className={styles.advantageCard} key={advantage.title}>
            <div className={styles.cardTopline}>
              <span className={styles.number}>{advantage.number}</span>
              <span className={styles.symbol} aria-hidden="true">{advantage.symbol}</span>
            </div>
            <h3>{advantage.title}</h3>
            <p>{advantage.description}</p>
            <span className={styles.cardRule} aria-hidden="true" />
          </article>
        ))}
      </div>
    </section>
  );
}