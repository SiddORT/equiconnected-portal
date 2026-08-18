/**
 * HorseLoader — brand spinner.
 * Outer ring: the horseshoe brand logo rotates slowly.
 * Centre: a warm-brown horse silhouette SVG (static).
 */
import styles from './HorseLoader.module.css';

interface HorseLoaderProps {
  /** Diameter of the whole loader in px. Default 96. */
  size?: number;
  /** Accessible label. */
  label?: string;
}

export function HorseLoader({ size = 96, label = 'Loading…' }: HorseLoaderProps) {
  const inner = Math.round(size * 0.44); // horse icon fits inside the ring

  return (
    <div
      className={styles.wrapper}
      style={{ width: size, height: size }}
      role="status"
      aria-label={label}
    >
      {/* ── Spinning horseshoe ring ──────────────────────────── */}
      <img
        src="/logo.png"
        alt=""
        aria-hidden="true"
        className={styles.ring}
        style={{ width: size, height: size }}
      />

    </div>
  );
}

/** Clean side-profile horse silhouette, fully scalable via currentColor. */
function HorseSVG() {
  return (
    <svg
      viewBox="0 0 64 60"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={styles.horse}
      aria-hidden="true"
    >
      {/* Tail */}
      <path
        d="M12 33 Q3 42 7 53"
        stroke="currentColor"
        strokeWidth="3.5"
        strokeLinecap="round"
        fill="none"
      />

      {/* Body */}
      <ellipse cx="28" cy="31" rx="15" ry="9" fill="currentColor" />

      {/* Haunch (rear hip bump) */}
      <ellipse cx="14" cy="28" rx="6" ry="7" fill="currentColor" />

      {/* Neck */}
      <path
        d="M 38 24 C 40 18 45 14 48 13 L 52 13 C 53 17 51 22 46 25 Z"
        fill="currentColor"
      />

      {/* Head */}
      <ellipse
        cx="51"
        cy="11"
        rx="7"
        ry="5"
        fill="currentColor"
        transform="rotate(-18 51 11)"
      />

      {/* Ear */}
      <polygon points="49,5 52,1 55,6" fill="currentColor" />

      {/* Snout */}
      <rect
        x="55"
        y="10"
        width="6"
        height="4"
        rx="2"
        fill="currentColor"
        transform="rotate(-10 55 10)"
      />

      {/* Nostril */}
      <circle cx="59" cy="13" r="1" fill="white" opacity="0.7" />

      {/* Eye */}
      <circle cx="50" cy="9" r="1.2" fill="white" opacity="0.8" />

      {/* Mane */}
      <path
        d="M 43 14 Q 41 10 43 7 Q 45 10 46 7 Q 48 10 48 13"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
        opacity="0.6"
      />

      {/* Front legs */}
      <rect x="30" y="38" width="4" height="16" rx="2" fill="currentColor" />
      <rect x="36" y="39" width="4" height="15" rx="2" fill="currentColor" />

      {/* Back legs */}
      <rect x="14" y="33" width="4" height="20" rx="2" fill="currentColor" />
      <rect x="20" y="36" width="4" height="18" rx="2" fill="currentColor" />

      {/* Hooves */}
      <rect x="30" y="52" width="5" height="3" rx="1" fill="currentColor" opacity="0.7" />
      <rect x="36" y="52" width="5" height="3" rx="1" fill="currentColor" opacity="0.7" />
      <rect x="13" y="51" width="5" height="3" rx="1" fill="currentColor" opacity="0.7" />
      <rect x="19" y="52" width="5" height="3" rx="1" fill="currentColor" opacity="0.7" />
    </svg>
  );
}
