import styles from './HomeV2.module.css';

const tags = [
  { label: 'Stable visit', icon: <><path d="M2 5h9v10H2zM11 9h3l3 3v3h-6z" /><circle cx="5" cy="16" r="1.5" /><circle cx="14" cy="16" r="1.5" /></> },
  { label: 'Hospital / clinic visit', icon: <><path d="M15.5 8c0 5-6.5 10-6.5 10S2.5 13 2.5 8a6.5 6.5 0 1 1 13 0Z" /><circle cx="9" cy="8" r="2" /></> },
  { label: 'Specialization', icon: <><path d="M4 3v6a5 5 0 0 0 10 0V3M2 3h4M12 3h4M9 14v1a3 3 0 0 0 6 0v-2" /><circle cx="16" cy="11.5" r="1.5" /></> },
  { label: 'Emirate', icon: <><circle cx="9" cy="9" r="7" /><path d="m11.5 6.5-1.5 4-4 1.5 1.5-4z" /></> },
  { label: 'Availability', icon: <><rect x="2" y="4" width="14" height="13" rx="2" /><path d="M2 8h14M5 2v4M13 2v4" /></> },
  { label: 'Language', icon: <><path d="M2 5h10M7 2v3M4 8c1 3 3.5 5 7 6M10 5c-.4 3.6-2.6 6.8-6.5 9M11 17l3-8 3 8M12 14h4" /></> },
  { label: 'Emergency services', icon: <><circle cx="9" cy="9" r="7" /><path d="M9 5v4l2.5 2" /></> },
];

export function FindCareTags() {
  return (
    <ul className={styles.findPills} aria-label="Care topics to explore">
      {tags.map(({ label, icon }) => (
        <li key={label}>
          <svg aria-hidden="true" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">{icon}</svg>
          <span>{label}</span>
        </li>
      ))}
    </ul>
  );
}