import styles from './Footer.module.css';

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className={styles.footer} role="contentinfo">
      <div className={`container ${styles.inner}`}>
        <div className={styles.brand}>
          <span className={styles.logoMark}>EC</span>
          <span className={styles.logoText}>EquiConnected</span>
        </div>

        <nav aria-label="Footer navigation" className={styles.links}>
          <a href="#about" className={styles.link}>About</a>
          <a href="#platform" className={styles.link}>Platform</a>
          <a href="#contact" className={styles.link}>Contact</a>
          <a href="/sitemap.xml" className={styles.link}>Sitemap</a>
        </nav>

        <p className={styles.copy}>
          © {year} EquiConnected. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
