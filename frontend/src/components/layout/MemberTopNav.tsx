import { useId, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import styles from './MemberTopNav.module.css';

export function MemberTopNav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const navigationId = useId();

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  }

  return (
    <header className={styles.nav} role="banner">
      <div className={styles.inner}>
        <Link className={styles.brand} to="/" aria-label="EquiConnected home">
          <img src="/logo.png" alt="" className={styles.logo} />
          <span>
            <strong>EquiConnected</strong>
            <small>Member area</small>
          </span>
        </Link>

        <button
          type="button"
          className={styles.menuButton}
          aria-label={menuOpen ? 'Close member navigation' : 'Open member navigation'}
          aria-controls={navigationId}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span aria-hidden="true">{menuOpen ? '×' : '☰'}</span>
          <span className={styles.menuLabel}>Menu</span>
        </button>

        <nav
          id={navigationId}
          className={`${styles.links} ${menuOpen ? styles.linksOpen : ''}`}
          aria-label="Member navigation"
        >
          <NavLink
            to="/providers"
            className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
            onClick={() => setMenuOpen(false)}
          >
            Providers
          </NavLink>
          <NavLink
            to="/profile"
            className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
            onClick={() => setMenuOpen(false)}
          >
            Profile
          </NavLink>
        </nav>

        <div className={styles.account}>
          <span className={styles.accountLabel}>Signed in as</span>
          <span className={styles.name}>{user?.full_name ?? user?.email}</span>
          <button
            type="button"
            className={styles.logout}
            onClick={handleLogout}
            disabled={loggingOut}
          >
            <span aria-hidden="true">↩</span>
            {loggingOut ? 'Logging out…' : 'Logout'}
          </button>
        </div>
      </div>
    </header>
  );
}