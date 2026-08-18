/**
 * Public "Coming Soon" page for the EquiConnected portal.
 */
import { useState } from 'react';
import styles from './PublicPage.module.css';

export function PublicPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  function handleNotify(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Please enter a valid email address.');
      return;
    }
    setError('');
    setSubmitted(true);
  }

  return (
    <div className={styles.page}>
      {/* ── Background decorative elements ──────────────────────── */}
      <div className={styles.bgCircle1} aria-hidden="true" />
      <div className={styles.bgCircle2} aria-hidden="true" />

      <main className={styles.main} id="main-content">
        {/* ── Logo ─────────────────────────────────────────────── */}
        <header className={styles.header}>
          <div className={styles.logoMark} aria-hidden="true">EC</div>
          <div className={styles.logoText}>
            <span className={styles.logoName}>equiconnected</span>
            <span className={styles.logoTagline}>CONNECTING HORSES WITH THE RIGHT CARE</span>
          </div>
        </header>

        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className={styles.hero} aria-labelledby="coming-soon-heading">
          <p className={styles.preTitle}>We're getting ready</p>
          <h1 id="coming-soon-heading" className={`text-display ${styles.heading}`}>
            Something beautiful
            <span className={styles.headingAccent}> is on its way.</span>
          </h1>
          <p className={styles.subtitle}>
            The EquiConnected portal is launching soon — bringing hospitals, 
            care teams, and visitors together through secure, elegant technology.
          </p>

          {/* ── Notify form ──────────────────────────────────────── */}
          <div className={styles.notifyBlock}>
            {submitted ? (
              <div className={styles.successMessage} role="status">
                <span className={styles.successIcon} aria-hidden="true">✓</span>
                <p>
                  <strong>You're on the list.</strong><br />
                  We'll let you know the moment we launch.
                </p>
              </div>
            ) : (
              <form onSubmit={handleNotify} className={styles.form} noValidate>
                <label htmlFor="notify-email" className={styles.formLabel}>
                  Get notified when we launch
                </label>
                <div className={styles.formRow}>
                  <input
                    id="notify-email"
                    type="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError(''); }}
                    placeholder="your@email.com"
                    className={`${styles.emailInput} ${error ? styles['emailInput--error'] : ''}`}
                    aria-describedby={error ? 'notify-error' : undefined}
                    aria-invalid={!!error}
                    autoComplete="email"
                  />
                  <button type="submit" className={styles.notifyBtn}>
                    Notify Me
                  </button>
                </div>
                {error && (
                  <p id="notify-error" className={styles.errorMsg} role="alert">
                    {error}
                  </p>
                )}
              </form>
            )}
          </div>
        </section>

        {/* ── Features teaser ──────────────────────────────────── */}
        <section className={styles.features} aria-label="What's coming">
          {TEASERS.map((t) => (
            <div key={t.title} className={styles.featureItem}>
              <span className={styles.featureIcon} aria-hidden="true">{t.icon}</span>
              <h2 className={styles.featureTitle}>{t.title}</h2>
              <p className={styles.featureDesc}>{t.desc}</p>
            </div>
          ))}
        </section>

        {/* ── Divider ──────────────────────────────────────────── */}
        <div className={styles.dividerLine} aria-hidden="true" />

        {/* ── Admin link ───────────────────────────────────────── */}
        <div className={styles.adminLink}>
          <a href="/admin/login" className={styles.adminAnchor}>
            Admin Portal →
          </a>
        </div>
      </main>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className={styles.footer} role="contentinfo">
        <p>© {new Date().getFullYear()} EquiConnected. All rights reserved.</p>
      </footer>
    </div>
  );
}

const TEASERS = [
  {
    icon: '🏥',
    title: 'Hospital Portal',
    desc: 'Streamlined tools for healthcare administrators and clinical teams.',
  },
  {
    icon: '🤝',
    title: 'Visitor Coordination',
    desc: 'Secure, dignified access management for families and visitors.',
  },
  {
    icon: '🔒',
    title: 'Built for Trust',
    desc: 'Enterprise-grade security with full audit trails and role-based access.',
  },
];
