/**
 * Public-facing header / navigation bar.
 */
import { Link } from 'react-router-dom';
import styles from './Header.module.css';
import { Button } from '@/components/ui/Button';

export function Header() {
  return (
    <header className={styles.header} role="banner">
      <div className={`container ${styles.inner}`}>
        <Link to="/" className={styles.logo} aria-label="EquiConnected Home">
          <span className={styles.logoMark}>EC</span>
          <span className={styles.logoText}>EquiConnected</span>
        </Link>

        <nav aria-label="Main navigation" className={styles.nav}>
          <a href="#about" className={styles.navLink}>About</a>
          <a href="#platform" className={styles.navLink}>Platform</a>
          <a href="#contact" className={styles.navLink}>Contact</a>
        </nav>

        <div className={styles.actions}>
          <Link to="/admin/login">
            <Button variant="outline" size="sm">Admin Login</Button>
          </Link>
        </div>

        {/* Mobile placeholder — full mobile nav handled in Phase 2 */}
        <button className={styles.menuBtn} aria-label="Open navigation menu">
          <span />
          <span />
          <span />
        </button>
      </div>
    </header>
  );
}
