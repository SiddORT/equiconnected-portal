import { useEffect, useState } from 'react';
import styles from './HeroNetwork.module.css';

type PointerPosition = {
  x: number;
  y: number;
};

const NODES = [
  { key: 'doctor', label: 'Doctor', short: 'DR', x: 14, y: 43, depth: 1 },
  { key: 'hospital', label: 'Hospital', short: 'H', x: 31, y: 11, depth: 2 },
  { key: 'clinic', label: 'Clinic', short: 'C', x: 84, y: 31, depth: 3 },
  { key: 'location', label: 'Location', short: 'L', x: 76, y: 81, depth: 2 },
  { key: 'specialization', label: 'Specialization', short: 'S', x: 27, y: 80, depth: 1 },
];

const CONNECTIONS = [
  'M 27 45 C 38 40, 39 31, 46 27',
  'M 46 27 C 53 21, 63 27, 73 35',
  'M 73 35 C 77 45, 77 61, 74 73',
  'M 74 73 C 65 80, 58 81, 49 75',
  'M 49 75 C 40 68, 36 58, 27 45',
  'M 46 27 C 52 37, 57 46, 54 53',
  'M 54 53 C 60 60, 66 67, 74 73',
  'M 27 45 C 37 47, 44 49, 54 53',
];

export function HeroNetwork() {
  const [pointer, setPointer] = useState<PointerPosition>({ x: 0, y: 0 });
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined;
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotionPreference = () => setReducedMotion(mediaQuery.matches);
    updateMotionPreference();
    mediaQuery.addEventListener('change', updateMotionPreference);
    return () => mediaQuery.removeEventListener('change', updateMotionPreference);
  }, []);

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (reducedMotion) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    setPointer({
      x: ((event.clientX - bounds.left) / bounds.width - 0.5) * 2,
      y: ((event.clientY - bounds.top) / bounds.height - 0.5) * 2,
    });
  }

  function resetPointer() {
    setPointer({ x: 0, y: 0 });
  }

  return (
    <div
      className={styles.scene}
      aria-label="A connected healthcare network linking members with doctors, clinics, hospitals, specializations, and locations"
      role="img"
      onPointerMove={handlePointerMove}
      onPointerLeave={resetPointer}
    >
      <div
        className={styles.network}
        style={{
          '--pointer-x': `${pointer.x}deg`,
          '--pointer-y': `${pointer.y}deg`,
        } as React.CSSProperties}
      >
        <div className={styles.halo} aria-hidden="true" />
        <div className={`${styles.orbit} ${styles.orbitOne}`} aria-hidden="true" />
        <div className={`${styles.orbit} ${styles.orbitTwo}`} aria-hidden="true" />
        <svg className={styles.connections} viewBox="0 0 100 100" aria-hidden="true">
          <defs>
            <linearGradient id="connection-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#C49B3A" stopOpacity="0.12" />
              <stop offset="48%" stopColor="#C49B3A" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#9BB6C8" stopOpacity="0.22" />
            </linearGradient>
          </defs>
          {CONNECTIONS.map((path, index) => (
            <path key={path} className={styles.connection} d={path} style={{ animationDelay: `${index * 0.35}s` }} />
          ))}
          <circle className={styles.connectionGlow} cx="54" cy="53" r="2.8" />
        </svg>

        <div className={styles.centerNode}>
          <span className={styles.centerOrb} aria-hidden="true"><span>EC</span></span>
          <span className={styles.centerLabel}>Member</span>
        </div>

        {NODES.map((node) => (
          <div
            key={node.key}
            className={`${styles.node} ${styles[`node--${node.key}`]}`}
            style={{
              left: `${node.x}%`,
              top: `${node.y}%`,
              '--node-z': `${node.depth * 12}px`,
            } as React.CSSProperties}
          >
            <span className={styles.nodeDot} aria-hidden="true">{node.short}</span>
            <span className={styles.nodeLabel}>{node.label}</span>
          </div>
        ))}
      </div>
      <div className={styles.sceneCaption} aria-hidden="true">
        <span className={styles.captionRule} />
        <span>One connected care network</span>
      </div>
    </div>
  );
}