/**
 * Public landing page — the EquiConnected public website at /.
 * SEO-optimised with semantic HTML, proper heading hierarchy, and meta tags.
 */
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import styles from './PublicPage.module.css';

export function PublicPage() {
  return (
    <>
      <Header />

      <main id="main-content">
        {/* ── Hero ───────────────────────────────────────────────────────── */}
        <section className={styles.hero} aria-labelledby="hero-heading">
          <div className={`container ${styles.heroInner}`}>
            <div className={styles.heroContent}>
              <div className={styles.heroBadge}>Healthcare Platform</div>
              <h1 id="hero-heading" className={`text-display ${styles.heroHeading}`}>
                Connected care,
                <span className={styles.heroAccent}> without barriers.</span>
              </h1>
              <p className={styles.heroSubtitle}>
                EquiConnected is a next-generation healthcare coordination platform — 
                bridging hospitals, staff, and patients with secure, streamlined digital tools.
              </p>
              <div className={styles.heroActions}>
                <a href="#platform" className={styles.ctaPrimary}>
                  Explore the Platform
                </a>
                <a href="#contact" className={styles.ctaSecondary}>
                  Request a Demo
                </a>
              </div>
            </div>

            <div className={styles.heroVisual} aria-hidden="true">
              <div className={styles.heroCard}>
                <div className={styles.heroCardBadge}>Live</div>
                <div className={styles.heroStat}>
                  <span className={styles.heroStatNumber}>99.9%</span>
                  <span className={styles.heroStatLabel}>Uptime SLA</span>
                </div>
                <div className={styles.heroStat}>
                  <span className={styles.heroStatNumber}>HIPAA</span>
                  <span className={styles.heroStatLabel}>Compliant Architecture</span>
                </div>
                <div className={styles.heroStat}>
                  <span className={styles.heroStatNumber}>End-to-End</span>
                  <span className={styles.heroStatLabel}>Encryption</span>
                </div>
              </div>
            </div>
          </div>

          <div className={styles.heroWave} aria-hidden="true">
            <svg viewBox="0 0 1440 80" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M0,40 C360,80 1080,0 1440,40 L1440,80 L0,80 Z" fill="var(--bg-base)" />
            </svg>
          </div>
        </section>

        {/* ── Trust Strip ────────────────────────────────────────────────── */}
        <section className={styles.trustStrip} aria-label="Trust indicators">
          <div className="container">
            <p className={styles.trustLabel}>Built for security, trust, and scale</p>
            <ul className={styles.trustList} role="list">
              {[
                { icon: '🔐', label: 'End-to-end encryption' },
                { icon: '🏥', label: 'Hospital-grade security' },
                { icon: '✓',  label: 'Role-based access control' },
                { icon: '📋', label: 'Full audit trail' },
                { icon: '⚡', label: 'Real-time updates' },
              ].map((t) => (
                <li key={t.label} className={styles.trustItem}>
                  <span aria-hidden="true">{t.icon}</span>
                  {t.label}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── Platform Overview ──────────────────────────────────────────── */}
        <section id="platform" className={styles.platform} aria-labelledby="platform-heading">
          <div className="container">
            <div className={styles.sectionHeader}>
              <h2 id="platform-heading" className={`text-display ${styles.sectionTitle}`}>
                One platform. Every connection.
              </h2>
              <p className={styles.sectionSubtitle}>
                EquiConnected unifies the entire care coordination workflow — from hospital 
                administrators to visiting family members.
              </p>
            </div>

            <div className={styles.featureGrid} role="list">
              {FEATURES.map((f) => (
                <article key={f.title} className={styles.featureCard} role="listitem">
                  <div className={styles.featureIcon} aria-hidden="true">{f.icon}</div>
                  <h3 className={styles.featureTitle}>{f.title}</h3>
                  <p className={styles.featureDesc}>{f.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ── About ─────────────────────────────────────────────────────── */}
        <section id="about" className={styles.about} aria-labelledby="about-heading">
          <div className="container">
            <div className={styles.aboutGrid}>
              <div className={styles.aboutContent}>
                <h2 id="about-heading" className={`text-display ${styles.sectionTitle}`}>
                  Healthcare deserves better infrastructure.
                </h2>
                <p className={styles.aboutText}>
                  The modern healthcare system runs on disconnected tools, fragmented records, 
                  and paper-based processes. EquiConnected was built to change that — 
                  providing a secure, unified platform for every stakeholder in the care journey.
                </p>
                <p className={styles.aboutText}>
                  From hospital administrators managing complex workflows to visitors navigating 
                  the care process, EquiConnected ensures everyone has the information they 
                  need — securely, and in real time.
                </p>
                <ul className={styles.aboutPoints} role="list">
                  {[
                    'Built on a normalized, auditable data architecture',
                    'Role-based access — right data to the right people',
                    'Designed from the ground up for healthcare compliance',
                  ].map((p) => (
                    <li key={p} className={styles.aboutPoint}>
                      <span className={styles.checkmark} aria-hidden="true">✓</span>
                      {p}
                    </li>
                  ))}
                </ul>
              </div>

              <div className={styles.aboutStats} aria-label="Platform statistics">
                {STATS.map((s) => (
                  <div key={s.label} className={styles.statCard}>
                    <span className={styles.statValue}>{s.value}</span>
                    <span className={styles.statLabel}>{s.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Contact CTA ───────────────────────────────────────────────── */}
        <section id="contact" className={styles.contact} aria-labelledby="contact-heading">
          <div className="container">
            <div className={styles.contactInner}>
              <h2 id="contact-heading" className={`text-display ${styles.contactTitle}`}>
                Ready to transform your care coordination?
              </h2>
              <p className={styles.contactSubtitle}>
                Get in touch with our team to learn how EquiConnected can work for your organisation.
              </p>
              <a href="mailto:hello@equiconnected.com" className={styles.ctaPrimary}>
                Contact Us
              </a>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}

// ── Static content (UI configuration, not application data) ─────────────────

const FEATURES = [
  {
    icon: '🏥',
    title: 'Hospital Administration',
    description:
      'Powerful tools for managing hospital workflows, staff, and patient coordination — all in one secure dashboard.',
  },
  {
    icon: '🔒',
    title: 'Security by Design',
    description:
      'Argon2id password hashing, JWT authentication, role-based access control, and a full audit trail — baked in from day one.',
  },
  {
    icon: '📊',
    title: 'Real-time Visibility',
    description:
      'Live dashboards and activity feeds give administrators an instant view of what's happening across the facility.',
  },
  {
    icon: '👥',
    title: 'Visitor Management',
    description:
      'Streamlined visitor registration, invitation workflows, and secure check-in processes that respect patient privacy.',
  },
  {
    icon: '🔗',
    title: 'Seamless Integration',
    description:
      'Built on open standards with a clean REST API — ready to integrate with existing hospital information systems.',
  },
  {
    icon: '📋',
    title: 'Full Audit Trail',
    description:
      'Every significant action is logged with structured audit records — meeting compliance and accountability requirements.',
  },
];

const STATS = [
  { value: 'HIPAA', label: 'Ready Architecture' },
  { value: '256-bit', label: 'AES Encryption' },
  { value: '< 15 min', label: 'Token Lifetime' },
  { value: '100%', label: 'Audit Coverage' },
];
